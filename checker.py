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
AGREE_INTERVAL_SECONDS = 9 * 60 # ზუსტად 9 წუთი
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
        
        # თუ მომხმარებელმა დაბლოკა ბოტი (403 Forbidden)
        if resp.status_code == 403:
            chat_id = data.get("chat_id")
            # ადმინს არ ვშლით შემთხვევით
            if chat_id and int(chat_id) != ADMIN_ID:
                remove_user_from_file(chat_id)
            return False

        if resp.status_code != 200:
            return False
            
        payload = resp.json()
        return payload.get("ok", False)
    except Exception:
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
async def human_move_and_click(page, element, label="ელემენტი"):
    try:
        await element.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        
        box = await element.bounding_box()
        if not box:
            await element.click(); return

        target_x = box["x"] + box["width"] / 2
        target_y = box["y"] + box["height"] / 2

        # მაუსის ნელი მოძრაობა (steps=25)
        await page.mouse.move(target_x, target_y, steps=25)
        await asyncio.sleep(0.2)
        await page.mouse.click(target_x, target_y)
        print(f"✅ დავაჭირე: {label}")
    except:
        try: await element.click()
        except: pass

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
# 📜 წესების ბოლომდე სქროლი და დათანხმება
async def handle_agreement(page):
    try:
        modal = page.locator('mat-dialog-container, [role="dialog"], .mat-mdc-dialog-container').first
        
        try:
            await modal.wait_for(state="visible", timeout=10000)
        except:
            print("ℹ️ წესების ფანჯარა არ ჩანს, ვაგრძელებ...")
            return True

        print("📜 წესები გამოჩნდა. ვააქტიურებ ფანჯარას...")
        box = await modal.bounding_box()
        if box:
            center_x = box["x"] + box["width"] / 2
            center_y = box["y"] + box["height"] / 2
            await page.mouse.move(center_x, center_y, steps=10)
            await page.mouse.click(center_x, center_y) 
            await asyncio.sleep(1)

            print("🖱 ვასქროლებ ბოლომდე...")
            for _ in range(12):
                await page.mouse.wheel(0, 500) 
                await asyncio.sleep(0.2)

        # ❗ იძულებითი ლოდინი სქროლის მერე (რომ საიტმა "დაიჯეროს")
        await page.keyboard.press("End")
        await asyncio.sleep(2) 

        agree_btn = page.locator('button:has-text("ვეთანხმები")').first
        
        print("⏳ ველოდები ღილაკის გააქტიურებას...")
        for i in range(15):
            is_disabled = await agree_btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true'")
            
            if not is_disabled and await agree_btn.is_visible():
                print(f"✅ ღილაკი მზადაა (ცდა {i}). ვაჭერ!")
                await human_move_and_click(page, agree_btn, "ვეთანხმები")
                await asyncio.sleep(3)
                # ვამოწმებთ, მართლა გაქრა თუ არა ფანჯარა
                if not await modal.is_visible():
                    return True
            
            await asyncio.sleep(0.5)
            if i % 4 == 0: await page.keyboard.press("End") # კიდევ ერთხელ დავაწვეთ End-ს
            
        return False
    except Exception as e:
        print(f"⚠️ შეცდომა handle_agreement-ში: {e}")
        return False

