import telebot
import random
import json
import os
import time
import threading
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════
# НАСТРОЙКИ (ВПИШИ СВОЙ ТОКЕН И СЕРВЕР)
# ═══════════════════════════════════════════════
TOKEN = "ВАШ_ТОКЕН_БОТА"
SERVER_URL = "http://177.3.213.27:8081"
apihelper.API_URL = f"{SERVER_URL}/bot{{0}}/{{1}}"
apihelper.FILE_URL = f"{SERVER_URL}/file/bot{{0}}/{{1}}"
bot = telebot.TeleBot(TOKEN)

DB_FILE = "roulette_db.json"
BOT_USERNAME = "ТВОЙ_БОТ_БЕЗ_@"
SHOP_UPDATE_INTERVAL = 15 * 60
ADMIN_SECRET_CODE = "777"  # Секретный код для входа в админку (поменяй)

# ═══════════════════════════════════════════════
# БАЗА
# ═══════════════════════════════════════════════
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "users" not in data: data["users"] = {}
            if "games" not in data: data["games"] = {}
            if "promos" not in data: 
                data["promos"] = {
                    "ROULETTE": {"type": "tokens", "amount": 500}, 
                    "START": {"type": "tokens", "amount": 100}
                }
            if "shop_stock" not in data: data["shop_stock"] = {}
            if "shop_timer" not in data: data["shop_timer"] = 0
            if "waiting_step" not in data: data["waiting_step"] = {}
            if "pending_count" not in data: data["pending_count"] = {}
            return data
        except Exception: pass
    return {
        "users": {}, "games": {}, 
        "promos": {"ROULETTE": {"type": "tokens", "amount": 500}, "START": {"type": "tokens", "amount": 100}}, 
        "shop_stock": {}, "shop_timer": 0, "waiting_step": {}, "pending_count": {}
    }

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

db = load_db()

def update_shop_stock():
    now = int(time.time())
    if now - db.get("shop_timer", 0) >= SHOP_UPDATE_INTERVAL or not db.get("shop_stock"):
        stock = {}
        if random.random() < 0.6: stock["xray"] = random.randint(1, 5)
        if random.random() < 0.5: stock["pill"] = random.randint(5, 15)
        if random.random() < 0.1: stock["angel"] = 1
        db["shop_stock"] = stock
        db["shop_timer"] = now
        save_db(db)

def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {
            "balance": 1000, "wins": 0, "deaths": 0, "username": None,
            "used_promos": [], "afk_count": 0, "ban_until": 0, "last_minus_bonus": 0,
            "inventory": {"xray": 0, "pill": 0, "angel": 0},
            "buffs": {"angel_active": False}
        }
        save_db(db)
    u = db["users"][uid]
    if "inventory" not in u: u["inventory"] = {"xray": 0, "pill": 0, "angel": 0}
    if "buffs" not in u: u["buffs"] = {"angel_active": False}
    return u

# ═══════════════════════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════════════════════
def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Добавить в чат", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"),
        InlineKeyboardButton("🎮 Мини-игры", callback_data="mini_games_menu"),
        InlineKeyboardButton("📖 Подробнее", callback_data="about"),
        InlineKeyboardButton("🛒 Магазин", callback_data="shop_menu"),
        InlineKeyboardButton("🔐 Секретный код", callback_data="secret_code"),
        InlineKeyboardButton("🏆 Топ игроков", callback_data="top_menu"),
        InlineKeyboardButton("👤 Мой профиль", callback_data="profile")
    )
    return kb

def shop_menu():
    update_shop_stock()
    stock = db["shop_stock"]
    kb = InlineKeyboardMarkup(row_width=1)
    if stock.get("xray", 0) > 0:
        kb.add(InlineKeyboardButton(f"👓 Рентген-очки (осталось: {stock['xray']}) — 250", callback_data="buy_xray"))
    if stock.get("pill", 0) > 0:
        kb.add(InlineKeyboardButton(f"💊 Таблетка (осталось: {stock['pill']}) — 50", callback_data="buy_pill"))
    if stock.get("angel", 0) > 0:
        kb.add(InlineKeyboardButton(f"👼 Зелье ангела (осталось: {stock['angel']}) — 1600", callback_data="buy_angel"))
    kb.add(InlineKeyboardButton("🔄 Обновить магазин", callback_data="shop_menu"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))
    return kb

