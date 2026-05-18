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

# Получаем токен из переменных окружения Render
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("Ошибка: Переменная окружения BOT_TOKEN не задана!", file=sys.stderr)
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# --- ВОЗВРАЩАЕМ ВАШЕ ОРИГИНАЛЬНОЕ ПРИВЕТСТВИЕ И КНОПКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    # Создаем клавиатуру с кнопками
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_create = telebot.types.KeyboardButton("➕ Создать новый сбор")
    btn_support = telebot.types.KeyboardButton("ℹ️ Поддержка")
    markup.add(btn_create, btn_support)
    
    # Ваш точный текст приветствия
    welcome_text = (
        "🍕 Привет! Я ИИ-помощник для совместных покупок.\n\n"
        "Здесь ты можешь удобно разделить чек с друзьями на пиццу или бургеры, "
        "а ИИ проследит за должниками!\n\n"
        "Выберите действие ниже 👇"
    )
    
    # Отправляем сообщение с кнопками
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

# Обработка нажатия на кнопку "Создать новый сбор"
@bot.message_handler(func=lambda message: message.text == "➕ Создать новый сбор")
def create_pool(message):
    bot.send_message(message.chat.id, "Запуск процесса создания нового сбора... (сюда можно подключить ваше Web App)")

# Обработка нажатия на кнопку "Поддержка"
@bot.message_handler(func=lambda message: message.text == "ℹ️ Поддержка")
def support_info(message):
    bot.send_message(message.chat.id, "Если у вас возникли вопросы, свяжитесь с администратором бота.")
# --------------------------------------------------------

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
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
    
    if "hash" not in parsed_data:
        return False
        
    received_hash = parsed_data.pop("hash")
    
    data_list = []
    for key, values in sorted(parsed_data.items()):
        data_list.append(f"{key}={values}")
    data_check_string = "\n".join(data_list)
    
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(computed_hash, received_hash)

# Запуск веб-сервера для прохождения портов Render
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



