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
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"pools": {}, "user_states": {}, "next_pool_id": 1}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def generate_invite_link(pool_id):
    """Генерирует ссылку-приглашение для сбора"""
    bot_username = bot.get_me().username
    return f"https://t.me/{bot_username}?start=join_pool_{pool_id}"

def join_pool_by_invite(message, pool_id):
    """Обрабатывает присоединение к сбору по ссылке"""
    db = load_db()
    pool = db["pools"].get(str(pool_id))
    
    if not pool:
        bot.send_message(message.chat.id, "❌ Такой сбор уже не существует или был удален!")
        return
    
    # Проверяем, не участвует ли уже пользователь
    if str(message.chat.id) in pool["participants"]:
        bot.send_message(message.chat.id, f"✅ Вы уже участвуете в сборе №{pool_id}!")
        send_pool_card(message.chat.id, pool_id)
        return
    
    # Добавляем пользователя в сбор
    username = message.from_user.username
    mention = f"@{username}" if username else message.from_user.first_name
    
    pool["participants"][str(message.chat.id)] = {
        "name": mention, 
        "paid": 0, 
        "status": "Не сдал"
    }
    save_db(db)
    
    # Отправляем подтверждение
    bot.send_message(
        message.chat.id, 
        f"🎉 Вы успешно присоединились к сбору №{pool_id}!\n\n"
        f"Создатель сбора: {pool['participants'][str(pool['creator'])]['name']}\n"
        f"Общая сумма: {pool['total']} руб."
    )
    
    # Показываем карточку сбора
    send_pool_card(message.chat.id, pool_id)
    
    # Уведомляем создателя сбора
    try:
        bot.send_message(
            pool["creator"],
            f"👤 Новый участник присоединился к сбору №{pool_id}!\n"
            f"Имя: {mention}\n"
            f"Теперь в сборе {len(pool['participants'])} человек(а)"
        )
    except Exception:
        pass

@bot.message_handler(commands=['start'])
def start(message):
    # Проверяем, есть ли параметр (приглашение в сбор)
    command_parts = message.text.split()
    if len(command_parts) > 1:
        param = command_parts[1]
        if param.startswith("join_pool_"):
            # Пользователь перешел по ссылке-приглашению
            pool_id = param.replace("join_pool_", "")
            join_pool_by_invite(message, pool_id)
            return
    
    # Обычный запуск (без приглашения)
    db = load_db()
    db["user_states"][str(message.chat.id)] = "MAIN_MENU"
    save_db(db)
    
    # Создаем инлайн-кнопки
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_create = types.InlineKeyboardButton("➕ Создать новый сбор", callback_data="btn_ask_total")
    btn_support = types.InlineKeyboardButton("🧑‍💻 Тех. поддержка", callback_data="btn_get_support")
    markup.add(btn_create, btn_support)
    
    welcome_text = (
        "🍕 Привет! Я ИИ-помощник для совместных покупок.\n\n"
        "Здесь ты можешь удобно разделить чек с друзьями на пиццу или бургеры, "
        "а ИИ проследит за должниками!\n\n"
        "Выберите действие ниже 👇"
    )
    
    # Удаляем старую клавиатуру
    remove_markup = types.ReplyKeyboardRemove()
    temp_msg = bot.send_message(message.chat.id, "Загрузка...", reply_markup=remove_markup)
    bot.delete_message(message.chat.id, temp_msg.message_id)
    
    # Отправляем приветственное сообщение
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

# Функция запуска сбора
def start_asking_amount(chat_id):
    db = load_db()
    db["user_states"][str(chat_id)] = "WAITING_FOR_TOTAL"
    save_db(db)
    bot.send_message(chat_id, "Введите общую сумму сбора (например, 1500):")

# Отлавливает случайный текст в главном меню
@bot.message_handler(func=lambda message: load_db().get("user_states", {}).get(str(message.chat.id)) == "MAIN_MENU")
def default_menu_handler(message):
    bot.send_message(
        message.chat.id, 
        "Пожалуйста, используйте синие инлайн-кнопки под сообщением выше 👆 для управления сборами."
    )