def turn_kb(game_id):
    game = db["games"].get(game_id)
    current_p = game["players"][game["turn"]]
    user = get_user(current_p)
    inv = user.get("inventory", {})
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔫 Выстрелить в себя", callback_data=f"shoot_self_{game_id}"))
    kb.add(InlineKeyboardButton("🎯 Выстрелить в других", callback_data=f"shoot_other_{game_id}"))
    if inv.get("xray", 0) > 0:
        kb.add(InlineKeyboardButton(f"👓 Рентген ({inv['xray']})", callback_data=f"use_xray_{game_id}"))
    if inv.get("pill", 0) > 0:
        kb.add(InlineKeyboardButton(f"💊 Таблетка ({inv['pill']})", callback_data=f"use_pill_{game_id}"))
    return kb

def target_kb(game_id):
    game = db["games"].get(game_id)
    kb = InlineKeyboardMarkup(row_width=2)
    current_p = game["players"][game["turn"]]
    for p in game["players"]:
        if p != current_p:
            kb.add(InlineKeyboardButton(f"🎯 {p}", callback_data=f"target_{game_id}_{p}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"back_turn_{game_id}"))
    return kb

def players_kb(game_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("✅ Присоединиться", callback_data=f"join_{game_id}"))
    kb.add(InlineKeyboardButton("🚀 Начать игру (Владелец)", callback_data=f"start_{game_id}"))
    kb.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{game_id}"))
    return kb

def top_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🪙 По токенам", callback_data="top_tokens"),
        InlineKeyboardButton("🏆 По победам", callback_data="top_wins")
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))
    return kb

def back_kb():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="refresh"))

# ═══════════════════════════════════════════════
# ХЕЛПЕРЫ
# ═══════════════════════════════════════════════
def safe_answer(call, text=None, show_alert=False):
    try: bot.answer_callback_query(call.id, text=text, show_alert=show_alert)
    except Exception: pass

def safe_send(chat_id, text, markup=None):
    try: return bot.send_message(chat_id, text, reply_markup=markup)
    except Exception: return None

def safe_edit(chat_id, message_id, text, markup=None):
    try: bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)
    except Exception: pass

# ═══════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def start(message):
    u = get_user(message.from_user.id)
    u["username"] = message.from_user.username or message.from_user.first_name
    save_db(db)
    text = ("Привет! Я игровой бот Roulette! 👋\n\n"
            "Я помогу поднять настроение тебе! Добавь меня в чат, "
            "и посмотрим, кто из нас останется в живых 😈")
    safe_send(message.chat.id, text, main_menu())

# ═══════════════════════════════════════════════
# АДМИН-ПАНЕЛЬ (ПРОМОКОДЫ)
# ═══════════════════════════════════════════════
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    bot.send_message(message.chat.id, "🔐 Введи секретный код:")
    bot.register_next_step_handler(message, admin_check)

def admin_check(message):
    if message.text.strip() == ADMIN_SECRET_CODE:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton("➕ Промокод на Токены", callback_data="adm_create_tokens"),
            InlineKeyboardButton("🎁 Промокод на Предмет", callback_data="adm_create_item"),
            InlineKeyboardButton("📋 Список промокодов", callback_data="adm_list_promos"),
            InlineKeyboardButton("❌ Удалить промокод", callback_data="adm_delete_promo")
        )
        bot.send_message(message.chat.id, "👑 АДМИН-ПАНЕЛЬ", reply_markup=kb)
    else:
        bot.send_message(message.chat.id, "❌ Неверный код.")

@bot.callback_query_handler(func=lambda c: c.data == "adm_create_tokens")
def adm_create_tokens(call):
    safe_answer(call)
    bot.send_message(call.message.chat.id, "Введи: `КОД СУММА`\nПример: `WIN 500`")
    bot.register_next_step_handler(call.message, adm_process_tokens)

def adm_process_tokens(message):
    parts = message.text.split()
    if len(parts) != 2: return safe_send(message.chat.id, "❌ Формат: `КОД СУММА`")
    code, amount_str = parts[0].upper(), parts[1]
    try: amount = int(amount_str)
    except ValueError: return safe_send(message.chat.id, "❌ Сумма должна быть числом.")
    
    db["promos"][code] = {"type": "tokens", "amount": amount}
    save_db(db)
    safe_send(message.chat.id, f"✅ Промокод `{code}` на {amount} токенов создан!")

