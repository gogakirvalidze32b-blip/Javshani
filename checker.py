import asyncio
import random
import requests
import json
import os
import time
import datetime
import inspect
from playwright.async_api import async_playwright

try:
    import winsound
except ImportError:
    winsound = None

try:
    from playwright_stealth import stealth_async as stealth_func
except ImportError:
    try:
        from playwright_stealth import stealth as stealth_func
    except:
        stealth_func = None

TOKEN = "8043569123:AAHv3MCItdKS2x7qj24wI3wUyuKlPynLvsg"
ADMIN_ID = 8330284515
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0") or 0)  # ცალკე chat/channel id debug ლოგებისთვის
DEBUG_TO_LOG_CHAT = os.getenv("DEBUG_TO_LOG_CHAT", "1") == "1"
DEBUG_LOG_EVERY_CITY = os.getenv("DEBUG_LOG_EVERY_CITY", "0") == "1"
EXACT_TIMING = os.getenv("EXACT_TIMING", "0") == "1"
FIXED_CYCLE_WAIT_SECONDS = int(os.getenv("FIXED_CYCLE_WAIT_SECONDS", "30") or 30)
USE_PROXY_ENV = os.getenv("USE_PROXY", "").strip().lower()  # 1/true/on ან 0/false/off
FILE_NAME = "users.json"
AUTOBOOK_FILE = "autobook.json"
last_report_time = 0
last_reminder_time = 0
MANUAL_LOGIN_GRACE_SECONDS = 300
LOGOUT_SPAM_INTERVAL_SECONDS = int(os.getenv("LOGOUT_SPAM_INTERVAL_SECONDS", "30") or 30)
_last_logout_signal_time = 0.0

