# Деплой на Railway

Бот работает на long-polling, поэтому это обычный **worker** — публичный порт,
домен и вебхуки не нужны.

## 0. Что уже подготовлено в репозитории

- `railway.json` — builder Nixpacks, старт-команда `python run.py`, **1 реплика**
  (важно: polling + планировщик нельзя запускать в 2+ копиях), рестарт при падении.
- `.python-version` — фиксирует Python 3.13.
- `requirements.txt` — зависимости.
- `.env` и `*.db` в `.gitignore` — секреты и локальная база НЕ попадают в репозиторий.

## 1. Залить код

Вариант A — через GitHub (рекомендуется):
```powershell
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```
Затем в Railway: **New Project → Deploy from GitHub repo** → выбрать репозиторий.

Вариант B — через Railway CLI (без GitHub):
```powershell
npm i -g @railway/cli
railway login
railway init
railway up
```

## 2. Постоянный диск для SQLite (Volume) ⚠️

Без тома файл `bot.db` стирается при каждом редеплое. Поэтому:

1. В сервисе Railway → вкладка **Variables → Volumes** (или **Settings → Volumes**)
   → **New Volume**.
2. Mount path: **`/data`**.
3. В переменных окружения задать путь к базе на этом томе (см. ниже).

## 3. Переменные окружения (Railway → Variables)

Скопировать значения из локального `.env`, но **`DATABASE_URL` поменять на путь
внутри тома** (четыре слэша = абсолютный путь):

```
BOT_TOKEN=<токен бота>
ADMIN_CHAT_ID=1125622099

DEEPSEEK_API_KEY=<ключ DeepSeek>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

EMAIL_ADDRESS=studymate@mail.ru
EMAIL_PASSWORD=<пароль приложения mail.ru>
SMTP_HOST=smtp.mail.ru
SMTP_PORT=465
IMAP_HOST=imap.mail.ru
IMAP_PORT=993

DATABASE_URL=sqlite+aiosqlite:////data/bot.db

FOLLOWUP_DELAY_DAYS=3
MAX_FOLLOWUPS=2
REMINDER_OFFSET_DAYS=7
```

> ⚠️ Секреты в дашборде, не в коде. Никогда не коммить реальный `.env`.

## 4. Первый запуск

`init_db()` создаёт таблицы автоматически на старте. База будет пустой —
возможности появятся после импорта реальной базы почт. Чтобы наполнить демо-данными
для проверки, можно один раз выполнить в Railway shell:
```
python seed_data.py
```

## 5. Логи и проверка

Railway → сервис → **Deployments → View Logs**. Должна быть строка
`Бот запущен. Планировщик активен.` После этого открой бота в Telegram → `/start`.
