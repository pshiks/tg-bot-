import telebot
from telebot import types
import random
import requests
import html
import sqlite3
import json

TOKEN = "8624371307:AAFo2rHtkMngWtBz-gCxVBB-_gZW23voPhw"
bot = telebot.TeleBot(TOKEN)

# 🛠 ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (Путь изменен обратно на локальный для бесплатного тарифа)
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
    
    if not parts:
        return f"🆔 <b>Сбор №{bill_id}</b>\n💰 Общая сумма: {total} руб.\n\n🤷‍♂️ В доле пока никого нет.\nСкопируйте и перешлите друзьям ссылку из сообщения ниже!"
    
    cost_per_person = round(total / len(parts), 1)
    text = f"🆔 <b>Сбор №{bill_id}</b>\n💰 Общая сумма: {total} руб.\n"
    text += f"👥 Участников: {len(parts)} чел. | С каждого: {cost_per_person} руб.\n\n"
    text += "📊 <b>Статус оплаты:</b>\n"
    
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

print("ИИ-Бот для сервера готов...")
bot.infinity_polling()
