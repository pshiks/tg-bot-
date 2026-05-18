
from telebot import types
import random
import requests
import html
import sqlite3
import base64
import hashlib
import hmac
import json
import os
import sys
import telebot
from dotenv import load_dotenv

# Загружаем переменные из файла .env (если он есть локально)
load_dotenv()

# Получаем токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")

# Проверка, что токен был успешно передан в программу
if not TOKEN:
    print("Ошибка: Переменная окружения BOT_TOKEN не задана!", file=sys.stderr)
    sys.exit(1)

TOKEN = "8624371307:AAFo2rHtkMngWtBz-gCxVBB-_gZW23voPhw"
bot = telebot.TeleBot(TOKEN)

# 🛠 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
def init_db():
    conn = sqlite3.connect("pizza_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            bill_id INTEGER PRIMARY KEY,
            total_cost INTEGER,
            creator_id INTEGER,
            participants TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_bill(bill_id, total_cost, creator_id, participants):
    conn = sqlite3.connect("pizza_bot.db")
    cursor = conn.cursor()
    parts_json = json.dumps(participants)
    cursor.execute(
        "INSERT OR REPLACE INTO bills (bill_id, total_cost, creator_id, participants) VALUES (?, ?, ?, ?)",
        (bill_id, total_cost, creator_id, parts_json)
    )
    conn.commit()
    conn.close()

def load_all_bills():
    conn = sqlite3.connect("pizza_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT bill_id, total_cost, creator_id, participants FROM bills")
    rows = cursor.fetchall()
    conn.close()
    
    bills_dict = {}
    for row in rows:
        try:
            loaded_parts = json.loads(row)
            fixed_parts = {int(k): v for k, v in loaded_parts.items()}
            bills_dict[row] = {
                "total_cost": row,
                "creator_id": row,
                "participants": fixed_parts
            }
        except Exception:
            pass
    return bills_dict

init_db()
bills = load_all_bills()

BACKUP_MEMES = [
    "🤖 Эй, {}! Мои ИИ-датчики фиксируют долг в {}₽. Пора платить!",
    "💸 {}, пицца уже переварилась, а {}₽ всё еще не долетели. Поторопись!",
    "🕵️‍♂️ Спецагенты уже выехали за долгом в {}₽ для {}!"
]

def generate_ai_meme(username, balance):
    prompt = f"Напиши ОДНО ОЧЕНЬ КОРОТКОЕ (1 sentence), саркастичное или мемное напоминание для пользователя {username}, который задолжал {balance} рублей за пиццу."
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Отправь мне JSON-строку от Telegram Web App для проверки.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        response = requests.post(
            "https://pollinations.ai", 
            json={"prompt": prompt, "textonly": True}, 
            timeout=4
        )
        if response.status_code == 200 and len(response.text.strip()) > 5:
            return response.text.strip()
    except Exception:
        pass
    return random.choice(BACKUP_MEMES).format(username, balance)

def get_main_inline_menu():
    markup = types.InlineKeyboardMarkup()
    btn_create = types.InlineKeyboardButton(text="➕ Создать новый сбор", callback_data="menu_create")
    
    # ИСПРАВЛЕНО: Ссылка теперь ведет строго на ваш аккаунт
    support_url = "https://t.me"
    btn_support = types.InlineKeyboardButton(text="👨‍💻 Тех. поддержка", url=support_url)
    
    markup.row(btn_create)
    markup.row(btn_support)
    return markup

def get_bill_inline_menu(bill_id):
    markup = types.InlineKeyboardMarkup()
    btn_join = types.InlineKeyboardButton(text="🙋‍♂️ Я в деле!", callback_data=f"join_{bill_id}")
    btn_pay = types.InlineKeyboardButton(text="💰 Я скинул +100₽", callback_data=f"pay_{bill_id}")
    btn_remind = types.InlineKeyboardButton(text="🧠 ИИ-напоминание", callback_data=f"remind_{bill_id}")
    btn_to_main = types.InlineKeyboardButton(text="⬅️ На главную", callback_data="to_main")
    
    markup.row(btn_join, btn_pay)
    markup.row(btn_remind)
    markup.row(btn_to_main)
    return markup

def get_bill_status_text(bill_id):
    bill = bills[bill_id]
    total = bill["total_cost"]
    parts = bill["participants"]
        data = json.loads(message.text)
        init_data = data.get("initData")
        if not init_data:
            bot.send_message(message.chat.id, "Ошибка: Поле 'initData' не найдено в JSON.")
            return

        is_valid = verify_telegram_web_app_data(init_data, TOKEN)
        if is_valid:
            bot.send_message(message.chat.id, "✅ Данные валидны! Проверка успешно пройдена.")
        else:
            bot.send_message(message.chat.id, "❌ Данные невалидны! Ошибка проверки подписи.")
    except json.JSONDecodeError:
        bot.send_message(message.chat.id, "Ошибка: Отправленный текст не является валидным JSON.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла непредвиденная ошибка: {e}")

def verify_telegram_web_app_data(init_data_str: str, bot_token: str) -> bool:
    from urllib.parse import parse_qs
    parsed_data = parse_qs(init_data_str)

    if not parts:
        return f"🆔 <b>Сбор №{bill_id}</b>\n💰 Общая сумма: {total} руб.\n\n🤷‍♂️ В доле пока никого нет.\nСкопируйте и перешлите друзьям ссылку из сообщения ниже!"
    if "hash" not in parsed_data:
        return False
        
    received_hash = parsed_data.pop("hash")[0]

    cost_per_person = round(total / len(parts), 1)
    text = f"🆔 <b>Сбор №{bill_id}</b>\n💰 Общая сумма: {total} руб.\n"
    text += f"👥 Участников: {len(parts)} чел. | С каждого: {cost_per_person} руб.\n\n"
    text += "📊 <b>Статус оплаты:</b>\n"
    data_list = []
    for key, values in sorted(parsed_data.items()):
        data_list.append(f"{key}={values[0]}")
    data_check_string = "\n".join(data_list)

    for p_id, data in parts.items():
        balance = cost_per_person - data["paid"]
        safe_name = html.escape(data['name'])
        if balance <= 0:
            text += f"🟢 {safe_name} — Сдал {data['paid']}₽ (В расчете!)\n"
        else:
            text += f"🔴 {safe_name} — Сдал {data['paid']}₽ (Долг: {balance}₽)\n"
    return text

@bot.message_handler(commands=['start'])
def start_cmd(message):
    args = message.text.split()
    if len(args) > 1:
        potential_id = args
        if potential_id.isdigit():
            bill_id = int(potential_id)
            if bill_id in bills:
                bot.send_message(message.chat.id, f"👋 Вы перешли в сбор №{bill_id}!")
                bot.send_message(message.chat.id, get_bill_status_text(bill_id), parse_mode="HTML", reply_markup=get_bill_inline_menu(bill_id))
                return
            else:
                bot.send_message(message.chat.id, "❌ Сбор по этой ссылке не найден.")
                return

    bot.send_message(
        message.chat.id, 
        "🍕 <b>Привет! Я ИИ-помощник для совместных покупок.</b>\n\n"
        "Здесь ты можешь удобно разделить чек с друзьями на пиццу или бургеры, а ИИ проследит за должниками!\n\n"
        "Выберите действие ниже 👇", 
        parse_mode="HTML", 
        reply_markup=get_main_inline_menu()
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    name = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if call.data == "menu_create":
        msg = bot.send_message(call.message.chat.id, "Введите общую сумму сбора (например, 1500):")
        bot.register_next_step_handler(msg, process_pizza_cost)
    elif call.data == "to_main":
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                text="🍕 <b>Главное меню:</b>", 
                parse_mode="HTML", 
                reply_markup=get_main_inline_menu()
            )
        except Exception: pass
    elif "_" in call.data:
        action, bill_id_str = call.data.split("_")
        bill_id = int(bill_id_str)
        if bill_id not in bills: return
        
        if action == "join":
            if user_id not in bills[bill_id]["participants"]:
                bills[bill_id]["participants"][user_id] = {"name": name, "paid": 0}
                save_bill(bill_id, bills[bill_id]["total_cost"], bills[bill_id]["creator_id"], bills[bill_id]["participants"])
                try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_bill_status_text(bill_id), parse_mode="HTML", reply_markup=get_bill_inline_menu(bill_id))
                except Exception: pass
        elif action == "pay":
            if user_id in bills[bill_id]["participants"]:
                bills[bill_id]["participants"][user_id]["paid"] += 100
                save_bill(bill_id, bills[bill_id]["total_cost"], bills[bill_id]["creator_id"], bills[bill_id]["participants"])
                try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_bill_status_text(bill_id), parse_mode="HTML", reply_markup=get_bill_inline_menu(bill_id))
                except Exception: pass
        elif action == "remind":
            parts = bills[bill_id]["participants"]
            if not parts: return
            cost_per_person = bills[bill_id]["total_cost"] / len(parts)
            debtors = [(data["name"], round(cost_per_person - data["paid"], 1)) for p_id, data in parts.items() if (cost_per_person - data["paid"]) > 0]
            if not debtors: bot.send_message(call.message.chat.id, "🎉 Все скинулись!")
            else:
                lucky_debtor_name, debt_amount = random.choice(debtors)
                temp_msg = bot.send_message(call.message.chat.id, "🧠 ИИ придумывает подкол...")
                ai_joke = generate_ai_meme(lucky_debtor_name, debt_amount)
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=temp_msg.message_id, text=f"🤖 <b>ИИ-напоминание для должника:</b>\n\n{ai_joke}", parse_mode="HTML")