@bot.callback_query_handler(func=lambda c: c.data == "adm_create_item")
def adm_create_item(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👓 Рентген-очки", callback_data="adm_item_xray"),
        InlineKeyboardButton("💊 Таблетка", callback_data="adm_item_pill"),
        InlineKeyboardButton("👼 Зелье ангела", callback_data="adm_item_angel")
    )
    safe_edit(call.message.chat.id, call.message.message_id, "Выбери предмет:", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_item_"))
def adm_item_chosen(call):
    item = call.data.replace("adm_item_", "")
    names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
    bot.send_message(call.message.chat.id, f"Введи: `КОД КОЛИЧЕСТВО` для предмета *{names[item]}*\nПример: `XRAY3 5`")
    bot.register_next_step_handler(call.message, adm_process_item, item)

def adm_process_item(message, item):
    parts = message.text.split()
    if len(parts) != 2: return safe_send(message.chat.id, "❌ Формат: `КОД КОЛИЧЕСТВО`")
    code, amount_str = parts[0].upper(), parts[1]
    try: amount = int(amount_str)
    except ValueError: return safe_send(message.chat.id, "❌ Количество должно быть числом.")
    
    db["promos"][code] = {"type": "item", "item": item, "amount": amount}
    save_db(db)
    names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
    safe_send(message.chat.id, f"✅ Промокод `{code}` на {amount} шт. ({names[item]}) создан!")

@bot.callback_query_handler(func=lambda c: c.data == "adm_list_promos")
def adm_list_promos(call):
    safe_answer(call)
    if not db["promos"]:
        return safe_edit(call.message.chat.id, call.message.message_id, "📭 Список пуст.", None)
    lines = ["📋 СПИСОК ПРОМОКОДОВ:\n"]
    for code, data in db["promos"].items():
        if data["type"] == "tokens":
            lines.append(f"• `{code}` — {data['amount']} токенов")
        else:
            lines.append(f"• `{code}` — {data['amount']} шт. ({data['item']})")
    safe_edit(call.message.chat.id, call.message.message_id, "\n".join(lines), back_kb())

@bot.callback_query_handler(func=lambda c: c.data == "adm_delete_promo")
def adm_delete_promo(call):
    safe_answer(call)
    bot.send_message(call.message.chat.id, "Введи код промокода для удаления:")
    bot.register_next_step_handler(call.message, adm_process_delete)

def adm_process_delete(message):
    code = message.text.strip().upper()
    if code in db["promos"]:
        del db["promos"][code]
        save_db(db)
        safe_send(message.chat.id, f"✅ Промокод `{code}` удален.")
    else:
        safe_send(message.chat.id, "❌ Промокод не найден.")

# ═══════════════════════════════════════════════
# МАГАЗИН
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "shop_menu")
def shop(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    update_shop_stock()
    time_left = SHOP_UPDATE_INTERVAL - (int(time.time()) - db["shop_timer"])
    min_left = max(0, time_left // 60)
    txt = (f"🛒 ТОКЕН-МАГАЗИН\n\n"
           f"💵 Твой баланс: {user['balance']}\n"
           f"🎒 Инвентарь: 👓 {user['inventory']['xray']} | 💊 {user['inventory']['pill']} | 👼 {user['inventory']['angel']}\n\n"
           f"🕒 Сток обновится через: {min_left} мин.\n"
           f"Выбирай товар:")
    safe_edit(call.message.chat.id, call.message.message_id, txt, shop_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_item(call):
    item = call.data.replace("buy_", "")
    user = get_user(call.from_user.id)
    update_shop_stock()
    prices = {"xray": 250, "pill": 50, "angel": 1600}
    if item not in prices: return safe_answer(call, "❌ Нет такого товара.")
    if db["shop_stock"].get(item, 0) <= 0: return safe_answer(call, "❌ Товар закончился! Жди обновления.", show_alert=True)
    price = prices[item]
    if user["balance"] < price: return safe_answer(call, f"❌ Нужно {price} токенов!", show_alert=True)
    user["balance"] -= price
    user["inventory"][item] += 1
    db["shop_stock"][item] -= 1
    save_db(db)
    names = {"xray": "👓 Рентген-очки", "pill": "💊 Таблетка", "angel": "👼 Зелье ангела"}
    safe_answer(call, f"✅ {names[item]} куплен!", show_alert=True)
    shop(call)

# ═══════════════════════════════════════════════
# СОЗДАНИЕ ИГРЫ (ВВОД ЧЕРЕЗ БАЗУ)
# ═══════════════════════════════════════════════
@bot.message_handler(commands=["create_game"])
def create_game(message):
    if message.chat.type == "private":
        return safe_send(message.chat.id, "❌ Игры доступны только в группах!")
    chat_id = str(message.chat.id)
    u = get_user(message.from_user.id)
    if u["balance"] < 0: return safe_send(message.chat.id, "❌ Твой баланс в минусе. Выйди из него через мини-игры.")
    if time.time() < u.get("ban_until", 0): return safe_send(message.chat.id, f"❌ Ты забанен за АФК. Осталось: {int(u['ban_until'] - time.time())} сек.")
    for gid, g in db["games"].items():
        if g["chat_id"] == chat_id and g["status"] in ("lobby", "playing"):
            return safe_send(message.chat.id, "❌ В этом чате уже есть активная игра!")
    
    db["waiting_step"][str(message.from_user.id)] = "players_count"
    save_db(db)
    safe_send(message.chat.id, "🔫 Сколько игроков будет в игре? (от 2 до 10)")

@bot.message_handler(func=lambda m: db.get("waiting_step", {}).get(str(m.from_user.id)) == "players_count")
def process_players_count(message):
    if message.text.startswith("/"): return
    try:
        count = int(message.text.strip())
        if count < 2 or count > 10: 
            return safe_send(message.chat.id, "❌ От 2 до 10.")
    except ValueError: 
        return safe_send(message.chat.id, "❌ Введи число.")
    
    db["waiting_step"][str(message.from_user.id)] = "bet"
    db["pending_count"][str(message.from_user.id)] = count
    save_db(db)
    safe_send(message.chat.id, "💰 Ставка в токенах (0 — бесплатно):")

@bot.message_handler(func=lambda m: db.get("waiting_step", {}).get(str(m.from_user.id)) == "bet")
def process_bet(message):
    if message.text.startswith("/"): return
    user_id = str(message.from_user.id)
    
    try:
        bet = int(message.text.strip())
        if bet < 0: return safe_send(message.chat.id, "❌ Ставка >= 0.")
    except ValueError: return safe_send(message.chat.id, "❌ Введи число.")

    count = db["pending_count"].get(user_id, 2)
    
    if user_id in db["waiting_step"]: del db["waiting_step"][user_id]
    if user_id in db["pending_count"]: del db["pending_count"][user_id]
    save_db(db)

    game_id = f"{user_id}_{int(time.time())}"
    db["games"][game_id] = {
        "creator": user_id, "chat_id": str(message.chat.id),
        "players_needed": count, "bet": bet, "players": [user_id],
        "lives": {user_id: 6}, "status": "lobby", "turn": 0,
        "afk_warned": [], "username": message.from_user.username or user_id
    }
    save_db(db)
    text = (
        f"Хей смельчаки! Хотите пострелять?) Присоединяйтесь к нам! "
        f"И узнаем, сколько есть у вас смелости))😈\n\n"
        f"👤 Создатель: @{message.from_user.username or user_id}\n"
        f"💵 Ставка: {bet if bet > 0 else 'Бесплатно'}\n"
        f"👥 Игроков: 1/{count}\n\nЖдём остальных..."
    )
    safe_send(message.chat.id, text, players_kb(game_id))

# ═══════════════════════════════════════════════
# JOIN & START
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("join_"))
def join_game(call):
    game_id = call.data.replace("join_", "")
    game = db["games"].get(game_id)
    user = get_user(call.from_user.id)
    if not game or game["status"] != "lobby": return safe_answer(call, "❌ Игра неактивна.", show_alert=True)
    if str(call.from_user.id) in game["players"]: return safe_answer(call, "❌ Ты уже в игре.", show_alert=True)
    if user["balance"] < 0: return safe_answer(call, "❌ Баланс в минусе!", show_alert=True)
    if len(game["players"]) >= game["players_needed"]: return safe_answer(call, "❌ Мест нет!", show_alert=True)

    game["players"].append(str(call.from_user.id))
    game["lives"][str(call.from_user.id)] = 6
    save_db(db)
    safe_answer(call, "✅ Ты в игре!")
    text = (f"Хей смельчаки! Хотите пострелять?) Присоединяйтесь к нам! "
            f"👤 Создатель: @{game['username']}\n"
            f"💵 Ставка: {game['bet'] if game['bet'] > 0 else 'Бесплатно'}\n"
            f"👥 Игроков: {len(game['players'])}/{game['players_needed']}\n\nЖдём остальных...")
    safe_edit(call.message.chat.id, call.message.message_id, text, players_kb(game_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("start_"))
def start_game(call):
    game_id = call.data.replace("start_", "")
    game = db["games"].get(game_id)
    if not game or game["status"] != "lobby": return safe_answer(call, "❌ Игра неактивна.", show_alert=True)
    if str(call.from_user.id) != game["creator"]: return safe_answer(call, "❌ Только владелец!", show_alert=True)
    if len(game["players"]) < 2: return safe_answer(call, "❌ Нужно от 2 игроков.", show_alert=True)

    game["status"] = "playing"
    game["turn"] = 0
    save_db(db)
    safe_answer(call, "🔫 Игра началась!")
    next_turn(game_id, call.message.chat.id)

def next_turn(game_id, chat_id):
    game = db["games"].get(game_id)
    if not game or game["status"] != "playing": return
    current_player = game["players"][game["turn"]]
    user = get_user(current_player)
    hp = game['lives'][current_player]
    lives = hp / 2
    text = (f"🔫 ВЫШЛА ОЧЕРЕДЬ, ДОРОГОЙ ДРУГ!\n\n"
            f"Игрок: @{user['username'] or current_player}\n"
            f"❤️ Твои жизни: {lives}/3\n"
            f"👥 Живых: {len(game['players'])}\n\n"
            f"Время идёт... Выбирай действие:")
    safe_send(chat_id, text, turn_kb(game_id))
    start_afk_timer(game_id, chat_id)

def start_afk_timer(game_id, chat_id):
    def timer():
        time.sleep(60)
        game = db["games"].get(game_id)
        if not game or game["status"] != "playing": return
        current_player = game["players"][game["turn"]]
        user = get_user(current_player)
        warns = game["afk_warned"].count(current_player)

        if warns == 0:
            game["afk_warned"].append(current_player)
            save_db(db)
            safe_send(chat_id, f"⚠️ @{user['username'] or current_player}, твой ход! Штраф за АФК.")
            start_afk_timer(game_id, chat_id)
        elif warns == 1:
            game["afk_warned"].append(current_player)
            user["balance"] -= 10
            save_db(db)
            safe_send(chat_id, f"💸 @{user['username'] or current_player}, -10 токенов за АФК.")
      game["turn"] = (game["turn"] + 1) % len(game["players"])
            save_db(db)
            next_turn(game_id, chat_id)
        else:
            user["ban_until"] = time.time() + 300
            game["players"].remove(current_player)
            del game["lives"][current_player]
            save_db(db)
            safe_send(chat_id, f"🚫 @{user['username'] or current_player} кикнут (АФК).")
            if len(game["players"]) <= 1:
                finish_game(game_id, chat_id)
            else:
                game["turn"] = game["turn"] % len(game["players"])
                save_db(db)
                next_turn(game_id, chat_id)
    threading.Thread(target=timer, daemon=True).start()

# ═══════════════════════════════════════════════
# ИСПОЛЬЗОВАНИЕ ПРЕДМЕТОВ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("use_xray_"))
def use_xray(call):
    game_id = call.data.replace("use_xray_", "")
    game = db["games"].get(game_id)
    current_p = game["players"][game["turn"]]
    if str(call.from_user.id) != current_p: return safe_answer(call, "❌ Не твой ход!")
    user = get_user(current_p)
    if user["inventory"]["xray"] <= 0: return safe_answer(call, "❌ Нет очков!")
    user["inventory"]["xray"] -= 1
    save_db(db)
    is_bullet = random.random() < (1/6)
    status = "БОЕВОЙ 🔴" if is_bullet else "ХОЛОСТОЙ ⚪"
    try:
        bot.send_message(call.from_user.id, f"👓 Твой рентген показывает: патрон **{status}**")
        safe_answer(call, "📩 Инфа отправлена в ЛС!")
    except Exception:
        safe_answer(call, "⚠️ Не могу написать в ЛС! Нажми /start у бота в личке.", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("use_pill_"))
def use_pill(call):
    game_id = call.data.replace("use_pill_", "")
    game = db["games"].get(game_id)
    current_p = game["players"][game["turn"]]
    if str(call.from_user.id) != current_p: return safe_answer(call, "❌ Не твой ход!")
    user = get_user(current_p)
    if user["inventory"]["pill"] <= 0: return safe_answer(call, "❌ Нет таблеток!")
    user["inventory"]["pill"] -= 1
    msg = safe_send(call.message.chat.id, "💊 Ты проглотил таблетку...")
    time.sleep(1)
    if random.random() < 0.5:
        game["lives"][current_p] = 0
        txt = "💀 Таблетка оказалась ядом! Ты умираешь..."
        game["players"].remove(current_p)
        del game["lives"][current_p]
        if len(game["players"]) <= 1:
            save_db(db)
            return finish_game(game_id, call.message.chat.id, msg)
        game["turn"] = game["turn"] % len(game["players"])
    else:
        game["lives"][current_p] = min(6, game["lives"][current_p] + 2)
        txt = "👼 Таблетка дала тебе жизнь! (+1 жизнь)"
        game["turn"] = (game["turn"] + 1) % len(game["players"])
    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, txt, None)
    time.sleep(1)
    next_turn(game_id, call.message.chat.id)

# ═══════════════════════════════════════════════
# ВЫСТРЕЛ В СЕБЯ / В ДРУГИХ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("shoot_self_"))
def shoot_self(call):
    game_id = call.data.replace("shoot_self_", "")
    game = db["games"].get(game_id)
    if not game or game["status"] != "playing": return safe_answer(call, "❌ Игра неактивна.", show_alert=True)
    current_player = game["players"][game["turn"]]
    if str(call.from_user.id) != current_player: return safe_answer(call, "❌ Не твой ход!", show_alert=True)

    safe_answer(call, "🔫 Спускаем курок...")
    msg = safe_send(call.message.chat.id, "🔄 Крутим барабан...")
    if msg:
        time.sleep(1)
        safe_edit(msg.chat.id, msg.message_id, "💥 БАМ!")

    is_bullet = random.random() < (1/6)
    if is_bullet:
        game["lives"][current_player] -= 1
        hp = game["lives"][current_player]
        txt = f"💀 Ты выстрелил в себя и попал! -0.5 жизни.\n❤️ Осталось: {hp/2}/3\n"
        user = get_user(current_player)
        if hp <= 0 and user["buffs"]["angel_active"]:
            user["buffs"]["angel_active"] = False
            game["lives"][current_player] = 2
            txt += "👼 ЗЕЛЬЕ АНГЕЛА АКТИВИРОВАНО! Ты воскрес с 1 жизнью!\n"
        elif hp <= 0:
            game["players"].remove(current_player)
            del game["lives"][current_player]
            txt += "☠️ Ты выбыл!\n"
            if len(game["players"]) <= 1:
                save_db(db)
                return finish_game(game_id, call.message.chat.id, msg)
            game["turn"] = game["turn"] % len(game["players"])
        else:
            game["turn"] = (game["turn"] + 1) % len(game["players"])
    else:
        txt = "🎯 Щелчок! Пусто.\n"
        game["turn"] = (game["turn"] + 1) % len(game["players"])

    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, txt + "\nСледующий ход...", None)
    time.sleep(1)
    next_turn(game_id, call.message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("shoot_other_"))
def shoot_other(call):
    game_id = call.data.replace("shoot_other_", "")
    game = db["games"].get(game_id)
    if not game or game["status"] != "playing": return safe_answer(call, "❌ Игра неактивна.", show_alert=True)
    current_player = game["players"][game["turn"]]
    if str(call.from_user.id) != current_player: return safe_answer(call, "❌ Не твой ход!", show_alert=True)
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🎯 В кого стреляем?", target_kb(game_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("back_turn_"))
def back_turn(call):
    game_id = call.data.replace("back_turn_", "")
        safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🎯 В кого стреляем?", target_kb(game_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("back_turn_"))
def back_turn(call):
    game_id = call.data.replace("back_turn_", "")
    safe_answer(call)
    next_turn(game_id, call.message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("target_"))
def target_chosen(call):
    parts = call.data.split("_")
    game_id = parts[1]
    target_id = parts[2]
    game = db["games"].get(game_id)
    if not game or game["status"] != "playing": return safe_answer(call, "❌ Игра неактивна.", show_alert=True)
    current_player = game["players"][game["turn"]]
    if str(call.from_user.id) != current_player: return safe_answer(call, "❌ Не твой ход!", show_alert=True)

    safe_answer(call, "🎯 Стреляем...")
    msg = safe_send(call.message.chat.id, "🔄 Крутим барабан...")
    if msg:
        time.sleep(1)
        safe_edit(msg.chat.id, msg.message_id, "💥 БАМ!")

    is_bullet = random.random() < (1/6)
    if is_bullet:
        game["lives"][target_id] -= 2
        t_user = get_user(target_id)
        hp = game["lives"][target_id]
        txt = f"💀 @{t_user['username'] or target_id} получил пулю!\n❤️ Осталось: {hp/2}/3\n"
        if hp <= 0 and t_user["buffs"]["angel_active"]:
            t_user["buffs"]["angel_active"] = False
            game["lives"][target_id] = 2
            txt += f"👼 @{t_user['username'] or target_id} ВОСКРЕС (Зелье ангела)!\n"
        elif hp <= 0:
            game["players"].remove(target_id)
            del game["lives"][target_id]
            txt += f"☠️ @{t_user['username'] or target_id} выбыл!\n"
            if len(game["players"]) <= 1:
                save_db(db)
                return finish_game(game_id, call.message.chat.id, msg)
            game["turn"] = game["turn"] % len(game["players"])
        else:
            game["turn"] = (game["turn"] + 1) % len(game["players"])
    else:
        txt = "🎯 Щелчок! Пусто. Выстрел в молоко.\n"
        game["turn"] = (game["turn"] + 1) % len(game["players"])

    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, txt + "\nСледующий ход...", None)
    time.sleep(1)
    next_turn(game_id, call.message.chat.id)

