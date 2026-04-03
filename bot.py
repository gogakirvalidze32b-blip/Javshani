import telebot
from telebot import types
import json
import os
import time

TOKEN = "8043569123:AAHv3MCItdKS2x7qj24wI3wUyuKlPynLvsg"
ADMIN_ID = 8330284515
GROUP_ID = -1003768013258
COMMUNITY_LINK = "https://t.me/+-ENrv7S2bpM4YTMy"
FILE_NAME = "users.json"
AUTOBOOK_FILE = "autobook.json"
TOPICS_FILE = "topics.json"
NOTIFIED_FILE = "notified.json"
bot = telebot.TeleBot(TOKEN)

admin_broadcast_state = {}
search_enabled = True

CITIES_LIST = [
    "რუსთავი", "გორი", "ქუთაისი", "ბათუმი", "ფოთი",
    "თელავი", "ახალციხე", "ოზურგეთი", "ზუგდიდი", "საჩხერე", "ამბროლაური"
]

def load_data():
    if not os.path.exists(FILE_NAME):
        return {}
    try:
        with open(FILE_NAME, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(FILE_NAME, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_topics():
    if not os.path.exists(TOPICS_FILE):
        return {}
    try:
        with open(TOPICS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_topics(data):
    with open(TOPICS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_or_create_topic(chat_id, name):
    topics = load_topics()
    if str(chat_id) in topics:
        return topics[str(chat_id)]
    try:
        result = bot.create_forum_topic(GROUP_ID, name)
        topic_id = result.message_thread_id
        topics[str(chat_id)] = topic_id
        save_topics(topics)
        return topic_id
    except Exception as e:
        print(f"Topic შექმნის შეცდომა: {e}")
        return None

def get_keyboard(user_cities):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btns = []
    for city in CITIES_LIST:
        status = " ✅" if city in user_cities else ""
        btns.append(types.InlineKeyboardButton(
            text=f"{city}{status}",
            callback_data=f"toggle:{city}"
        ))
    markup.add(*btns)
    all_selected = all(c in user_cities for c in CITIES_LIST)
    markup.add(types.InlineKeyboardButton(
        text="❌ ყველას მოხსნა" if all_selected else "⭐ ყველას მონიშვნა",
        callback_data="select_all"
    ))
    markup.add(types.InlineKeyboardButton(
        text="💾 არჩევანის შენახვა",
        callback_data="save_settings"
    ))
    return markup

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start_chat
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['start_chat'])
def start_chat(message):
    if message.chat.type != "private":
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        text="🗣 შემოგვიერთდი საკომუნიკაციო ჩათში",
        callback_data="join_community"
    ))
    bot.send_message(
        message.chat.id,
        "👥 <b>საკომუნიკაციო ჩათი</b>\n\n"
        "შემოგვიერთდი ჩვენს ჯგუფში სადაც შეგიძლია სხვა მომხმარებლებთან დაკავშირება და გამოცდილების გაზიარება 👇",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "join_community")
def join_community(call):
    chat_id = call.message.chat.id
    # ვაგზავნით ლინკს პირად შეტყობინებაში
    bot.send_message(
        chat_id,
        f"👉 {COMMUNITY_LINK}",
    )
    # ვცვლით ღილაკიან შეტყობინებას
    bot.edit_message_text(
        "🗣 <b>კეთილი იყოს თქვენი მობრძანება საკომუნიკაციო ჩათში!</b>",
        chat_id,
        call.message.message_id,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /broadcast
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ არ გაქვს წვდომა.")
        return
    admin_broadcast_state[message.chat.id] = "waiting"
    bot.send_message(
        message.chat.id,
        "📢 <b>Broadcast რეჟიმი</b>\n\n"
        "გამოაგზავნე შეტყობინება და ავტომატურად გაიგზავნება ყველა იუზერთან.\n\n"
        "გასაუქმებლად: /cancel",
        parse_mode="HTML"
    )

def load_notified():
    if not os.path.exists(NOTIFIED_FILE):
        return []
    try:
        with open(NOTIFIED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_notified(data):
    with open(NOTIFIED_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

@bot.message_handler(commands=['newmsg'])
def newmsg_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    admin_broadcast_state[message.chat.id] = "newmsg"
    bot.send_message(message.chat.id,
        "📢 <b>ახალი შეტყობინება</b>\n\n"
        "გამოაგზავნე ტექსტი — გაიგზავნება მხოლოდ მათ ვისაც ჯერ არ მისვლია.\n\n"
        "გასაუქმებლად: /cancel",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['all'])
def all_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    admin_broadcast_state[message.chat.id] = "waiting"
    bot.send_message(
        message.chat.id,
        "📢 <b>ყველასთან გაგზავნა</b>\n\n"
        "გამომიგზავნე შეტყობინება და გავაგზავნი ყველა იუზერთან.\n\n"
        "გასაუქმებლად: /cancel",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['new'])
def new_cmd(message):
    if message.chat.id != ADMIN_ID:
        return
    admin_broadcast_state[message.chat.id] = "newmsg"
    bot.send_message(
        message.chat.id,
        "🆕 <b>მხოლოდ ახალებთან გაგზავნა</b>\n\n"
        "გამომიგზავნე შეტყობინება — მივა მხოლოდ მათთან, ვისაც ჯერ არ მისვლია.\n\n"
        "გასაუქმებლად: /cancel",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and admin_broadcast_state.get(m.chat.id) == "newmsg")
def do_newmsg(message):
    del admin_broadcast_state[message.chat.id]
    data = load_data()
    notified = load_notified()
    sent, failed = 0, 0

    for chat_id in data:
        if chat_id in notified:
            continue
        try:
            bot.copy_message(chat_id, message.chat.id, message.message_id)
            notified.append(chat_id)
            sent += 1
        except:
            failed += 1

    save_notified(notified)
    bot.send_message(message.chat.id,
        f"✅ <b>გაიგზავნა!</b>\n\n"
        f"✅ გაიგზავნა: <code>{sent}</code>\n"
        f"❌ ვერ გაიგზავნა: <code>{failed}</code>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['cancel'])
def cancel_cmd(message):
    if message.chat.id in admin_broadcast_state:
        del admin_broadcast_state[message.chat.id]
        bot.send_message(message.chat.id, "✅ გაუქმებულია.")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and admin_broadcast_state.get(m.chat.id) == "waiting")
def do_broadcast(message):
    del admin_broadcast_state[message.chat.id]
    data = load_data()
    users = list(data.keys())
    sent, failed = 0, 0
    for uid in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            sent += 1
        except:
            failed += 1
    bot.send_message(
        message.chat.id,
        f"✅ <b>გაგზავნა დასრულდა!</b>\n\n"
        f"👥 სულ იუზერი: <code>{len(users)}</code>\n"
        f"✅ გაიგზავნა: <code>{sent}</code>\n"
        f"❌ ვერ გაიგზავნა: <code>{failed}</code>",
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start და /settings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['start', 'settings'])
def start(message):
    if message.chat.type != "private":
        return
    data = load_data()
    chat_id = str(message.chat.id)
    is_new = chat_id not in data
    if is_new:
        data[chat_id] = []
        save_data(data)

    bot.send_message(
        chat_id,
        "🏛 <b>მოგესალმებით!</b>\n\n"
        "ეს ბოტი დაგეხმარებათ მართვის მოწმობის პრაქტიკული გამოცდის დაჭავშნაში.\n\n"
        "დააჭირეთ ქვედა ღილაკს ქალაქის ასარჩევად 👇",
        parse_mode="HTML",
        reply_markup=get_keyboard(data[chat_id])
    )

    # ახალ იუზერს ავტომატურად უგზავნის ჯგუფის ღილაკს
    if is_new:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            text="🗣 შემოგვიერთდი საკომუნიკაციო ჩათში",
            callback_data="join_community"
        ))
        bot.send_message(
            chat_id,
            "👥 <b>საკომუნიკაციო ჩათი</b>\n\n"
            "შემოგვიერთდი ჩვენს ჯგუფში სადაც შეგიძლია სხვა მომხმარებლებთან დაკავშირება 👇",
            parse_mode="HTML",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle:"))
def toggle(call):
    city = call.data.split(":")[1]
    data = load_data()
    chat_id = str(call.message.chat.id)
    if chat_id not in data:
        data[chat_id] = []
    if city in data[chat_id]:
        data[chat_id].remove(city)
    else:
        data[chat_id].append(city)
    save_data(data)
    bot.answer_callback_query(call.id)
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_keyboard(data[chat_id]))

@bot.callback_query_handler(func=lambda call: call.data == "select_all")
def select_all(call):
    data = load_data()
    chat_id = str(call.message.chat.id)
    if chat_id not in data:
        data[chat_id] = []
    all_selected = all(c in data[chat_id] for c in CITIES_LIST)
    if all_selected:
        data[chat_id] = []
        bot.answer_callback_query(call.id, "ყველა ქალაქი მოხსნილია")
    else:
        data[chat_id] = list(CITIES_LIST)
        bot.answer_callback_query(call.id, "ყველა ქალაქი მონიშნულია ✅")
    save_data(data)
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_keyboard(data[chat_id]))

@bot.callback_query_handler(func=lambda call: call.data == "save_settings")
def save(call):
    data = load_data()
    chat_id = str(call.message.chat.id)
    user_cities = data.get(chat_id, [])
    bot.answer_callback_query(call.id, "შენახულია! ✅")

    try:
        user = call.message.chat
        name = user.first_name or "უცნობი"
        if user.last_name:
            name += f" {user.last_name}"
        username = f" (@{user.username})" if user.username else ""
        admin_msg = (
            f"🔔 <b>იუზერმა შეინახა მონაცემები!</b>\n\n"
            f"👤 <b>სახელი:</b> {name}{username}\n"
            f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
            f"📍 <b>ქალაქები:</b> {', '.join(user_cities) if user_cities else 'არ აურჩევია'}"
        )
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")
    except Exception as e:
        print(f"შეტყობინების გაგზავნის ერორი: {e}")

    if not user_cities:
        confirm_text = "⚠️ <b>ქალაქი არ არის არჩეული!</b>\n\nგთხოვთ მონიშნოთ მინიმუმ ერთი ქალაქი.\n\nდააჭირეთ /settings ხელახლა ასარჩევად."
    elif len(user_cities) == len(CITIES_LIST):
        confirm_text = ("✅ <b>ყველა ქალაქი არჩეულია!</b>\n\n🔍 <b>ვეძებთ ყველა ქალაქში:</b>\n"
            + ", ".join(f"<code>{c}</code>" for c in user_cities)
            + "\n\n📩 შეტყობინებას მიიღებთ ნებისმიერი ქალაქის გახსნისას.")
    elif len(user_cities) == 1:
        confirm_text = (f"✅ <b>ქალაქი არჩეულია: {user_cities[0]}</b>\n\n"
            f"🔍 <b>ვეძებთ მხოლოდ {user_cities[0]}ში</b>\n\n"
            f"📩 შეტყობინებას მიიღებთ ადგილის გახსნისთანავე.")
    else:
        cities_fmt = "\n".join(f"  • <code>{c}</code>" for c in user_cities)
        confirm_text = (f"✅ <b>არჩეულია {len(user_cities)} ქალაქი:</b>\n\n{cities_fmt}\n\n"
            f"🔍 <b>ვეძებთ მხოლოდ ამ ქალაქებში</b>\n\n"
            f"📩 შეტყობინებას მიიღებთ ამ ქალაქებიდან ნებისმიერის გახსნისას.\n\n"
            f"⚙️ შეცვლა: /settings")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="⚙️ ქალაქების არჩევა ახლიდან", callback_data="reopen_cities"))
    bot.edit_message_text(confirm_text, chat_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "reopen_cities")
