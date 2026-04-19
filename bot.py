"""Telegram bot that uses Google Gemini 2.5 Flash Image ("Nano Banana")
to generate and edit images.

Commands:
    /start   — greeting and help
    /help    — show available commands
    /gen     — generate 1 image from a text prompt
    /gen4    — generate 4 variants from a text prompt

Image editing:
    Send a photo with a caption describing how to change it.
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO

from dotenv import load_dotenv
from telegram import InputMediaPhoto, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import gemini_client

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
# httpx is very chatty — quiet it down.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Привет! Я генерирую и редактирую картинки через Google Gemini "
    "2.5 Flash Image (Nano Banana).\n\n"
    "<b>Команды:</b>\n"
    "/gen <i>описание</i> — сгенерировать 1 изображение\n"
    "/gen4 <i>описание</i> — сгенерировать 4 варианта\n"
    "/help — эта подсказка\n\n"
    "<b>Редактирование фото:</b>\n"
    "Пришли фото с подписью, что именно изменить — "
    "например «сделай фон космическим» или «добавь солнечные очки»."
)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP_TEXT)


async def cmd_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(HELP_TEXT)


async def _generate_and_send(update: Update, prompt: str, n: int) -> None:
    """Shared logic for /gen and /gen4."""
    chat = update.effective_chat
    message = update.effective_message

    if not prompt:
        await message.reply_text(
            "Добавь описание после команды.\nНапример: /gen котик-астронавт в неоновых тонах"
        )
        return

    await chat.send_action(ChatAction.UPLOAD_PHOTO)
    status = await message.reply_text(
        f"Генерирую {n} изображени{'е' if n == 1 else 'й'}... ⏳"
    )

    try:
        images = await asyncio.to_thread(gemini_client.generate_images, prompt, n)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generation failed")
        await status.edit_text(f"❌ Ошибка генерации: {html.escape(str(exc))}")
        return

    try:
        if len(images) == 1:
            await chat.send_photo(
                photo=BytesIO(images[0]),
                caption=f"🍌 {prompt}",
            )
        else:
            media = [
                InputMediaPhoto(
                    media=BytesIO(img),
                    caption=f"🍌 {prompt}" if i == 0 else None,
                )
                for i, img in enumerate(images)
            ]
            # Telegram allows up to 10 media per album.
            await chat.send_media_group(media=media[:10])
        await status.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send images")
        await status.edit_text(f"❌ Не удалось отправить: {html.escape(str(exc))}")


async def cmd_gen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(ctx.args) if ctx.args else ""
    await _generate_and_send(update, prompt, n=1)


async def cmd_gen4(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(ctx.args) if ctx.args else ""
    await _generate_and_send(update, prompt, n=4)


async def handle_photo(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Edit an uploaded photo using its caption as the prompt."""
    message = update.effective_message
    chat = update.effective_chat
    prompt = (message.caption or "").strip()

    if not prompt:
        await message.reply_text(
            "Добавь подпись к фото с описанием, что изменить.\n"
            "Например: «сделай фон закатом»."
        )
        return

    await chat.send_action(ChatAction.UPLOAD_PHOTO)
    status = await message.reply_text("Редактирую изображение... ⏳")

    try:
        # Pick the highest-resolution photo Telegram offers.
        photo = message.photo[-1]
        tg_file = await photo.get_file()
        buf = BytesIO()
        await tg_file.download_to_memory(out=buf)
        buf.seek(0)
        source = buf.read()

        edited = await asyncio.to_thread(gemini_client.edit_image, source, prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Edit failed")
        await status.edit_text(f"❌ Ошибка редактирования: {html.escape(str(exc))}")
        return

    try:
        await chat.send_photo(photo=BytesIO(edited), caption=f"✏️ {prompt}")
        await status.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send edited image")
        await status.edit_text(f"❌ Не удалось отправить: {html.escape(str(exc))}")


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=ctx.error)


class _HealthHandler(BaseHTTPRequestHandler):
    """Tiny HTTP server so Koyeb/Render health checks pass."""

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Quiet: we don't need every health-check ping in logs.
        return


def _start_health_server() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health-check HTTP server listening on :%d", port)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("gen", cmd_gen))
    app.add_handler(CommandHandler("gen4", cmd_gen4))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(on_error)

    _start_health_server()

    logger.info("Bot starting (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
