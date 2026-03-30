import asyncio
import os
import json
import telebot
from playwright.async_api import async_playwright
from threading import Thread

# --- მონაცემები ---
TOKEN = "8043569123:AAHv3MCItdKS2x7qj24wI3wUyuKlPynLvsg"
ADMIN_ID = 1295535879
FILE_NAME = "users.json"
AUTH_FILE = "auth.json"  # აქ შეინახება სესია
BOOKING_URL = "https://my.sa.gov.ge" 

bot = telebot.TeleBot(TOKEN)

def load_users():
    if not os.path.exists(FILE_NAME): return []
    with open(FILE_NAME, 'r') as f:
        try: return json.load(f)
        except: return []

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = str(message.chat.id)
    if chat_id not in load_users():
        users = load_users()
        users.append(chat_id)
        with open(FILE_NAME, 'w') as f: json.dump(users, f, indent=4)
        bot.send_message(chat_id, "✅ დარეგისტრირდი! ადგილის გამოჩენისას შეგატყობინებ 🔔")
    else:
        bot.send_message(chat_id, "უკვე სიაში ხარ! 🚀")

# --- LOGIN სესიის შენახვით ---
async def login(browser_context, page):
    if os.path.exists(AUTH_FILE):
        print("🍪 ვიყენებ შენახულ სესიას, კოდი აღარ მჭირდება...")
        return True
    try:
        print("🔐 ვცდილობ პირველად შესვლას...")
        await page.goto('https://my.sa.gov.ge', wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await page.locator('text=შესვლა').first.click()
        await asyncio.sleep(2)
        await page.fill('input[type="email"]', 'gogakirvalidze@gmail.com')
        await page.fill('input[type="password"]', 'Kirvala1#')
        await page.locator('button[type="submit"]').click()
        
        print("⏳ დაელოდე! თუ SMS მოვიდა, ჩაწერე ბრაუზერში ხელით (გაქვს 20 წამი)...")
        await asyncio.sleep(20) 

        # ვინახავთ სესიას ფაილში
        await browser_context.storage_state(path=AUTH_FILE)
        print("✅ სესია შენახულია! შემდეგში კოდს აღარ მოგთხოვს.")
        return True
    except Exception as e:
        print(f"❌ შესვლა ვერ მოხდა: {e}")
        return False

# --- შემოწმების ლოგიკა ---
async def monitor_slots():
    async with async_playwright() as p:
        # შეცვალე False-ზე პირველად, რომ SMS ჩაწერო!
        browser = await p.chromium.launch(headless=False) 
        
        storage = AUTH_FILE if os.path.exists(AUTH_FILE) else None
        context = await browser.new_context(storage_state=storage)
        page = await context.new_page()

        if await login(context, page):
            while True:
                try:
                    print("🔍 ვამოწმებ კალენდარს...")
                    await page.goto(BOOKING_URL, wait_until="networkidle")
                    await asyncio.sleep(5)
                    content = await page.content()

                    if "დაჯავშნილია" in content or "აქტიური ჯავშანი" in content:
                        bot.send_message(ADMIN_ID, "⚠️ ექაუნთმა დაიჯავშნა ადგილი!")
                        break

                    if "თავისუფალი" in content:
                        print("🎉 ადგილი იპოვნა!")
                        for user_id in load_users():
                            try: bot.send_message(user_id, "📢 გამოჩნდა თავისუფალი ადგილი!")
                            except: pass
                        await asyncio.sleep(600)
                    
                    await asyncio.sleep(180)
                except Exception as e:
                    print(f"⚠️ შეცდომა: {e}")
                    await asyncio.sleep(30)

if __name__ == "__main__":
    Thread(target=lambda: bot.infinity_polling(), daemon=True).start()
    asyncio.run(monitor_slots())