def reopen_cities(call):
    data = load_data()
    chat_id = str(call.message.chat.id)
    user_cities = data.get(chat_id, [])
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "🏛 <b>მონიშნეთ ქალაქები:</b>\n\n<i>დააჭირეთ ქალაქს მოსანიშნად და ბოლოს შეინახეთ.</i>",
        chat_id, call.message.message_id,
        parse_mode="HTML",
        reply_markup=get_keyboard(user_cities)
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id != ADMIN_ID:
        return
    data = load_data()
    if not data:
        bot.send_message(message.chat.id, "📭 ბაზაში ჯერ არავინ არის.")
        return

    count = len(data)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📂 სიის გახსნა", callback_data="users_expand"))
    bot.send_message(
        message.chat.id,
        f"👥 <b>იუზერების რაოდენობა:</b> <code>{count}</code>\n\n"
        "სიის სანახავად დააჭირე ღილაკს 👇",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "users_expand")
def users_expand(call):
    if call.message.chat.id != ADMIN_ID:
        return
    data = load_data()
    if not data:
        bot.answer_callback_query(call.id, "სია ცარიელია")
        return

    lines = ["👥 <b>აქტიური იუზერების სია:</b>\n"]
    for chat_id, cities in data.items():
        try:
            chat_info = bot.get_chat(chat_id)
            name = chat_info.first_name or "უცნობი"
            if chat_info.last_name:
                name += f" {chat_info.last_name}"
            username = f" (@{chat_info.username})" if chat_info.username else ""
            cities_str = ", ".join(cities) if cities else "არ აურჩევია"
            lines.append(f"👤 <b>{name}</b>{username}\n🆔 ID: <code>{chat_id}</code>\n📍 ქალაქები: {cities_str}\n")
        except:
            lines.append(f"👤 უცნობი იუზერი\n🆔 ID: <code>{chat_id}</code>\n📍 ქალაქები: {', '.join(cities)}\n")
    msg_text = "\n".join(lines)
    close_markup = types.InlineKeyboardMarkup()
    close_markup.add(types.InlineKeyboardButton(text="🔽 სიის დახურვა", callback_data="users_collapse"))
    bot.answer_callback_query(call.id, "სია გაიხსნა")

    if len(msg_text) > 4000:
        parts = [msg_text[x:x+4000] for x in range(0, len(msg_text), 4000)]
        bot.edit_message_text(parts[0], call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=close_markup)
        for part in parts[1:]:
            bot.send_message(call.message.chat.id, part, parse_mode="HTML")
    else:
        bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=close_markup)

