# 🍌 Nano Banana Telegram Bot

Telegram-бот для генерации и редактирования изображений через **Google Gemini 2.5 Flash Image** (кодовое имя «Nano Banana»).

## Что умеет

- `/gen описание` — сгенерировать одно изображение по тексту
- `/gen4 описание` — сгенерировать 4 варианта
- **Редактирование фото** — пришли фото боту с подписью («сделай фон космическим», «добавь очки» и т. п.)

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # впиши свои ключи
python bot.py
```

## Деплой на Koyeb (бесплатно, 24/7, без карты)

1. Залогинься на [koyeb.com](https://www.koyeb.com) через GitHub.
2. В дашборде: **Create Service → GitHub**, подключи свой аккаунт GitHub и выбери этот репозиторий.
3. Koyeb автоматически найдёт `Dockerfile` и соберёт контейнер.
4. Instance type: **Eco / Free**.
5. В **Environment variables** добавь (как Secret):
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
6. Health check: HTTP, port `8000`, path `/`.
7. **Deploy.** Через пару минут бот запустится — проверь в Telegram.

## Обновление бота

```bash
git add .
git commit -m "update"
git push        # Koyeb автоматически подхватит и передеплоит
```

## Переменные окружения

| Имя | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `GEMINI_API_KEY`     | Ключ из [Google AI Studio](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL`       | (опц.) модель, по умолчанию `gemini-2.5-flash-image` |
| `PORT`               | (опц.) порт health-check, по умолчанию `8000` |

## Структура

```
├── bot.py               # обработчики Telegram + health-check
├── gemini_client.py     # обёртка над Gemini API
├── requirements.txt
├── Dockerfile
├── Procfile             # для платформ, которые его используют
├── .env.example
├── .gitignore
└── README.md
```

## FAQ

**«Gemini returned no images».** Промт заблокирован фильтрами безопасности Google — переформулируй.

**Ошибка `409 Conflict: terminated by other getUpdates request`.** Значит бот запущен в двух местах одновременно. Останови локальную копию — оставь только на Koyeb.

**Как ограничить бота только собой?** Добавь в `bot.py` проверку `update.effective_user.id` против своего ID (узнать — у [@userinfobot](https://t.me/userinfobot)).

## Лицензия

MIT.
