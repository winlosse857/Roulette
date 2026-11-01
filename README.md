# NOVA AI

NOVA AI — веб-интерфейс ИИ-помощника на Claude.

## Публикация интерфейса
`index.html` находится в корне репозитория, поэтому GitHub Pages сможет опубликовать страницу: Settings → Pages → Deploy from a branch → `main` → `/ (root)`.

## Важно про Claude API
GitHub Pages размещает только статические файлы и **не запускает** `server.mjs`. Чтобы чат отвечал, разверни Node.js backend на отдельном хостинге и добавь там `ANTHROPIC_API_KEY` в секретные переменные окружения. Затем настрой адрес `/api/chat` в `index.html` на адрес backend (с включённым CORS для сайта).

## Локальный запуск
Нужен Node.js 20+. Скопируй `.env.example` в `.env`, добавь ключ Anthropic только в `.env`, затем выполни `npm start` и открой http://localhost:3000.

Не публикуй API-ключ и не добавляй `.env` в Git. Запросы Claude могут тарифицироваться Anthropic.