@bot.callback_query_handler(func=lambda call: call.data == "users_collapse")
def users_collapse(call):
    if call.message.chat.id != ADMIN_ID:
        return
    count = len(load_data())
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📂 სიის გახსნა", callback_data="users_expand"))
    bot.answer_callback_query(call.id, "სია დაიხურა")
    bot.edit_message_text(
        f"👥 <b>იუზერების რაოდენობა:</b> <code>{count}</code>\n\n"
        "სიის სანახავად დააჭირე ღილაკს 👇",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /autobook
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['autobook'])
def manage_autobook(message):
    if message.chat.id != ADMIN_ID:
        return
    args = message.text.split()
    if not os.path.exists(AUTOBOOK_FILE):
        config = {"enabled": False, "target_user_id": "", "button_text": "დაჯავშნა", "stop_after_booking": True}
    else:
        with open(AUTOBOOK_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    if len(args) == 1:
        status = "🟢 ჩართული" if config.get("enabled") else "🔴 გამორთული"
        user = config.get("target_user_id", "არავინ")
        bot.send_message(
            message.chat.id,
            f"⚙️ <b>ავტო-დაჯავშნის სტატუსი:</b>\n\n"
            f"სტატუსი: {status}\n"
            f"სამიზნე იუზერი: <code>{user}</code>\n\n"
            f"<b>მართვის ბრძანებები:</b>\n"
            f"ჩასართავად: <code>/autobook on იუზერის_ID</code>\n"
            f"გამოსართავად: <code>/autobook off</code>",
            parse_mode="HTML"
        )
        return
    action = args[1].lower()
    if action == "on" and len(args) == 3:
        config["enabled"] = True
        config["target_user_id"] = args[2]
        with open(AUTOBOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

        data = load_data()
        user_cities = data.get(args[2], [])
        cities_fmt = "\n".join(f"  • <code>{c}</code>" for c in user_cities) if user_cities else "  • არ არის არჩეული"

        try:
            bot.send_message(args[2],
                "🤖 <b>ავტომატური ჯავშანი ჩაირთო!</b>\n"
                "────────────────────\n\n"
                f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
                "────────────────────\n\n"
                "🔔 <b>ადგილის გამოჩენისთანავე ავტომატურად დაგიჭერთ!</b>",
                parse_mode="HTML"
            )
        except:
            pass

        bot.send_message(message.chat.id,
            f"✅ <b>ავტო-დაჯავშნა ჩაირთო!</b>\n\nსამიზნე ID: <code>{args[2]}</code>",
            parse_mode="HTML")
    elif action == "off":
        config["enabled"] = False
        with open(AUTOBOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        bot.send_message(message.chat.id,
            "🛑 <b>ავტო-დაჯავშნა გამოირთო!</b>",
            parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ არასწორი ბრძანება.\n/autobook on ID\n/autobook off")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /startbot
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['startbot'])
def startbot_cmd(message):
    global search_enabled
    if message.chat.id != ADMIN_ID:
        return
    search_enabled = True

    data = load_data()
    autobook_config = {}
    if os.path.exists(AUTOBOOK_FILE):
        with open(AUTOBOOK_FILE, 'r', encoding='utf-8') as f:
            autobook_config = json.load(f)

    target_user_id = str(autobook_config.get("target_user_id", ""))
    notified = load_notified()
    sent = 0

    for chat_id, cities in data.items():
        if not cities:
            continue
        cities_fmt = "\n".join(f"  • <code>{c}</code>" for c in cities)
        if chat_id == target_user_id and autobook_config.get("enabled"):
            msg = (
                "🤖 <b>ავტო-ჯავშნის ძიება დაიწყო!</b>\n"
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
        try:
            bot.send_message(chat_id, msg, parse_mode="HTML")
            if chat_id not in notified:
                notified.append(chat_id)
            sent += 1
        except:
            pass

    save_notified(notified)
    bot.send_message(
        ADMIN_ID,
        f"✅ <b>შეტყობინებები გაიგზავნა!</b>\n\n"
        f"👥 სულ იუზერი: <code>{len(data)}</code>\n"
        f"✅ გაიგზავნა: <code>{sent}</code>",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['stopbot'])
def stopbot_cmd(message):
    global search_enabled
    if message.chat.id != ADMIN_ID:
        return
    search_enabled = False
    bot.send_message(
        ADMIN_ID,
        "🛑 <b>ძიება გაჩერებულია.</b>\n\n"
        "ბოტი დროებით აღარ გააგზავნის ძიების საათობრივ შეტყობინებებს.\n"
        "გასააქტიურებლად: <code>/startbot</code>",
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ყოველ საათში შეტყობინება
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import threading

def hourly_reminder():
    while True:
        time.sleep(3600)
        if not search_enabled:
            continue
        data = load_data()
        if not data:
            continue

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
                    "🤖 <b>ავტო-ჯავშანი აქტიურია!</b>\n"
                    "────────────────────\n\n"
                    f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
                    "────────────────────\n\n"
                    "🔔 <b>ბოტი მუშაობს 24/7 — ადგილის გამოჩენისთანავე დაგიჭერთ!</b>"
                )
            else:
                msg = (
                    "⏳ <b>ძიება მიმდინარეობს...</b>\n"
                    "────────────────────\n\n"
                    f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
                    "────────────────────\n\n"
                    "🔔 <b>ბოტი მუშაობს 24/7 — ადგილის გამოჩენისთანავე შეგატყობინებთ!</b>"
                )
            try:
                bot.send_message(chat_id, msg, parse_mode="HTML")
            except:
                pass

threading.Thread(target=hourly_reminder, daemon=True).start()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /dm და /msg
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(commands=['dm'])
def dm_user(message):
    if message.chat.id != ADMIN_ID:
        return
    args = message.text.split(None, 2)
    if len(args) < 3:
        bot.send_message(message.chat.id,
            "გამოიყენე ასე:\n<code>/dm USER_ID შეტყობინება</code>",
            parse_mode="HTML")
        return
    try:
        bot.send_message(args[1], args[2], parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ გაიგზავნა!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ შეცდომა: {e}")

@bot.message_handler(commands=['msg'])
def msg_user(message):
    if message.chat.id != ADMIN_ID:
        return
    args = message.text.split(None, 2)
    if len(args) < 3:
        bot.send_message(message.chat.id,
            "გამოიყენე ასე:\n<code>/msg USER_ID შეტყობინება</code>",
            parse_mode="HTML")
        return
    try:
        bot.send_message(args[1], args[2], parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ გაიგზავნა!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ შეცდომა: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ — ავტო-დაჯავშნის მოთხოვნა
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(func=lambda m: m.text == "✅" and m.chat.type == "private")
def autobook_request(message):
    chat_id = str(message.chat.id)
    user = message.chat
    name = user.first_name or "უცნობი"
    if user.last_name:
        name += f" {user.last_name}"
    username = f" (@{user.username})" if user.username else ""
    bot.send_message(
        ADMIN_ID,
        f"🔔 <b>ავტო-დაჯავშნის მოთხოვნა!</b>\n\n"
        f"👤 <b>სახელი:</b> {name}{username}\n"
        f"🆔 <b>ID:</b> <code>{chat_id}</code>\n\n"
        f"იუზერს სურს ავტომატური დაჯავშნა.",
        parse_mode="HTML"
    )
    bot.send_message(
        message.chat.id,
        "✅ <b>თქვენი მოთხოვნა მიღებულია!</b>\n\n"
        "ადმინისტრატორი მალე დაგიკავშირდებათ.",
        parse_mode="HTML"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# იუზერის შეტყობინება → topic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(func=lambda m: m.chat.type == "private" and m.chat.id != ADMIN_ID)
def forward_to_topic(message):
    if not message.text:
        return
    chat_id = str(message.chat.id)
    user = message.chat
    name = user.first_name or "უცნობი"
    if user.last_name:
        name += f" {user.last_name}"
    username = f" (@{user.username})" if user.username else ""

    topic_id = get_or_create_topic(chat_id, f"{name}{username}")

    if topic_id:
        try:
            bot.send_message(GROUP_ID, f"💬 {message.text}", message_thread_id=topic_id)
        except telebot.apihelper.ApiTelegramException as e:
            if "message thread not found" in str(e).lower():
                topics = load_topics()
                if chat_id in topics:
                    del topics[chat_id]
                    save_topics(topics)
                new_topic_id = get_or_create_topic(chat_id, f"{name}{username}")
                if new_topic_id:
                    bot.send_message(GROUP_ID, f"💬 {message.text}", message_thread_id=new_topic_id)
            else:
                print(f"⚠️ გაგზავნის ერორი: {e}")
    else:
        bot.send_message(
            ADMIN_ID,
            f"💬 <b>{name}{username}</b>\n🆔 <code>{chat_id}</code>\n\n{message.text}",
            parse_mode="HTML"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ჯგუფიდან პასუხი → იუზერს
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.message_handler(func=lambda m: m.chat.id == GROUP_ID and m.message_thread_id is not None and not m.from_user.is_bot)
def reply_from_group(message):
    topics = load_topics()
    for user_id, topic_id in topics.items():
        if topic_id == message.message_thread_id:
            try:
                bot.send_message(
                    user_id,
                    f"📩 <b>ადმინისტრაციის პასუხი:</b>\n\n{message.text}",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"პასუხის შეცდომა: {e}")
            break

print("🤖 ბოტი ჩართულია...")
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"⚠️ კავშირი წყდება... ({e})")
        time.sleep(5)