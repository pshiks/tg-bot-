import os
import sys
import json
import telebot
from telebot import types
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("Ошибка: Переменная окружения BOT_TOKEN не задана!", file=sys.stderr)
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

DB_FILE = 'database.json'

def load_db():
    if not os.path.exists(DB_FILE):
        return {"pools": {}, "user_states": {}, "next_pool_id": 1}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

@bot.message_handler(commands=['start'])
def start(message):
    db = load_db()
    db["user_states"][str(message.chat.id)] = "MAIN_MENU"
    save_db(db)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_create = types.KeyboardButton("➕ Создать новый сбор")
    btn_support = types.KeyboardButton("🧑‍💻 Тех. поддержка")
    markup.add(btn_create, btn_support)
    
    welcome_text = (
        "🍕 Привет! Я ИИ-помощник для совместных покупок.\n\n"
        "Здесь ты можешь удобно разделить чек с друзьями на пиццу или бургеры, "
        "а ИИ проследит за должниками!\n\n"
        "Выберите действие ниже 👇"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "➕ Создать новый сбор")
def ask_total_amount(message):
    db = load_db()
    db["user_states"][str(message.chat.id)] = "WAITING_FOR_TOTAL"
    save_db(db)
    bot.send_message(message.chat.id, "Введите общую сумму сбора (например, 1500):")

@bot.message_handler(func=lambda message: load_db()["user_states"].get(str(message.chat.id)) == "WAITING_FOR_TOTAL")
def process_total_amount(message):
    try:
        total = float(message.text)
        if total <= 0:
            bot.send_message(message.chat.id, "Сумма должна быть больше нуля. Попробуйте еще раз:")
            return
        
        db = load_db()
        pool_id = db["next_pool_id"]
        db["next_pool_id"] += 1
        
        username = message.from_user.username
        mention = f"@{username}" if username else message.from_user.first_name
        
        db["pools"][str(pool_id)] = {
            "creator": message.chat.id,
            "total": total,
            "participants": {str(message.chat.id): {"name": mention, "paid": 0, "status": "Не сдал"}}
        }
        db["user_states"][str(message.chat.id)] = "MAIN_MENU"
        save_db(db)
        
        send_pool_card(message.chat.id, pool_id)
        
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное число:")

def send_pool_card(chat_id, pool_id):
    db = load_db()
    pool = db["pools"].get(str(pool_id))
    if not pool:
        return
    
    total = pool["total"]
    parts = pool["participants"]
    count = len(parts)
    per_person = round(total / count, 2) if count > 0 else total
    
    text = f"🆔 **Сбор №{pool_id}**\n"
    text += f"💰 Общая сумма: {total} руб.\n"
    text += f"👥 Участников: {count} чел. | С каждого: {per_person} руб.\n\n"
    text += "📊 Статус оплаты:\n"
    
    for p_id, p_info in parts.items():
        status_emoji = "🟢" if p_info["status"] == "В расчете!" else "🔴"
        text += f"{status_emoji} {p_info['name']} — {p_info['status']} ({p_info['paid']}₽)\n"
        
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_join = types.InlineKeyboardButton("🤠 Я в деле!", callback_data=f"join_{pool_id}")
    btn_paid = types.InlineKeyboardButton("💰 Я скинул", callback_data=f"paid_{pool_id}")
    btn_remind = types.InlineKeyboardButton("🧠 ИИ-напоминание", callback_data=f"remind_{pool_id}")
    btn_home = types.InlineKeyboardButton("⬅️ На главную", callback_data="home")
    
    markup.add(btn_join, btn_paid)
    markup.add(btn_remind)
    markup.add(btn_home)
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    db = load_db()
    data = call.data
    chat_id = call.message.chat.id
    
    if data.startswith("join_"):
        pool_id = data.split("_")[1]
        pool = db["pools"].get(pool_id)
        if pool:
            username = call.from_user.username
            mention = f"@{username}" if username else call.from_user.first_name
            if str(chat_id) not in pool["participants"]:
                pool["participants"][str(chat_id)] = {"name": mention, "paid": 0, "status": "Не сдал"}
                save_db(db)
                bot.answer_callback_query(call.id, "Вы успешно добавлены в сбор!")
                send_pool_card(chat_id, pool_id)
            else:
                bot.answer_callback_query(call.id, "Вы уже участвуете в этом сборе.")
                
    elif data.startswith("paid_"):
        pool_id = data.split("_")[1]
        pool = db["pools"].get(pool_id)
        if pool:
            parts = pool["participants"]
            if str(chat_id) in parts:
                count = len(parts)
                per_person = round(pool["total"] / count, 2)
                parts[str(chat_id)]["paid"] = per_person
                parts[str(chat_id)]["status"] = "В расчете!"
                save_db(db)
                bot.answer_callback_query(call.id, "Статус обновлен!")
                send_pool_card(chat_id, pool_id)
            else:
                bot.answer_callback_query(call.id, "Сначала нажмите кнопку 'Я в деле!'", show_alert=True)
                
    elif data.startswith("remind_"):
        pool_id = data.split("_")[1]
        pool = db["pools"].get(pool_id)
        if pool:
            if pool["creator"] == chat_id:
                bot.answer_callback_query(call.id, "ИИ-напоминания отправлены должникам!")
                for p_id, p_info in pool["participants"].items():
                    if p_info["status"] != "В расчете!" and int(p_id) != chat_id:
                        try:
                            bot.send_message(int(p_id), f"🤖 ИИ напоминает: Пора скинуть деньги на сбор №{pool_id}! С вас {round(pool['total']/len(pool['participants']), 2)} руб.")
                        except Exception:
                            pass
            else:
                bot.answer_callback_query(call.id, "Только создатель сбора может отправлять напоминания!", show_alert=True)
                
    elif data == "home":
        bot.answer_callback_query(call.id)
        start(call.message)

@bot.message_handler(func=lambda message: message.text == "🧑‍💻 Тех. поддержка")
def support(message):
    bot.send_message(message.chat.id, "По всем вопросам и предложениям пишите разработчику: @pshiks")

if __name__ == "__main__":
    from threading import Thread
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")

    def run_server():
        port = int(os.environ.get("PORT", 8000))
        server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
        server.serve_forever()

    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    bot.infinity_polling()