def process_pizza_cost(message):
    try:
        total_cost = int(message.text)
        bill_id = random.randint(100, 999)
        bills[bill_id] = {"total_cost": total_cost, "creator_id": message.from_user.id, "participants": {}}
        
        save_bill(bill_id, total_cost, message.from_user.id, {})
        
        bot_username = bot.get_me().username
        clean_link = f"https://t.me{bot_username}?start={bill_id}"
        
        bot.send_message(message.chat.id, get_bill_status_text(bill_id), parse_mode="HTML", reply_markup=get_bill_inline_menu(bill_id))
        
        bot.send_message(
            message.chat.id, 
            f"🔗 <b>Ссылка для чата с друзьями:</b>\n\n<code>{clean_link}</code>\n\n"
            f"Зажмите это сообщение, скопируйте и отправьте друзьям!"
        )
    except ValueError:
        msg = bot.send_message(message.chat.id, "❌ Нужно ввести число. Какая сумма?")
        bot.register_next_step_handler(msg, process_pizza_cost)

@bot.message_handler(func=lambda msg: msg.text.isdigit())
def handle_id_input(message):
    bill_id = int(message.text)
    if bill_id in bills:
        bot.send_message(message.chat.id, get_bill_status_text(bill_id), parse_mode="HTML", reply_markup=get_bill_inline_menu(bill_id))
    else:
        bot.send_message(message.chat.id, "Сбор с таким ID не найден.")

import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def run_dummy_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Фиктивный сервер запущен на порту {port}")
    server.serve_forever()
    return hmac.compare_digest(computed_hash, received_hash)

# Запуск фейкового HTTP-сервера для прохождения портов на хостинге (например, Render)
if __name__ == "__main__":
    # Запускаем веб-сервер в отдельном потоке, чтобы порадовать Render
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    # Запускаем бота
    print("ИИ-Бот для сервера обновлен...")
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
        print(f"Сервер запущен на порту {port}")
        server.serve_forever()

    # Запускаем веб-сервер в отдельном потоке
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()

    print("Бот запускается...")
    bot.infinity_polling()




