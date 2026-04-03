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

def format_slots(times, prices):
    if not times:
        return "<code>არ არის თავისუფალი საათი</code>"

    if prices:
        times_with_prices = [f"{t} ({prices.get(t, 'არ არის ფასი')} ლარი)" for t in times]
        return "<code>" + ", ".join(times_with_prices) + "</code>"

    return "<code>" + ", ".join(times) + "</code>"


def test_autobook():
    print("🚀 autobook ტესტი დაიწყო")

    autos = {}
    if os.path.exists(AUTOBOOK_FILE):
        with open(AUTOBOOK_FILE, 'r', encoding='utf-8') as f:
            autos = json.load(f)

    target_city = autos.get("target_cities", ["საჩხერე"])[0] if autos.get("target_cities") else "საჩხერე"
    target_date = autos.get("target_dates", ["28-05-2026"])[0] if autos.get("target_dates") else "28-05-2026"
    target_hours = autos.get("target_hours", ["11:00", "12:00"]) if autos.get("target_hours") else ["11:00", "12:00"]

    # მაგალითი slots + უფასო ფასი ფურის გარშემო (თუ არ არის კონკრეტული data)
    slots = ["11:00", "12:00", "12:30", "14:00"]
    prices_for_slots = {"11:00": "90", "12:00": "250", "12:30": "250", "14:00": "90"}

    message = (
        "🔔 <b>ტესტი: ჯავშანი გაიხსნა</b>\n"
        "────────────────────\n\n"
        f"🏛 <b>ქალაქი:</b> <code>{target_city}</code>\n"
        f"📅 <b>თარიღი:</b> <code>{target_date}</code>\n\n"
        "────────────────────\n"
        "🕒 <b>თავისუფალი საათები:</b>\n"
        f"{format_slots(slots, prices_for_slots)}\n"
        "────────────────────\n\n"
        "⚡ <b>ბოტი სცდება ავტომატურ დაჯავშნას (test mode).</b>\n"
        "🔎 ეს შეტყობინება მიდის ADMIN-ზე და მომხმარებლებზე (users.json)\n"
        "💡 ფილტრები: target_prices=" + str(autos.get('target_prices', [])) + ", target_dates=" + str(autos.get('target_dates', [])) + ", target_hours=" + str(autos.get('target_hours', []))
    )

    link_kb = types.InlineKeyboardMarkup()
    link_kb.add(types.InlineKeyboardButton("🚀 სასწრაფოდ დაჯავშნა", url="https://my.sa.gov.ge"))

    send_msg(TARGET_USER_ID, message, link_kb)

    send_msg(TARGET_USER_ID,
        "⏳ <b>მიმდინარეობს ავტომატური დაჯავშნა...</b>\n"
        "<i>გთხოვთ დაელოდოთ, სისტემა აგზავნის მოთხოვნას.</i>"
    )

    time.sleep(3)

    send_msg(TARGET_USER_ID,
        "✅ <b>წარმატებით დაიჯავშნა!</b>\n"
        "────────────────────\n\n"
        f"🏛 <b>ქალაქი:</b> <code>{target_city}</code>\n\n"
        f"📅 <b>თარიღი:</b> <code>{target_date}</code>\n\n"
        f"⏰ <b>დრო:</b> <code>{target_hours[0] if target_hours else '11:00'}</code>\n\n"
        "────────────────────\n\n"
        "📱 <b>გთხოვთ გადაამოწმოთ ტელეფონზე მოსული SMS შეტყობინება</b>\n\n"
        "მასში მოცემულია თქვენი ჯავშნის კოდი და დეტალები.\n\n"
        "────────────────────\n\n"
        "📌 გამოცდაზე გამოცხადდით <b>15 წუთით ადრე</b>\n"
        "და წარმოადგინეთ SMS კოდით მოსული შეტყობინება."
    )

    print("✅ autobook ტესტი დასრულდა!")

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