PROXIES = [
    {"server": "http://31.59.20.176:6754",    "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://23.95.150.145:6114",   "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://198.23.239.134:6540",  "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://45.38.107.97:6014",    "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://107.172.163.27:6543",  "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://198.105.121.200:6462", "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://216.10.27.159:6837",   "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://142.111.67.146:5611",  "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://191.96.254.138:6185",  "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
    {"server": "http://31.58.9.4:6077",       "username": "kemibmrf", "password": "5ld1nwwhs1ym"},
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Keep-alive ტაიმერი (12 წუთი)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
last_agree_click_time = 0
AGREE_INTERVAL_SECONDS = int(os.getenv("AGREE_INTERVAL_SECONDS", str(15 * 60)) or (15 * 60))
NAV_TIMEOUT_MS = 60000
NAV_RETRIES = 2
NAV_EVERY_N_CYCLES = int(os.getenv("NAV_EVERY_N_CYCLES", "8") or 8)
KEEPALIVE_ENABLED = os.getenv("KEEPALIVE_ENABLED", "1") == "1"
LOGOUT_BACKOFF_SECONDS_MIN = int(os.getenv("LOGOUT_BACKOFF_SECONDS_MIN", "45") or 45)
LOGOUT_BACKOFF_SECONDS_MAX = int(os.getenv("LOGOUT_BACKOFF_SECONDS_MAX", "120") or 120)


async def sleep_between(min_s, max_s):
    if EXACT_TIMING:
        await asyncio.sleep((min_s + max_s) / 2)
    else:
        await asyncio.sleep(random.uniform(min_s, max_s))


def safe_telegram_post(url, data, timeout=10, context="telegram"):
    try:
        resp = requests.post(url, data=data, timeout=timeout)
        if resp.status_code != 200:
            print(f"⚠️ Telegram ({context}) HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        payload = resp.json()
        if not payload.get("ok", False):
            print(f"⚠️ Telegram ({context}) API error: {payload}")
            return False
        return True
    except Exception as e:
        print(f"⚠️ Telegram ({context}) შეცდომა: {e}")
        return False


def send_log_msg(text, force=False):
    if not LOG_CHAT_ID:
        return False
    if not DEBUG_TO_LOG_CHAT and not force:
        return False
    return safe_telegram_post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": LOG_CHAT_ID,
            "text": text
        },
        timeout=10,
        context="debug-log"
    )


async def safe_goto(page, url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS, retries=NAV_RETRIES):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            return True
        except Exception as e:
            last_exc = e
            msg = f"⚠️ navigate შეცდომა (ცდა {attempt}/{retries}): {e}"
            print(msg)
            send_log_msg(msg)
            if attempt < retries:
                await asyncio.sleep(2 * attempt)
    fail_msg = f"❌ navigate ვერ შესრულდა: {last_exc}"
    print(fail_msg)
    send_log_msg(fail_msg, force=True)
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ადამიანური მოძრაობის ფუნქციები
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def human_move_and_click(page, element):
    try:
        try:
            await page.evaluate("(el) => el.scrollIntoView({block: 'center'})", await element.element_handle())
        except:
            pass
        await sleep_between(0.3, 0.6)
        box = await element.bounding_box()
        if not box:
            await element.click()
            return
        target_x = box["x"] + box["width"] / 2
        target_y = box["y"] + box["height"] / 2
        await page.mouse.move(target_x + random.uniform(-30, 30), target_y + random.uniform(-20, 20))
        await sleep_between(0.1, 0.3)
        await page.mouse.move(target_x, target_y, steps=random.randint(5, 10))
        await sleep_between(0.1, 0.2)
        await page.mouse.click(target_x, target_y)
        print(f"🖱 კლიკი: ({int(target_x)}, {int(target_y)})")
    except Exception as e:
        print(f"⚠️ კლიკის შეცდომა: {e}")
        try:
            await element.click()
        except:
            pass


async def close_overlays(page):
    # ღია dropdown/dialog ხშირად აბნევს შემდეგ კლიკებს
    for _ in range(2):
        try:
            await page.keyboard.press("Escape")
        except:
            pass
        await asyncio.sleep(0.15)


async def wait_city_dropdown(page, timeout=10000):
    end_at = time.time() + (timeout / 1000)
    while time.time() < end_at:
        try:
            dropdowns = page.locator("mat-select")
            count = await dropdowns.count()
            for k in range(count):
                pl = await dropdowns.nth(k).get_attribute("placeholder")
                if pl and "საგამოცდო ცენტრი" in pl:
                    return dropdowns.nth(k)
        except:
            pass
        await asyncio.sleep(0.25)
    return None


async def robust_click(page, locator, label="element"):
    # პირველ ცდაზე ველოდებით ხილვადობას, მერე "human" კლიკი, ბოლოს force fallback
    for attempt in range(1, 4):
        try:
            await locator.wait_for(state="visible", timeout=8000)
            await human_move_and_click(page, locator)
            return True
        except Exception as e:
            msg = f"⚠️ {label} კლიკი ვერ შესრულდა (ცდა {attempt}/3): {e}"
            print(msg)
            send_log_msg(msg)
            try:
                await locator.click(force=True, timeout=4000)
                return True
            except:
                await close_overlays(page)
                await asyncio.sleep(0.3 * attempt)
    return False


async def human_scroll(page):
    try:
        scroll_y = random.randint(300, 600)
        await page.mouse.wheel(0, scroll_y // 3)
        await sleep_between(0.3, 0.5)
        await page.mouse.wheel(0, scroll_y // 3)
        await sleep_between(0.3, 0.5)
        await page.mouse.wheel(0, scroll_y // 3)
        await sleep_between(0.4, 0.8)
        await page.mouse.wheel(0, -(scroll_y // 4))
        await sleep_between(0.2, 0.4)
        await page.evaluate(
            """(amount) => {
                window.scrollBy({ top: amount, behavior: "auto" });
                const selectors = [
                    ".mat-mdc-dialog-content",
                    ".mat-dialog-content",
                    "div[appcustomscroll]",
                    ".cdk-overlay-pane .mat-mdc-select-panel",
                    "mat-sidenav-content",
                    "main"
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.scrollHeight > el.clientHeight) {
                        el.scrollTop = Math.min(el.scrollTop + Math.floor(amount * 0.8), el.scrollHeight);
                        break;
                    }
                }
            }""",
            scroll_y
        )
        await sleep_between(0.15, 0.35)
    except:
        pass

async def human_pause():
    await sleep_between(0.25, 1.0)

async def random_idle(page):
    x = random.randint(200, 900)
    y = random.randint(200, 600)
    await page.mouse.move(x, y, steps=random.randint(5, 10))
    await sleep_between(0.1, 0.35)

async def anti_bot_break(page):
    if random.random() < 0.12:
        await random_idle(page)
        await sleep_between(1.0, 2.5)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# "ვეთანხმები" სქროლი + კლიკი
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def scroll_to_bottom_and_agree(page):
    try:
        # ჯერ ველოდებით რომ modal ნამდვილად გამოჩნდეს
        await page.locator(".cdk-overlay-pane, mat-dialog-container").first.wait_for(state="visible", timeout=8000)
        agree_btn = page.locator('button:has-text("ვეთანხმები"), text=ვეთანხმები').first
        if not await agree_btn.is_visible(timeout=6000):
            return False

        # რამდენიმე ცდით ვსქროლავთ modal-ს ბოლომდე და ვცდილობთ დაჭერას
        for attempt in range(1, 6):
            scrolled_to_bottom = await page.evaluate("""
                () => {
                    const selectors = [
                        ".mat-mdc-dialog-content",
                        ".mat-dialog-content",
                        "mat-dialog-content",
                        "div[appcustomscroll]",
                        ".cdk-overlay-pane .mat-mdc-dialog-content",
                        ".cdk-overlay-pane .mat-dialog-content",
                        ".modal-body"
                    ];
                    let target = null;
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.scrollHeight > el.clientHeight) {
                            target = el;
                            break;
                        }
                    }
                    if (!target) return true;
                    target.scrollTop = Math.min(target.scrollTop + Math.floor(target.clientHeight * 0.9), target.scrollHeight);
                    return target.scrollTop + target.clientHeight >= target.scrollHeight - 6;
                }
            """)

            try:
                is_disabled = await agree_btn.evaluate(
                    "el => el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true'"
                )
            except:
                is_disabled = False

            if (not is_disabled) and await agree_btn.is_visible(timeout=1500):
                clicked = await robust_click(page, agree_btn, label="'ვეთანხმები'")
                if clicked:
                    await sleep_between(1.0, 1.8)
                    print("✅ 'ვეთანხმები' დაჭერილია.")
                    return True

            if not scrolled_to_bottom:
                await page.mouse.wheel(0, 350)
            await asyncio.sleep(0.45 + (attempt * 0.08))

        print("ℹ️ 'ვეთანხმები' ჯერ disabled/უხილავია პირველ ცდებზე.")
        return False
    except Exception as e:
        print(f"⚠️ scroll_to_bottom_and_agree შეცდომა: {e}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Keep-alive: ყოველ 12 წუთში
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def keepalive_agree_click(page):
    global last_agree_click_time
    now = time.time()
    if now - last_agree_click_time < AGREE_INTERVAL_SECONDS:
        return False, False

    msg = "🔄 Keep-alive: ვახლებ სესიას და ვაჭერ 'ვეთანხმები'-ს..."
    print(msg)
    send_log_msg(msg)
    try:
        ok = await safe_goto(page, 'https://my.sa.gov.ge')
        if not ok:
            # timeout-ის დროს ნუ შევაჩერებთ მთლიან ლუპს; შემდეგ ციკლში ხელახლა ცდის
            last_agree_click_time = time.time()
            return True, False
        await sleep_between(3, 5)

        if await confirm_logged_out(page):
            msg = "🔒 Keep-alive: სესია გავიდა navigate-ის შემდეგ!"
            print(msg)
            send_log_msg(msg, force=True)
            last_agree_click_time = time.time()
            return True, True

        await human_scroll(page)

        practic_btn = page.locator('text=პრაქტიკული გამოცდა').first
        try:
            await practic_btn.wait_for(state="visible", timeout=8000)
            await human_move_and_click(page, practic_btn)
            await sleep_between(3, 5)
        except:
            msg = "⚠️ Keep-alive: 'პრაქტიკული გამოცდა' ვერ ვიპოვე"
            print(msg)
            send_log_msg(msg)

        if await confirm_logged_out(page):
            msg = "🔒 Keep-alive: სესია გავიდა!"
            print(msg)
            send_log_msg(msg, force=True)
            last_agree_click_time = time.time()
            return True, True

        try:
            agreed = await scroll_to_bottom_and_agree(page)
            if agreed:
                msg = "✅ Keep-alive: სესია განახლებულია."
                print(msg)
                send_log_msg(msg)
            else:
                msg = "ℹ️ Keep-alive: 'ვეთანხმები' არ ჩანს."
                print(msg)
                send_log_msg(msg)
        except Exception as e:
            msg = f"⚠️ 'ვეთანხმები' ვერ დაჭირდა: {e}"
            print(msg)
            send_log_msg(msg)

        last_agree_click_time = time.time()
        return True, False

    except Exception as e:
        msg = f"❌ Keep-alive შეცდომა: {e}"
        print(msg)
        send_log_msg(msg, force=True)
        last_agree_click_time = time.time()
        return True, False


async def ensure_b_and_second_stage(page, force=False):
    try:
        category_selected = False
        stage_selected = False

        if not force:
            try:
                selected = await page.locator("mat-select .mat-mdc-select-value-text").first.inner_text()
                category_selected = "B" in selected
            except:
                category_selected = False
            try:
                selected_stage = await page.locator("mat-button-toggle-checked").first.inner_text()
                stage_selected = "მეორე ეტაპი" in selected_stage
            except:
                stage_selected = False

        if not category_selected:
            cat_drop = page.locator("mat-select").first
            await human_move_and_click(page, cat_drop)
            await sleep_between(2, 3.5)
            try:
                b_option = page.locator('mat-option:has-text("B")').first
                await b_option.wait_for(timeout=8000)
                await human_move_and_click(page, b_option)
                await sleep_between(0.8, 1.8)
            except:
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)

        if not stage_selected:
            stage_2 = page.locator('text=მეორე ეტაპი').first
            if await stage_2.is_visible():
                await human_pause()
                await human_move_and_click(page, stage_2)
                await sleep_between(1.2, 2.5)
    except:
        pass


def _rate_limited_logout_print(msg: str):
    global _last_logout_signal_time
    now = time.time()
    if now - _last_logout_signal_time >= LOGOUT_SPAM_INTERVAL_SECONDS:
        _last_logout_signal_time = now
        print(msg)
        return True
    return False


async def is_logged_out(page, quiet=False):
    try:
        url = page.url.lower()
        if "login" in url or "/auth" in url or "signin" in url:
            if not quiet:
                _rate_limited_logout_print(f"🔒 logout სიგნალი URL-დან: {page.url}")
            return True

        login_btn = page.locator('button:has-text("შესვლა"), a:has-text("შესვლა")').first
        if await login_btn.is_visible(timeout=2000):
            if not quiet:
                _rate_limited_logout_print("🔒 logout სიგნალი: 'შესვლა' ღილაკი ჩანს")
            return True

        phone_input = page.locator('input[type="tel"], input[placeholder*="ტელეფ"], input[placeholder*="პირად"]').first
        if await phone_input.is_visible(timeout=1500):
            if not quiet:
                _rate_limited_logout_print("🔒 logout სიგნალი: login ფორმა ჩანს")
            return True

        return False
    except:
        return False


async def confirm_logged_out(page, checks=3, delay=1.2):
    # URL-ის მოკლე გადართვებზე false positive რომ არ ჩაითვალოს logout
    hits = 0
    for _ in range(checks):
        if await is_logged_out(page, quiet=True):
            hits += 1
        await asyncio.sleep(delay)
    return hits >= 2


async def wait_for_manual_login(page):
    msg = "🔐 ავტორიზაცია საჭიროა — გაიარე login/SMS კოდი და ბოტი ავტომატურად გააგრძელებს."
    print(msg)
    send_log_msg(msg, force=True)
    while True:
        await asyncio.sleep(5)
        if not await confirm_logged_out(page):
            ok_msg = "✅ ავტორიზაცია დასრულდა — ვაგრძელებ სკანირებას."
            print(ok_msg)
            send_log_msg(ok_msg, force=True)
            await asyncio.sleep(1.5)
            return


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ბრაუზერის გაშვება
# PC (Windows/Mac):  headless=False — ბრაუზერი ჩანს
# სერვერი (Ubuntu):  headless=True  — DISPLAY არ არის
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def relaunch_browser_context(playwright, user_data_dir):
    print("🌐 ვტვირთავ ბრაუზერს (persistent session)...")

    is_server = (os.name != "nt") and (not os.environ.get("DISPLAY"))
    headless = is_server
    print(f"🖥 რეჟიმი: {'სერვერი — headless=True' if headless else 'PC — headless=False (ბრაუზერი ჩანს)'}")

    # უსაფრთხო ნაგულისხმევი:
    # - Windows ლოკალზე: proxy ყოველთვის OFF (თუ ძალიან არ გინდა ჩართო)
    # - სერვერზე: proxy მხოლოდ მაშინ თუ env-ით ჩართავ
    if os.name == "nt":
        use_proxy = False
    elif USE_PROXY_ENV in ("1", "true", "yes", "on"):
        use_proxy = True
    else:
        use_proxy = False

    proxy = random.choice(PROXIES) if use_proxy else None
    print(f"🔀 Proxy: {proxy['server']}" if proxy else "🔀 Proxy: OFF (direct connection)")
    send_log_msg(
        f"🚀 Checker start | mode={'server' if headless else 'pc'} | proxy={(proxy['server'] if proxy else 'OFF')}",
        force=True
    )

    extra_args = ["--disable-blink-features=AutomationControlled"]
    if is_server:
        extra_args += [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]

    launch_kwargs = dict(
        headless=headless,
        viewport={'width': 1280, 'height': 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        args=extra_args
    )
    if proxy:
        launch_kwargs["proxy"] = proxy

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir,
        **launch_kwargs
    )
    page = context.pages[0] if context.pages else await context.new_page()

    if stealth_func:
        try:
            if inspect.iscoroutinefunction(stealth_func):
                await stealth_func(page)
            else:
                stealth_func(page)
        except:
            pass

    return context, page


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Config ფუნქციები
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_autobook_config():
    if not os.path.exists(AUTOBOOK_FILE):
        default_config = {
            "enabled": False,
            "target_user_id": "",
            "target_cities": ["რუსთავი", "გორი", "თელავი"],
            "button_text": "დაჯავშნა",
            "stop_after_booking": True
        }
        with open(AUTOBOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    try:
        with open(AUTOBOOK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"enabled": False, "target_user_id": "", "button_text": "დაჯავშნა", "stop_after_booking": True}


def get_cities_to_check():
    cities = set()
    autobook_config = get_autobook_config()
    target_user_id = str(autobook_config.get("target_user_id", ""))

    if os.path.exists(FILE_NAME):
        try:
            with open(FILE_NAME, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            for uid, user_cities in users_data.items():
                cities.update(user_cities)
            if autobook_config.get("enabled") and target_user_id in users_data:
                cities.update(users_data[target_user_id])
        except Exception as e:
            print(f"შეცდომა ფაილის წაკითხვისას: {e}")
    return cities


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# შეტყობინებების ფუნქციები
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def send_premium_msg(city, date_val, times_str, is_opening=False):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        if is_opening:
            msg = (
                "🔔 <b>ყურადღება! ჯავშანი გაიხსნა</b>\n"
                "────────────────────\n\n"
                f"🏛 <b>ქალაქი:</b> <code>{city}</code>\n"
                f"📅 <b>თარიღი:</b> <code>{date_val}</code>\n\n"
                "────────────────────\n"
                "🕒 <b>თავისუფალი საათები:</b>\n"
                f"<code>{times_str}</code>\n"
                "────────────────────\n\n"
                "⚡ <b>იჩქარეთ, ადგილები მალე ივსება!</b>"
            )
        else:
            msg = (
                f"🏛 <b>ქალაქი:</b> <code>{city}</code>\n"
                f"📅 <b>თარიღი:</b> <code>{date_val}</code>\n\n"
                "🕒 <b>თავისუფალი საათები:</b>\n"
                f"<code>{times_str}</code>\n\n"
                f"🚀 <a href='https://my.sa.gov.ge'>სასწრაფოდ დაჯავშნა</a>"
            )

        keyboard = {"inline_keyboard": [[{"text": "🚀 სასწრაფოდ დაჯავშნა", "url": "https://my.sa.gov.ge"}]]}

        safe_telegram_post(url, data={
            "chat_id": ADMIN_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }, timeout=10, context="admin-premium")

        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for chat_id in data:
                if city in data[chat_id]:
                    safe_telegram_post(url, data={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(keyboard)
                    }, timeout=10, context=f"user-premium-{chat_id}")
    except:
        pass


def send_booked_msg(city, date_val, time_val):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        msg = (
            "🔴 <b>ადგილი დაიჯავშნა!</b>\n"
            "────────────────────\n\n"
            f"🏛 <b>ქალაქი:</b> <code>{city}</code>\n"
            f"📅 <b>თარიღი:</b> <code>{date_val}</code>\n"
            f"⏰ <b>დრო:</b> <code>{time_val}</code>\n\n"
            "────────────────────\n\n"
            "⏳ <b>ბოტი აგრძელებს ძებნას 24/7 რეჟიმში</b>\n"
            "<i>შეგატყობინებთ როგორც კი ახალი ადგილი გამოჩნდება!</i>"
        )
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for chat_id in data:
                if city in data[chat_id]:
                    safe_telegram_post(url, data={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "HTML"
                    }, timeout=10, context=f"user-booked-{chat_id}")
    except:
        pass


def send_status_report(cities_checked, found_cities):
    global last_report_time
    now = time.time()
    if now - last_report_time < 1200:
        return
    last_report_time = now

    if found_cities:
        status = "✅ <b>ნაპოვნია ჯავშანი!</b>\n" + "\n".join(f"• <code>{c}</code>" for c in found_cities)
    else:
        status = "🔍 <b>ჯავშანი არსად არ არის</b>"

    msg = (
        f"📊 <b>სტატუს რეპორტი</b>\n"
        f"────────────────────\n\n"
        f"{status}\n\n"
        f"────────────────────\n"
        f"🏙 <b>შემოწმებული ქალაქები:</b>\n"
        f"<code>{', '.join(cities_checked)}</code>\n\n"
        f"⏰ <b>დრო:</b> <code>{datetime.datetime.now().strftime('%H:%M:%S')}</code>"
    )
    safe_telegram_post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"},
        timeout=10,
        context="admin-status"
    )


def send_user_reminder():
    global last_reminder_time
    now = time.time()
    if now - last_reminder_time < 3600:
        return
    last_reminder_time = now

    if not os.path.exists(FILE_NAME):
        return
    with open(FILE_NAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for chat_id, cities in data.items():
        if not cities:
            continue
        cities_fmt = "\n".join(f"• <code>{c}</code>" for c in cities)
        msg = (
            "⏳ <b>ძიება მიმდინარეობს...</b>\n"
            "────────────────────\n\n"
            "🤖 ბოტი აქტიურად ეძებს თავისუფალ ადგილს\n\n"
            f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
            "────────────────────\n"
            "🔔 ადგილის გამოჩენისთანავე შეგატყობინებთ!"
        )
        safe_telegram_post(url, data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10, context=f"user-reminder-{chat_id}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# მთავარი checker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def run_checker():
    async with async_playwright() as p:
        print("🌐 ბრაუზერი იხსნება...")
        user_data_dir = os.path.join(os.getcwd(), "user_data")
        context, page = await relaunch_browser_context(p, user_data_dir)
        await safe_goto(page, 'https://my.sa.gov.ge')

        was_available_cities = set()
        cycle_count = 0
        need_navigation = True

        while True:
            try:
                if await confirm_logged_out(page):
                    await wait_for_manual_login(page)
                    need_navigation = True
                    continue

                # ━━━ 1. Keep-alive (ყოველ 12 წუთში) ━━━
                if KEEPALIVE_ENABLED:
                    keepalive_triggered, keepalive_logged_out = await keepalive_agree_click(page)
                    if keepalive_logged_out:
                        # logout-ისას ნუ “ვაწვებით” — ცოტა ხანი დავაცადოთ და მერე ხელით login
                        await asyncio.sleep(random.uniform(LOGOUT_BACKOFF_SECONDS_MIN, LOGOUT_BACKOFF_SECONDS_MAX))
                        await wait_for_manual_login(page)
                        need_navigation = True
                        continue
                    if keepalive_triggered:
                        need_navigation = True

                # ━━━ 2. Config წამოღება ━━━
                autobook_cfg = get_autobook_config()
                priority_cities = autobook_cfg.get("target_cities", ["რუსთავი", "გორი", "თელავი"])
                all_requested = list(get_cities_to_check())

                if not all_requested:
                    print("😴 არცერთი ქალაქი არ არის არჩეული. ველოდები 20 წამი...")
                    await asyncio.sleep(20)
                    continue

                # ━━━ 3. პრიორიტეტული სია ━━━
                others = [c for c in all_requested if c not in priority_cities]
                random.shuffle(others)
                check_list = []
                if priority_cities:
                    if others:
                        for other_city in others:
                            check_list.extend(priority_cities)
                            check_list.append(other_city)
                    else:
                        check_list = list(priority_cities)
                else:
                    check_list = all_requested

                print(f"📡 ვიწყებ სკანირებას ({len(check_list)} წერტილი). პრიორიტეტი: {priority_cities}")

                # ━━━ 4. ნავიგაცია ━━━
                if "DrivingLicensePracticalExams" not in page.url and not need_navigation:
                    need_navigation = True

                cycle_count += 1

                if await confirm_logged_out(page):
                    # logout-ზე სწრაფი retry ხშირად აუარესებს მდგომარეობას
                    await asyncio.sleep(random.uniform(LOGOUT_BACKOFF_SECONDS_MIN, LOGOUT_BACKOFF_SECONDS_MAX))
                    await wait_for_manual_login(page)
                    need_navigation = True
                    continue

                if need_navigation:
                    ok = await safe_goto(page, 'https://my.sa.gov.ge')
                    if not ok:
                        await asyncio.sleep(8)
                        continue
                    await asyncio.sleep(4)
                    await human_scroll(page)

                    practic_btn = page.locator('text=პრაქტიკული გამოცდა').first
                    clicked_practic = await robust_click(page, practic_btn, label="პრაქტიკული გამოცდა")
                    if not clicked_practic:
                        msg = "⚠️ 'პრაქტიკული გამოცდა' ვერ დაიჭირა, ვცდი თავიდან შემდეგ ციკლში"
                        print(msg)
                        send_log_msg(msg)
                        need_navigation = True
                        continue
                    await asyncio.sleep(4)

                    try:
                        await scroll_to_bottom_and_agree(page)
                    except:
                        pass

                    await ensure_b_and_second_stage(page, force=True)
                    need_navigation = False

                # ━━━ 5. ქალაქების შემოწმება ━━━
                current_available_cities = set()

                for city in check_list:
                    city_msg = f"🔎 ვამოწმებ: {city}"
                    print(city_msg)
                    if DEBUG_LOG_EVERY_CITY:
                        send_log_msg(city_msg)
                    await random_idle(page)
                    await anti_bot_break(page)

                    city_dropdown = await wait_city_dropdown(page, timeout=10000)

                    if not city_dropdown:
                        msg = "⚠️ მენიუ დაიკარგა! ვაკეთებ რეფრეშს..."
                        print(msg)
                        send_log_msg(msg)
                        need_navigation = True
                        break

                    clicked_dropdown = await robust_click(page, city_dropdown, label="ქალაქის dropdown")
                    if not clicked_dropdown:
                        msg = "⚠️ dropdown ვერ გაიხსნა, ვაკეთებ რეფრეშს..."
                        print(msg)
                        send_log_msg(msg)
                        need_navigation = True
                        break
                    await asyncio.sleep(0.4)
                    option = page.locator(f'mat-option span.mat-option-text:has-text("{city}")')
                    if not await option.is_visible():
                        await close_overlays(page)
                        continue
                    clicked_option = await robust_click(page, option, label=f"ქალაქი {city}")
                    if not clicked_option:
                        await close_overlays(page)
                        continue
                    await asyncio.sleep(1.2)

                    available_days = page.locator('mat-calendar-body-cell[aria-disabled="false"]')
                    if await available_days.count() > 0:
                        current_available_cities.add(city)
                        day_el = available_days.first
                        date_val = await day_el.get_attribute("aria-label")
                        await human_move_and_click(page, day_el)
                        await asyncio.sleep(0.9)

                        slots = page.locator('button:has-text(":")')
                        times = [await slots.nth(j).inner_text() for j in range(await slots.count())]

                        is_new = city not in was_available_cities
                        send_premium_msg(city, date_val, ", ".join(times), is_opening=is_new)

                        if autobook_cfg.get("enabled") and city in priority_cities and times:
                            try:
                                print(f"⚡ ვცდილობ დაჯავშნას: {city}...")
                                await human_move_and_click(page, slots.first)
                                await asyncio.sleep(1)
                                btn_text = autobook_cfg.get("button_text", "დაჯავშნა")
                                book_btn = page.locator(f'button:has-text("{btn_text}")').first
                                if await book_btn.is_visible():
                                    await human_move_and_click(page, book_btn)
                                    send_booked_msg(city, date_val, times[0])
                                    if autobook_cfg.get("stop_after_booking"):
                                        autobook_cfg["enabled"] = False
                                        with open(AUTOBOOK_FILE, 'w', encoding='utf-8') as f:
                                            json.dump(autobook_cfg, f)
                            except:
                                pass

                        if winsound:
                            winsound.Beep(1000, 500)
                        await close_overlays(page)
                        await asyncio.sleep(1.5)
                    else:
                        await close_overlays(page)

                # ━━━ 6. ციკლის დასრულება ━━━
                was_available_cities = current_available_cities
                send_status_report(list(all_requested), list(current_available_cities))
                send_user_reminder()

                wait = FIXED_CYCLE_WAIT_SECONDS if EXACT_TIMING else random.randint(30, 55)
                next_keepalive = max(0, int(AGREE_INTERVAL_SECONDS - (time.time() - last_agree_click_time)))
                cycle_msg = (
                    f"⌛ ციკლი #{cycle_count} დასრულდა. "
                    f"შემდეგი შემოწმება {wait} წამში... "
                    f"(keep-alive კიდევ {next_keepalive // 60}:{next_keepalive % 60:02d}-ში)"
                )
                print(cycle_msg + "\n")
                send_log_msg(cycle_msg)

                # ნაკლები ნავიგაცია = ნაკლები logout/ფლაკი
                need_navigation = (cycle_count % max(4, NAV_EVERY_N_CYCLES) == 0)

                await asyncio.sleep(wait)

            except Exception as e:
                msg = f"❌ შეცდომა: {e}"
                print(msg)
                send_log_msg(msg, force=True)
                await asyncio.sleep(15)


if __name__ == "__main__":
    asyncio.run(run_checker())