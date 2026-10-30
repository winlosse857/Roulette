# Roulette Telegram Bot

## Запуск в Termux (Android)

1. Установи Python и Git:
   ```bash
   pkg update && pkg upgrade
   pkg install python git
   ```

2. Склонируй репозиторий и перейди в папку:
   ```bash
   git clone https://github.com/winlosse857/Roulette.git
   cd Roulette
   ```

3. Установи зависимости:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Задай токен Telegram-бота и секрет админ-панели. Не публикуй их в GitHub:
   ```bash
   export BOT_TOKEN="ТОКЕН_ОТ_BOTFATHER"
   export ADMIN_SECRET_CODE="СЛОЖНЫЙ_СЕКРЕТНЫЙ_КОД"
   ```

   Необязательно можно задать username бота (без @):
   ```bash
   export BOT_USERNAME="username_бота"
   ```

5. Запусти:
   ```bash
   python bot.py
   ```

База данных `roulette_db.json` создаётся рядом с `bot.py` и не отправляется в Git.

## Повторный запуск

После закрытия Termux снова открой папку проекта, задай переменные окружения (если они не сохранены в профиле shell) и выполни `python bot.py`.

Для остановки нажми `Ctrl+C`.