# ═══════════════════════════════════════════════
# ЗАВЕРШЕНИЕ ИГРЫ
# ═══════════════════════════════════════════════
def finish_game(game_id, chat_id, msg=None):
    game = db["games"].get(game_id)
    game["status"] = "finished"
    if len(game["players"]) == 1:
        winner_id = game["players"][0]
        winner = get_user(winner_id)
        base_win = random.randint(10, 100) if random.random() > 0.2 else random.randint(10, 50)
        total_win = base_win * game["players_needed"]
        winner["balance"] += total_win
        winner["wins"] += 1
        for p in list(db["users"].keys()):
            if p in game["lives"] and game["lives"][p] <= 0 and game["bet"] > 0:
                get_user(p)["balance"] -= game["bet"]
        save_db(db)
        text = (f"🏆 ИГРА ЗАВЕРШЕНА!\n\n"
                f"Победитель: @{winner['username'] or winner_id}\n"
                f"🎁 Награда: +{total_win} токенов (x{game['players_needed']})!")
    else:
        text = "Игра завершена."
    if msg:
        safe_edit(msg.chat.id, msg.message_id, text, main_menu())
    else:
        safe_send(chat_id, text, main_menu())

# ═══════════════════════════════════════════════
# ОТМЕНА ИГРЫ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_"))
def cancel_game(call):
    game_id = call.data.replace("cancel_", "")
    game = db["games"].get(game_id)
    if not game or game["status"] != "lobby": return safe_answer(call, "❌ Игра уже неактивна.", show_alert=True)
    if str(call.from_user.id) != game["creator"]: return safe_answer(call, "❌ Только владелец может отменить.", show_alert=True)
    game["status"] = "cancelled"
    save_db(db)
    safe_answer(call, "❌ Игра отменена.")
    safe_edit(call.message.chat.id, call.message.message_id, "❌ Игра отменена.", main_menu())