# ⚙️ კატეგორია B და მეორე ეტაპის არჩევა (მხოლოდ ერთხელ!)
async def setup_category_and_stage(page):
    try:
        print("⚙️ ვაყენებ კატეგორია B-ს და მეორე ეტაპს...")
        # დაველოდოთ რომ გვერდი მზად იყოს წესების მერე
        await asyncio.sleep(2)
        
        cat_drop = page.locator("mat-select").first
        await human_move_and_click(page, cat_drop, "კატეგორიის მენიუ")
        await asyncio.sleep(1.5)
        
        b_option = page.locator('mat-option:has-text("B")').first
        await b_option.wait_for(state="visible", timeout=5000)
        await human_move_and_click(page, b_option, "კატეგორია B")
        await asyncio.sleep(2)
        
        stage_2 = page.locator('text=მეორე ეტაპი').first
        if await stage_2.is_visible():
            await human_move_and_click(page, stage_2, "მეორე ეტაპი")
            await asyncio.sleep(2)
            
        print("✅ ყველაფერი გასწორდა. ვიწყებ ძებნას.")
        return True
    except Exception as e:
        print(f"⚠️ პარამეტრების დაყენებისას მოხდა შეცდომა: {e}")
        return False
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Keep-alive: ყოველ 12 წუთში
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
        current_url = (page.url or "").lower()
        if "drivinglicensepracticalexams" not in current_url:
            ok = await safe_goto(page, 'https://my.sa.gov.ge')
            if not ok:
                last_agree_click_time = time.time()
                return True, False
            await sleep_between(3, 5)

        practic_btn = page.locator('text=პრაქტიკული გამოცდა').first
        if await practic_btn.is_visible():
            await human_move_and_click(page, practic_btn)
            await sleep_between(3, 5)

        # 👈 აი აქ იყო შეცდომა, ახლა გასწორებულია:
        try:
            agreed = await handle_agreement(page)
            if agreed:
                print("✅ Keep-alive: სესია განახლებულია.")
            else:
                print("ℹ️ Keep-alive: 'ვეთანხმები' ვერ დაჭირდა.")
        except Exception as e:
            print(f"⚠️ Keep-alive შეცდომა: {e}")

        last_agree_click_time = time.time()
        return True, False

    except Exception as e:
        print(f"❌ Keep-alive კატასტროფული შეცდომა: {e}")
        last_agree_click_time = time.time()
        return True, False

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


async def ensure_session_ready(page):
    try:
        await ensure_b_and_second_stage(page, force=True)
        await scroll_to_bottom_and_agree(page)
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
    msg = "🔐 ავტორიზაცია საჭიროა! ბრაუზერი ღიაა, გაიარე login/SMS კოდი. ბოტი თავისით გააგრძელებს, როგორც კი შეხვალ."
    print(msg)
    send_log_msg(msg, force=True)
    
    while True:
        try:
            # თუ გვერდი დახურულია, ეს ფუნქცია შეჩერდება და run_checker გადატვირთავს
            if page.is_closed():
                return
                
            await asyncio.sleep(5)
            # ვამოწმებთ, ისევ გამოსულია თუ არა
            is_out = await confirm_logged_out(page)
            if not is_out:
                ok_msg = "✅ ავტორიზაცია დაფიქსირდა! ვაგრძელებ მუშაობას..."
                print(ok_msg)
                send_log_msg(ok_msg, force=True)
                await asyncio.sleep(2)
                return
        except:
            return # შეცდომისას გამოვდივართ, რომ run_checker-მა გადატვირთოს
            
async def inject_click_visualizer(page):
    await page.add_init_script("""
        window.addEventListener('mousedown', e => {
            const div = document.createElement('div');
            div.style.position = 'fixed';
            div.style.left = e.clientX - 10 + 'px';
            div.style.top = e.clientY - 10 + 'px';
            div.style.width = '20px';
            div.style.height = '20px';
            div.style.borderRadius = '50%';
            div.style.backgroundColor = 'rgba(255, 0, 0, 0.8)';
            div.style.zIndex = '999999';
            div.style.pointerEvents = 'none';
            document.body.appendChild(div);
            setTimeout(() => div.remove(), 600);
        }, true);
    """)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ბრაუზერის გაშვება
# PC (Windows/Mac):  headless=False — ბრაუზერი ჩანს
# სერვერი (Ubuntu):  headless=True  — DISPLAY არ არის
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def relaunch_browser_context(playwright, user_data_dir):
    print("🌐 ვტვირთავ ბრაუზერს (persistent session)...")

    # დარწმუნდით, რომ user_data დირექტორია არსებობს, შენდება სეიშენები.
    os.makedirs(user_data_dir, exist_ok=True)

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
        slow_mo=80,
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
            "target_only": False,
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


def build_check_sequence(priority_cities, all_cities):
    """მოცემული პრიორიტეტული ქალაქების იატლი ორიენტირებული გამეორება და დანარჩენების ჩასმა."""
    if not all_cities:
        return []

    priority = [c for c in priority_cities if c in all_cities]
    others = [c for c in all_cities if c not in priority]
    if not priority:
        return list(all_cities)

    sequence = []
    for idx in range(max(len(others), 1)):
        for p in priority:
            sequence.append(p)
        if idx < len(others):
            sequence.append(others[idx])

    return sequence


