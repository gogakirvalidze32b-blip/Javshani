import telebot
from telebot import types
import time
import json
import os

TOKEN = "8043569123:AAHv3MCItdKS2x7qj24wI3wUyuKlPynLvsg"
ADMIN_ID = 8330284515
TARGET_USER_ID = 8330284515
AUTOBOOK_FILE = "autobook.json"
FILE_NAME = "users.json"
bot = telebot.TeleBot(TOKEN)

def send_msg(chat_id, text, markup=None):
    try:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        time.sleep(2)
    except Exception as e:
        print(f"შეცდომა გაგზავნისას: {e}")

def test_startbot():
    print("🚀 /startbot ტესტი დაიწყო")

    data = {}
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, 'r', encoding='utf-8') as f:
            data = json.load(f)

    autobook_config = {}
    if os.path.exists(AUTOBOOK_FILE):
        with open(AUTOBOOK_FILE, 'r', encoding='utf-8') as f:
            autobook_config = json.load(f)

    target_user_id = str(autobook_config.get("target_user_id", ""))

    for chat_id, cities in data.items():
        if not cities:
            continue

        cities_fmt = "\n".join(f"  • <code>{c}</code>" for c in cities)

        if chat_id == target_user_id and autobook_config.get("enabled"):
            msg = (
                "🤖 <b>ავტომატური ჯავშნის ძიება დაიწყო!</b>\n"
                "────────────────────\n\n"
                f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
                "────────────────────\n\n"
                "🔔 <b>ადგილის გამოჩენისთანავე ავტომატურად დაგიჭერთ!</b>"
            )
        else:
            msg = (
                "⏳ <b>ძიება დაიწყო!</b>\n"
                "────────────────────\n\n"
                f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
                "────────────────────\n\n"
                "🔔 <b>ადგილის გამოჩენისთანავე შეგატყობინებთ!</b>"
            )

        send_msg(chat_id, msg)

    print("✅ /startbot ტესტი დასრულდა!")

def test_autobook():
    print("🚀 autobook ტესტი დაიწყო")

    link_kb = types.InlineKeyboardMarkup()
    link_kb.add(types.InlineKeyboardButton("🚀 სასწრაფოდ დაჯავშნა", url="https://my.sa.gov.ge"))

    send_msg(TARGET_USER_ID,
        "🔔 <b>ყურადღება! ჯავშანი გაიხსნა</b>\n"
        "────────────────────\n\n"
        "🏛 <b>ქალაქი:</b> <code>საჩხერე</code>\n"
        "📅 <b>თარიღი:</b> <code>1 აპრილი, ოთხშაბათი</code>\n\n"
        "────────────────────\n"
        "🕒 <b>თავისუფალი საათები:</b>\n"
        "<code>11:00, 12:30, 14:00</code>\n"
        "────────────────────\n\n"
        "⚡ <b>ბოტი იწყებს ავტომატურ დაჯავშნას...</b>",
        link_kb
    )

    send_msg(TARGET_USER_ID,
        "⏳ <b>მიმდინარეობს ავტომატური დაჯავშნა...</b>\n"
        "<i>გთხოვთ დაელოდოთ, სისტემა აგზავნის მოთხოვნას.</i>"
    )

    time.sleep(3)

    send_msg(TARGET_USER_ID,
        "✅ <b>წარმატებით დაიჯავშნა!</b>\n"
        "────────────────────\n\n"
        "🏛 <b>სერვის ცენტრი:</b> <code>საჩხერე</code>\n\n"
        "📅 <b>თარიღი:</b> <code>1 აპრილი, ოთხშაბათი</code>\n\n"
        "⏰ <b>დრო:</b> <code>11:00</code>\n\n"
        "────────────────────\n\n"
        "📱 <b>გთხოვთ გადაამოწმოთ ტელეფონზე მოსული SMS შეტყობინება</b>\n\n"
        "მასში მოცემულია თქვენი ჯავშნის კოდი და დეტალები.\n\n"
        "────────────────────\n\n"
        "📌 გამოცდაზე გამოცხადდით <b>15 წუთით ადრე</b>\n"
        "და წარმოადგინეთ SMS კოდით მოსული შეტყობინება."
    )

    print("✅ autobook ტესტი დასრულდა!")

if __name__ == "__main__":      
    test_startbot()   # ← /start   
    test_autobook()   # ← autobook