# ═══════════════════════════════════════════════
# МИНИ-ИГРЫ
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "mini_games_menu")
def mini_games_menu_cb(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🥃 Напёрстки (+50)", callback_data="mg_cups"),
        InlineKeyboardButton("🎲 Кубик (+50)", callback_data="mg_dice"),
        InlineKeyboardButton("🪙 Монетка (x2)", callback_data="mg_coin"),
        InlineKeyboardButton("🎁 Бонус: Снятие минуса (раз в день)", callback_data="mg_minus"),
        InlineKeyboardButton("⬅️ Назад", callback_data="refresh")
    )
    safe_edit(call.message.chat.id, call.message.message_id, "🎮 МИНИ-ИГРЫ\nВыбери игру:", kb)

@bot.callback_query_handler(func=lambda c: c.data == "mg_cups")
def mg_cups(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("🥃 1", callback_data="cup_1"),
        InlineKeyboardButton("🥃 2", callback_data="cup_2"),
        InlineKeyboardButton("🥃 3", callback_data="cup_3")
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="mini_games_menu"))
    safe_edit(call.message.chat.id, call.message.message_id, "🥃 Угадай, где шарик (+50):", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cup_"))
def cup_choice(call):
    safe_answer(call, "Крутим...")
    user = get_user(call.from_user.id)
    choice = int(call.data.replace("cup_", ""))
    msg = safe_send(call.message.chat.id, "🥃 Перемешиваем...")
    if not msg: return
    time.sleep(0.5)
    safe_edit(msg.chat.id, msg.message_id, "🔀 🔀 🔀")
    time.sleep(0.5)
    correct = random.randint(1, 3)
    if choice == correct:
        user["balance"] += 50
        txt = f"🎉 Угадал! +50 токенов.\n💵 Баланс: {user['balance']}"
    else:
        txt = f"😢 Не угадал. Шарик был под {correct}."
    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, txt, main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "mg_dice")