def get_cycle_wait_seconds(cycle_count):
    if EXACT_TIMING:
        return FIXED_CYCLE_WAIT_SECONDS

    # ღამის რეჟიმში (02:00 - 08:00) ისევ დავტოვოთ გრძელი პაუზა უსაფრთხოებისთვის
    if is_night_maintenance():
        return random.randint(150, 300)

    # დღის რეჟიმში: 25-დან 45 წამამდე პაუზა (იდეალურია)
    return random.randint(25, 45)

def is_night_maintenance():
    h = datetime.datetime.now().hour
    return 2 <= h < 8


async def is_block_or_captcha(page):
    try:
        url = (page.url or "").lower()
        # ვამოწმებთ მხოლოდ URL-ს, სადაც წერია ხოლმე captcha ან blocked
        if any(k in url for k in ["captcha", "blocked", "access-denied"]):
            return True
            
        # ვამოწმებთ მხოლოდ ხილულ ტექსტს და არა მთლიან კოდს
        content = await page.inner_text("body")
        content = content.lower()
        
        # ვეძებთ კონკრეტულ ფრაზებს, რომლებსაც საიტი გვიწერს ბლოკისას
        bad_phrases = ["your ip is blocked", "access denied", "too many requests"]
        if any(p in content for p in bad_phrases):
            return True
    except:
        pass
    return False


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
        print("🌐 Opening Browser...")
        user_data_dir = os.path.join(os.getcwd(), "user_data")
        context, page = await relaunch_browser_context(p, user_data_dir)
        await safe_goto(page, 'https://my.sa.gov.ge')

        was_available_cities = set()
        cycle_count = 0
        need_navigation = True

        while True:
            try:
                # თუ გაშვებული page შემთხვევით დაიხურა, თავიდან ვიწყებთ აღდგენას
                if page.is_closed():
                    print("🔁 Page დახურულია, რე-ლოგინ/რესეტზე ვცდები...")
                    try:
                        await context.close()
                    except:
                        pass
                    context, page = await relaunch_browser_context(p, user_data_dir)
                    await safe_goto(page, 'https://my.sa.gov.ge')
                    need_navigation = True
                    continue

                # 1. 🔍 სესიის პირველადი შემოწმება - თუ Logout-ია, მაშინვე ვჩერდებით
                if await is_logged_out(page):
                    print("🔒  Session Expired!")
                    await wait_for_manual_login(page)
                    need_navigation = True
                    continue


                # ━━━ 2. ბლოკის ან კაპტჩის შემოწმება ━━━
                if await is_block_or_captcha(page):
                    msg = "⚠️ ბლოკი/კაფტჩა გამოვლინდა, ველოდებით..."
                    print(msg); send_log_msg(msg, force=True)
                    need_navigation = True
                    await asyncio.sleep(random.uniform(45, 80))
                    continue

                # ━━━ 3. ღამის რეჟიმი (02:00-08:00) ━━━
                if is_night_maintenance():
                    print("🌙 ღამის რეჟიმი: ბოტი ისვენებს...")
                    if KEEPALIVE_ENABLED:
                        await keepalive_agree_click(page)
                    await asyncio.sleep(random.uniform(120, 180))
                    continue

                # ━━━ 4. Keep-alive (ყოველ 12 წუთში) ━━━
                if KEEPALIVE_ENABLED:
                    keep_trig, keep_out = await keepalive_agree_click(page)
                    if keep_out:
                        await wait_for_manual_login(page)
                        need_navigation = True
                        continue
                    if keep_trig:
                        need_navigation = True

               # ━━━ 5. ნავიგაცია და მომზადება ━━━
                if need_navigation:
                    print("🚀 ვაკეთებ სესიის სრულ გაცოცხლებას (Hard Refresh)...")
                    # გადავდივართ მთავარზე
                    await page.goto('https://my.sa.gov.ge', wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    
                    # შევდივართ პრაქტიკულებზე
                    practic_btn = page.locator('text=პრაქტიკული გამოცდა').first
                    await human_move_and_click(page, practic_btn, "პრაქტიკული გამოცდა")
                    await asyncio.sleep(3)
                    
                    # წესებზე დათანხმება
                    if await handle_agreement(page):
                        await setup_category_and_stage(page)
                        need_navigation = False
                        last_agree_click_time = time.time() # 👈 ტაიმერი აქ ნულდება
                        print("✅ სესია განახლებულია 7 წუთით!")
                    else:
                        print("⚠️ რეფრეში ვერ მოხერხდა, ვცდი თავიდან...")
                        continue

                # ❗ დამატებითი დაზღვევა: თუ წესები მაინც ამოხტა (თუნდაც need_navigation False იყოს)
                modal_visible = await page.locator(".mat-mdc-dialog-content, mat-dialog-content").first.is_visible()
                if modal_visible:
                    print("🚨 წესების ფანჯარა მოულოდნელად გამოჩნდა! ვასწორებ...")
                    await handle_agreement(page)
                    await setup_category_and_stage(page)

                # ━━━ 6. ქალაქების სიის მომზადება ━━━
                autobook_cfg = get_autobook_config()
                all_requested = list(get_cities_to_check())
                priority_cities = autobook_cfg.get("target_cities", ["თელავი", "რუსთავი"])
                
                check_list = build_check_sequence(priority_cities, all_requested)
                if not check_list: check_list = list(all_requested)

                print(f"📡 სკანირება: {priority_cities} + სხვები")

                # ━━━ 7. ქალაქების შემოწმება ━━━
                current_available_cities = set()

                # ━━━ 5. ქალაქების შემოწმება ━━━
                for city in check_list:
                    # ❗ აი ეს დაიცავს სესიას სიკვდილისგან:
                    if time.time() - last_agree_click_time > AGREE_INTERVAL_SECONDS:
                        print(f"🚨 9 წუთი გავიდა! ვაჩერებ ძებნას და ვაახლებ სესიას...")
                        need_navigation = True
                        break # წყვეტს ძებნას და მიდის ზემოთ რეფრეშზ

                    # შემოწმება თუ მაინც ამოაგდო (უსაფრთხოებისთვის)
                    if await is_logged_out(page):
                        need_navigation = True
                        break 

                    print(f"🔎 Checking: {city}")

                    dropdowns = page.locator("mat-select")
                    city_dropdown = None
                    
                    # ვეძებთ მენიუს მაქსიმუმ 5 წამი
                    try:
                        count = await dropdowns.count()
                        for k in range(count):
                            pl = await dropdowns.nth(k).get_attribute("placeholder")
                            if pl and "საგამოცდო ცენტრი" in pl:
                                city_dropdown = dropdowns.nth(k); break
                    except: pass

                    if not city_dropdown:
                        # ❗ თუ მენიუ ვერ იპოვა, ე.ი. სესია მოკვდა
                        print("⚠️ მენიუ ვერ მოიძებნა! ვამოწმებ სესიას...")
                        if await is_logged_out(page):
                            print("🔒 სესია ნამდვილად გაწყდა. გადავდივარ აღდგენაზე.")
                            need_navigation = True
                            break
                        else:
                            # თუ სესია ცოცხალია, უბრალოდ გვერდი გაიჭედა
                            print("🔄 გვერდი გაიჭედა, ვაკეთებ რეფრეშს...")
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

                    await sleep_between(1.8, 2.4)
                    if random.random() < 0.2:
                        await human_scroll(page)
                    await sleep_between(0.7, 1.2)

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
                
                wait = get_cycle_wait_seconds(cycle_count)
                
                # რეფრეშამდე დარჩენილი დროის გამოთვლა
                time_passed = time.time() - last_agree_click_time
                next_keepalive = max(0, int(AGREE_INTERVAL_SECONDS - time_passed))
                
                cycle_msg = (
                    f"⌛ Cycle #{cycle_count} finished. "
                    f"შემდეგი შემოწმება {wait} წამში... "
                    f"(რეფრეში დარჩა {next_keepalive // 60}:{next_keepalive % 60:02d})"
                )
                print(cycle_msg + "\n")
                send_log_msg(cycle_msg)

                need_navigation = False 
                await asyncio.sleep(wait)

            except Exception as e:
                msg = f"❌ შეცდომა ციკლში: {e}"
                print(msg)
                send_log_msg(msg, force=True)
                await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(run_checker())