# Обработка ввода суммы
@bot.message_handler(func=lambda message: load_db().get("user_states", {}).get(str(message.chat.id)) == "WAITING_FOR_TOTAL")
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
    btn_invite = types.InlineKeyboardButton("🔗 Пригласить друга", callback_data=f"invite_{pool_id}")
    btn_home = types.InlineKeyboardButton("⬅️ На главную", callback_data="home")
    
    markup.add(btn_join, btn_paid)
    markup.add(btn_invite)
    markup.add(btn_remind)
    markup.add(btn_home)
    
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    db = load_db()
    data = call.data
    chat_id = call.message.chat.id
    
    if data == "btn_ask_total":
        bot.answer_callback_query(call.id)
        start_asking_amount(chat_id)
        
    elif data == "btn_get_support":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "По всем вопросам и предложениям пишите разработчику: @eFpshik")
    
    elif data.startswith("invite_"):
        pool_id = data.split("_")[1]
        pool = db["pools"].get(pool_id)
        
        if pool:
            invite_link = generate_invite_link(pool_id)
            
            # Создаем кнопки для ссылки
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_share = types.InlineKeyboardButton(
                "📤 Поделиться ссылкой", 
                url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к совместному сбору денег!"
            )
            btn_copy = types.InlineKeyboardButton(
                "📋 Скопировать ссылку", 
                callback_data=f"copy_link_{pool_id}"
            )
            markup.add(btn_share, btn_copy)
            
            bot.send_message(
                chat_id, 
                f"🔗 **Ссылка для приглашения в сбор №{pool_id}:**\n\n"
                f"`{invite_link}`\n\n"
                f"📌 Отправьте эту ссылку другу — он сможет присоединиться к сбору, нажав «Start» или перейдя по ссылке!\n\n"
                f"💡 *Совет:* Можно также нажать «Поделиться» и выбрать любой мессенджер.",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "Сбор не найден!")
    
    elif data.startswith("copy_link_"):
        pool_id = data.split("_")[2]
        invite_link = generate_invite_link(pool_id)
        
        # Пытаемся скопировать через всплывающее окно (только для Telegram Desktop)
        bot.answer_callback_query(
            call.id, 
            f"Ссылка скопирована: {invite_link}", 
            show_alert=False
        )
        
        # Дополнительно отправляем ссылку отдельным сообщением для копирования
        bot.send_message(
            chat_id,
            f"🔗 Ваша ссылка:\n`{invite_link}`\n\nНажмите на неё и выберите «Копировать»",
            parse_mode="Markdown"
        )
        
    elif data.startswith("join_"):
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
        else:
            bot.answer_callback_query(call.id, "Сбор не найден!")
            
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
        else:
            bot.answer_callback_query(call.id, "Сбор не найден!")
                
    elif data.startswith("remind_"):
        pool_id = data.split("_")[1]
        pool = db["pools"].get(pool_id)
        if pool:
            if pool["creator"] == chat_id:
                bot.answer_callback_query(call.id, "ИИ-напоминания отправлены должникам!")
                for p_id, p_info in pool["participants"].items():
                    if p_info["status"] != "В расчете!" and int(p_id) != chat_id:
                        try:
                            per_person = round(pool["total"] / len(pool["participants"]), 2)
                            bot.send_message(int(p_id), f"🤖 ИИ напоминает: Пора скинуть деньги на сбор №{pool_id}! С вас {per_person} руб.")
                        except Exception:
                            pass
            else:
                bot.answer_callback_query(call.id, "Только создатель сбора может отправлять напоминания!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Сбор не найден!")
                
    elif data == "home":
        bot.answer_callback_query(call.id)
        # Создаем имитацию сообщения для функции start
        class MockMessage:
            def __init__(self, chat_id):
                self.chat = type('obj', (object,), {'id': chat_id})()
                self.text = "/start"
        start(MockMessage(chat_id))

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
    
    # Убираем вебхук на всякий случай
    bot.remove_webhook()
    
    print("Бот запущен и готов к работе!")
    print(f"Имя бота: @{bot.get_me().username}")
    bot.infinity_polling()