def mg_dice(call):
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🎲 Бросаем кубик...", None)
    time.sleep(0.5)
    user = get_user(call.from_user.id)
    r = random.randint(1, 6)
    if r >= 4:
        user["balance"] += 50
        txt = f"🎲 Выпало: {r}. Победа! +50 токенов.\n💵 Баланс: {user['balance']}"
    else:
        txt = f"🎲 Выпало: {r}. Не повезло."
    save_db(db)
    safe_edit(call.message.chat.id, call.message.message_id, txt, main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "mg_coin")
def mg_coin(call):
    safe_answer(call)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🪙 Орел", callback_data="coin_heads"),
        InlineKeyboardButton("🪙 Решка", callback_data="coin_tails")
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="mini_games_menu"))
    safe_edit(call.message.chat.id, call.message.message_id, "🪙 Орел или решка?", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("coin_"))
def coin_flip(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    choice = call.data.replace("coin_", "")
    msg = safe_send(call.message.chat.id, "🪙 Подбрасываем...")
    if not msg: return
    time.sleep(1)
    result = random.choice(["heads", "tails"])
    if choice == result:
        user["balance"] *= 2
        txt = f"🪙 {result.capitalize()}! Ты угадал. Баланс удвоен: {user['balance']}"
    else:
        txt = f"🪙 {result.capitalize()}! Не угадал."
    save_db(db)
    safe_edit(msg.chat.id, msg.message_id, txt, main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "mg_minus")
def mg_minus(call):
    safe_answer(call)
    user = get_user(call.from_user.id)
    now = int(time.time())
    if now - user.get("last_minus_bonus", 0) < 86400:
        left = 86400 - (now - user["last_minus_bonus"])
        return safe_answer(call, f"⏳ Бонус через {left//3600}ч {(left%3600)//60}м", show_alert=True)
    if user["balance"] >= 0:
        return safe_answer(call, "❌ Бонус доступен только при минусовом балансе!", show_alert=True)
    user["balance"] = 0
    user["last_minus_bonus"] = now
    save_db(db)
    safe_edit(call.message.chat.id, call.message.message_id, "🎁 Минус снят! Твой баланс теперь 0.", main_menu())

# ═══════════════════════════════════════════════
# ПРОЧЕЕ (ABOUT, ПРОМОКОДЫ, ТОП, ПРОФИЛЬ)
# ═══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "about")
def about(call):
    safe_answer(call)
    txt = ("📖 МЕХАНИКИ\n\n🔫 **Рулетка:**\nУ каждого 3 жизни. Выбирай: выстрелить в себя (-0.5) или в другого (-1). Шанс пули 1/6.\n\n💵 **Ставки:**\nСписываются только с проигравших.")
    safe_edit(call.message.chat.id, call.message.message_id, txt, back_kb())

@bot.callback_query_handler(func=lambda c: c.data == "secret_code")
def secret_code(call):
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🔐 Введи код:", back_kb())
    bot.register_next_step_handler(call.message, process_promo)

def process_promo(message):
    if message.text.startswith("/"): return
    code = message.text.strip().upper()
    user = get_user(message.from_user.id)
    
    if code not in db["promos"]: return safe_send(message.chat.id, "❌ Неверный код.", main_menu())
    if code in user.get("used_promos", []): return safe_send(message.chat.id, "❌ Уже активирован.", main_menu())
    
    promo = db["promos"][code]
    if promo["type"] == "tokens":
        user["balance"] += promo["amount"]
        reward_text = f"+{promo['amount']} токенов"
    elif promo["type"] == "item":
        item = promo["item"]
        user["inventory"][item] += promo["amount"]
        names = {"xray": "Рентген", "pill": "Таблетка", "angel": "Зелье ангела"}
        reward_text = f"+{promo['amount']} шт. {names[item]}"
        
    user.setdefault("used_promos", []).append(code)
    save_db(db)
    safe_send(message.chat.id, f"✅ Активирован! Награда: {reward_text}\n💵 Баланс: {user['balance']}", main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "top_menu")
def top_menu_cb(call):
    safe_answer(call)
    safe_edit(call.message.chat.id, call.message.message_id, "🏆 ТОП", top_menu())

@bot.callback_query_handler(func=lambda c: c.data in ("top_tokens", "top_wins"))
def show_top(call):
    safe_answer(call)
    sort_by = "balance" if call.data == "top_tokens" else "wins"
    all_users = list(db["users"].items())
    all_users.sort(key=lambda x: x[1].get(sort_by, 0), reverse=True)
    lines = [f"🏆 ТОП ПО {'ТОКЕНАМ' if sort_by=='balance' else 'ПОБЕДАМ'}:\n"]
    for i, (uid, info) in enumerate(all_users[:10], 1):
        lines.append(f"{i}. {info.get('username') or uid} — {info.get(sort_by, 0)}")
    safe_edit(call.message.chat.id, call.message.message_id, "\n".join(lines), top_menu())

@bot.callback_query_handler(func=lambda c: c.data == "profile")
def profile(call):
    safe_answer(call)
    u = get_user(call.from_user.id)
    txt = (f"👤 ПРОФИЛЬ\n🆔 `{call.from_user.id}`\n💵 {u['balance']}\n"
           f"🏆 {u['wins']}\n💀 {u['deaths']}\n\n"
           f"🎒 Инвентарь: 👓 {u['inventory']['xray']} | 💊 {u['inventory']['pill']} | 👼 {u['inventory']['angel']}")
    safe_edit(call.message.chat.id, call.message.message_id, txt, back_kb())

@bot.callback_query_handler(func=lambda c: c.data == "refresh")
def refresh(call):
    safe_answer(call)
    text = ("Привет! Я игровой бот Roulette! 👋\n\nДобавь меня в чат, "
            "и посмотрим, кто из нас останется в живых 😈")
    safe_edit(call.message.chat.id, call.message.message_id, text, main_menu())

# ═══════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    print("🚀 ROULETTE BOT запущен...")
    update_shop_stock()
    bot.infinity_polling()
