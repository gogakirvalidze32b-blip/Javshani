import asyncio
import random
import requests
import json
import os
import time
import datetime
import inspect
import re
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
BOOKING_DIRECT_URL = os.getenv("BOOKING_DIRECT_URL", "https://my.sa.gov.ge/home/DrivingLicensePracticalExams")
LOGIN_URL = os.getenv("LOGIN_URL", "https://my.sa.gov.ge/auth")
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0") or 0)
DEBUG_TO_LOG_CHAT = os.getenv("DEBUG_TO_LOG_CHAT", "1") == "1"
DEBUG_LOG_EVERY_CITY = os.getenv("DEBUG_LOG_EVERY_CITY", "0") == "1"
EXACT_TIMING = os.getenv("EXACT_TIMING", "0") == "1"
FIXED_CYCLE_WAIT_SECONDS = int(os.getenv("FIXED_CYCLE_WAIT_SECONDS", "30") or 30)
USE_PROXY_ENV = os.getenv("USE_PROXY", "").strip().lower()
FORCE_SEND_ON_START = os.getenv("FORCE_SEND_ON_START", "0") == "1"
FILE_NAME = "users.json"
AUTOBOOK_FILE = "autobook.json"
SEEN_SLOTS_FILE = os.getenv("SEEN_SLOTS_FILE", "seen_slots.json")
last_report_time = 0
last_reminder_time = 0
MANUAL_LOGIN_GRACE_SECONDS = 300
LOGOUT_SPAM_INTERVAL_SECONDS = int(os.getenv("LOGOUT_SPAM_INTERVAL_SECONDS", "30") or 30)
_last_logout_signal_time = 0.0

# autobook Telegram: full = ადმინს ყველა ეტაპი | errors_only = ადმინს მხოლოდ error/success
AUTOBOOK_TG_ADMIN_MODE = os.getenv("AUTOBOOK_TG_ADMIN_MODE", "full").strip().lower()
# დაჯავშნის ნაბიჯებს შორის დროის გამრავლებელი (სერვერის ლოკის შემცირება)
AUTOBOOK_SOFT = float(os.getenv("AUTOBOOK_SOFT_MULTIPLIER", "1.7") or 1.7)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SEEN_SLOTS: city -> date -> {
#   "times": set(),          — ნანახი საათები
#   "last_sent": float,      — ბოლო გაგზავნის unix time
# }
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEEN_SLOTS: dict = {}
RESEND_INTERVAL = int(os.getenv("RESEND_INTERVAL_SECONDS", str(2 * 3600)) or (2 * 3600))  # default 2 საათი
# სწრაფი სკანის შეტყობინებაში (მხოლოდ თარიღები) — SEEN_SLOTS-ში პლეისჰოლდერი
DATE_QUICK_MARKER = "■dates_only■"

# თარიღების რაოდენობა, რომლის ზემოთაც დეტალები document-ად იგზავნება (Telegram ტექსტის ლიმიტი)
TG_DATES_FILE_THRESHOLD = int(os.getenv("TG_DATES_FILE_THRESHOLD", "5") or 5)
# „არაფერი ახალი“ სტატუს-რეპორტის მინიმალური ინტერვალი (წამი) — ნაგულისხმევი 2 საათი
STATUS_REPORT_INTERVAL = int(os.getenv("STATUS_REPORT_INTERVAL_SECONDS", str(2 * 3600)) or (2 * 3600))
# მომხმარებლისთვის სტატუსი/რემაინდერი არაა სასურველი ამ საათებში (ადგილობრივი დრო)
USER_QUIET_HOURS_START = int(os.getenv("USER_QUIET_HOURS_START", "2") or 2)
USER_QUIET_HOURS_END = int(os.getenv("USER_QUIET_HOURS_END", "8") or 8)

# ქალაქები რომელთაც ახლა თავისუფალი სლოტი აქვს — პრიორიტეტი დაბლა
_cities_with_slots: set = set()
_force_sent_cities: set = set()


def load_seen_slots():
    global SEEN_SLOTS, _cities_with_slots
    try:
        if not os.path.exists(SEEN_SLOTS_FILE):
            return
        with open(SEEN_SLOTS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # raw: city -> date -> {times: [...], last_sent: float}
        seen = {}
        cities_with = set()
        for city, dates in (raw or {}).items():
            if not isinstance(dates, dict):
                continue
            seen[city] = {}
            for date_val, v in dates.items():
                if not isinstance(v, dict):
                    continue
                times = set(v.get("times") or [])
                last_sent = float(v.get("last_sent") or 0.0)
                seen[city][date_val] = {"times": times, "last_sent": last_sent}
                if times:
                    cities_with.add(city)
        SEEN_SLOTS = seen
        _cities_with_slots = cities_with
    except Exception as e:
        print(f"⚠️ load_seen_slots: {e}")


def save_seen_slots():
    try:
        payload = {}
        for city, dates in (SEEN_SLOTS or {}).items():
            payload[city] = {}
            for date_val, v in (dates or {}).items():
                payload[city][date_val] = {
                    "times": sorted(list(v.get("times") or [])),
                    "last_sent": float(v.get("last_sent") or 0.0),
                }
        with open(SEEN_SLOTS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ save_seen_slots: {e}")

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

CITIES_LIST = [
    "რუსთავი", "გორი", "ქუთაისი", "ბათუმი", "ფოთი",
    "თელავი", "ახალციხე", "ოზურგეთი", "ზუგდიდი", "საჩხერე", "ამბროლაური"
]

last_agree_click_time = 0
# ბოლო წარმატებული „სრული“ ნავიგაცია პრაქტიკულზე (SESSION_FORCE_NAV-ისთვის)
last_hard_navigation_time = 0.0
# keepalive / ციკლში რეფრეშის ინტერვალი წამებში (ნაგულისხმევი 9 წთ, min 2 წთ, max 20 წთ)
AGREE_INTERVAL_SECONDS = max(
    300,
    min(1200, int(os.getenv("AGREE_INTERVAL_SECONDS", str(random.randint(5, 8) * 60)) or (6 * 60))),
)
# 0 = გამორთული. მაგ. 3300 ≈ 55 წთ — იძულებით სრული გვერდის განახლება სერვერის JWT-მდე
SESSION_FORCE_NAV_SECONDS = int(os.getenv("SESSION_FORCE_NAV_SECONDS", "0") or 0)
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
        if resp.status_code == 403:
            chat_id = data.get("chat_id")
            if chat_id and int(chat_id) != ADMIN_ID:
                remove_user_from_file(chat_id)
            return False
        if resp.status_code != 200:
            return False
        payload = resp.json()
        return payload.get("ok", False)
    except Exception:
        return False


def is_user_quiet_hours(when: datetime.datetime | None = None) -> bool:
    dt = when or datetime.datetime.now()
    return USER_QUIET_HOURS_START <= dt.hour < USER_QUIET_HOURS_END


def safe_telegram_send_document(
    chat_id,
    filename: str,
    content: bytes,
    caption_html: str | None = None,
    reply_markup_json: str | None = None,
    timeout=60,
    context="telegram-doc",
):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    try:
        files = {"document": (filename, content, "text/plain; charset=utf-8")}
        data = {"chat_id": str(chat_id)}
        if caption_html:
            data["caption"] = caption_html[:1024]
            data["parse_mode"] = "HTML"
        if reply_markup_json:
            data["reply_markup"] = reply_markup_json
        resp = requests.post(url, data=data, files=files, timeout=timeout)
        if resp.status_code == 403:
            if int(chat_id) != ADMIN_ID:
                remove_user_from_file(chat_id)
            return False
        if resp.status_code != 200:
            return False
        return bool(resp.json().get("ok"))
    except Exception:
        return False


def _slot_time_needle(raw_slot: str) -> str:
    m = re.search(r"\d{1,2}:\d{2}", raw_slot or "")
    return m.group(0) if m else (raw_slot or "").strip()[:16]


def remove_user_from_file(chat_id):
    try:
        if not os.path.exists(FILE_NAME):
            return
        with open(FILE_NAME, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if str(chat_id) in data:
            del data[str(chat_id)]
            with open(FILE_NAME, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"🗑 მომხმარებელი {chat_id} წაიშალა (ბოტი დაბლოკა)")
    except Exception as e:
        print(f"⚠️ remove_user_from_file: {e}")


def send_log_msg(text, force=False):
    if not LOG_CHAT_ID:
        return False
    if not DEBUG_TO_LOG_CHAT and not force:
        return False
    return safe_telegram_post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": LOG_CHAT_ID, "text": text},
        timeout=10,
        context="debug-log"
    )


def _ab_delay(base: float) -> float:
    return max(0.15, float(base) * AUTOBOOK_SOFT)


def send_autobook_notify(autobook_cfg: dict, html: str, kind: str):
    """
    kind: progress | success | error — target_user_id + ადმინი (განმეორება არა იმავე chat-ზე).
    AUTOBOOK_TG_ADMIN_MODE=errors_only → ადმინს მხოლოდ success/error.
    """
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    uid = str(autobook_cfg.get("target_user_id") or "").strip()
    send_admin = AUTOBOOK_TG_ADMIN_MODE == "full" or kind in ("success", "error")

    recipients = []
    if uid and str(uid).isdigit():
        recipients.append(int(uid))
    if send_admin and ADMIN_ID not in recipients:
        recipients.append(ADMIN_ID)

    for cid in recipients:
        safe_telegram_post(
            url,
            data={"chat_id": cid, "text": html, "parse_mode": "HTML"},
            context=f"autobook-{kind}",
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
    print(f"❌ navigate ვერ შესრულდა: {last_exc}")
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ადამიანური მოძრაობის ფუნქციები (სწორი ხაზის ნაცვლად — ოდნავ მოხვეული გზა, ჯიტერი, ცვლადი ტემპი)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _pick_click_point_in_box(box: dict) -> tuple[float, float]:
    """ცენტრის ნაცვლად — შიდა ზონიდან შემთხვევითი წერტილი (არა ყოველთვის იგივე პიქსელი)."""
    w, h = box["width"], box["height"]
    if w < 3 or h < 3:
        return box["x"] + w / 2, box["y"] + h / 2
    mx = min(max(w * 0.12, 4), w * 0.35)
    my = min(max(h * 0.12, 3), h * 0.35)
    tx = box["x"] + mx + random.random() * max(w - 2 * mx, 1)
    ty = box["y"] + my + random.random() * max(h - 2 * my, 1)
    return tx, ty


async def _human_path_move(page, x: float, y: float):
    """1–2 შუალედური წერტილი — უფრო ბუნებრივი ტრაექტორია ვიდრე ერთი სწორი ხაზი."""
    try:
        vp = page.viewport_size
        vw = float(vp["width"]) if vp else 1280.0
        vh = float(vp["height"]) if vp else 800.0
    except Exception:
        vw, vh = 1280.0, 800.0
    # „საწყისი“ უხეშად — ეკრანის ცენტრის ირგვლივ (ბოლო მაუსის პოზიცია არ ვიცით)
    sx = random.uniform(vw * 0.2, vw * 0.8)
    sy = random.uniform(vh * 0.2, vh * 0.8)
    if random.random() < 0.72:
        wx = sx + (x - sx) * random.uniform(0.35, 0.65) + random.uniform(-35, 35)
        wy = sy + (y - sy) * random.uniform(0.35, 0.65) + random.uniform(-28, 28)
        wx = max(2, min(vw - 2, wx))
        wy = max(2, min(vh - 2, wy))
        await page.mouse.move(wx, wy, steps=random.randint(14, 28))
        await sleep_between(0.04, 0.16)
    await page.mouse.move(x, y, steps=random.randint(22, 52))
    await sleep_between(0.06, 0.32)
    if random.random() < 0.45:
        jx = x + random.uniform(-2.5, 2.5)
        jy = y + random.uniform(-2.5, 2.5)
        await page.mouse.move(jx, jy, steps=random.randint(2, 5))
        await sleep_between(0.02, 0.09)


async def human_move_and_click(page, element, label="ელემენტი"):
    try:
        await element.scroll_into_view_if_needed()
        await sleep_between(0.06, 0.2)
        await sleep_between(0.2, 0.65)
        box = await element.bounding_box()
        if not box:
            await element.click()
            return
        target_x, target_y = _pick_click_point_in_box(box)
        await _human_path_move(page, target_x, target_y)
        await page.mouse.click(target_x, target_y, delay=random.randint(35, 120))
        print(f"✅ დავაჭირე: {label}")
    except:
        try:
            await element.click()
        except:
            pass


async def close_overlays(page):
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


async def wait_category_dropdown(page, timeout=10000):
    end_at = time.time() + (timeout / 1000)
    while time.time() < end_at:
        try:
            dropdowns = page.locator("mat-select")
            count = await dropdowns.count()
            for k in range(count):
                pl = await dropdowns.nth(k).get_attribute("placeholder")
                if pl and "კატეგორი" in pl:
                    return dropdowns.nth(k)
        except:
            pass
        await asyncio.sleep(0.25)
    return None


async def detect_practical_booking_lock_message(page) -> str | None:
    """
    სერვერი (ზოგჯერ მთავარი გვერდის banner-ზე): „მითითებულ პირად ნომერზე მიმდინარეობს დაჯავშნა“ —
    პირად ნომერზე დროებითი ლოკი; ამ დროს B/ფორმა ხშირად არ მუშაობს. არ ნიშნავს SMS-ზე დადასტურებულ ჯავშანს.
    """
    try:
        raw = await page.inner_text("body", timeout=8000)
        txt = raw.lower()
    except Exception:
        return None
    # უფრო სპეციფიკური ფრაზები პირველად (სკრინშოტიდან)
    needles = (
        "მითითებულ პირად ნომერზე მიმდინარეობს დაჯავშნა",
        "პირად ნომერზე მიმდინარეობს დაჯავშნა",
        "მიმდინარეობს დაჯავშნა",
        "დაჯავშნა მიმდინარეობს",
        "ჯავშნის პროცესი",
        "დაჯავშნის პროცესი",
        "სცადეთ ერთი საათ",
        "სცადეთ 1 საათ",
        "1 საათის შემდეგ",
        "ერთი საათის შემდეგ",
        "საათის შემდეგ სცადეთ",
    )
    for n in needles:
        if n in txt:
            return n
    return None


async def find_category_mat_select(page, timeout=12000):
    """კატეგორიის mat-select — placeholder ან პირველი არა-ქალაქ/თარიღ/დრო ველი."""
    end_at = time.time() + (timeout / 1000)
    while time.time() < end_at:
        try:
            dropdowns = page.locator("mat-select")
            count = await dropdowns.count()
            for k in range(count):
                pl = (await dropdowns.nth(k).get_attribute("placeholder")) or ""
                if "კატეგორი" in pl:
                    return dropdowns.nth(k)
            for k in range(count):
                pl = (await dropdowns.nth(k).get_attribute("placeholder")) or ""
                if any(x in pl for x in ("საგამოცდო", "თარიღი", "დრო")):
                    continue
                if pl.strip():
                    return dropdowns.nth(k)
            if count >= 1:
                pl0 = (await dropdowns.nth(0).get_attribute("placeholder")) or ""
                if "საგამოცდო" not in pl0 and "თარიღი" not in pl0 and "დრო" not in pl0:
                    return dropdowns.nth(0)
        except Exception:
            pass
        await asyncio.sleep(0.25)
    return None


async def pick_category_b_mat_option(page):
    order = [
        page.locator("mat-option").filter(has_text=re.compile(r"B\s*კატეგორია", re.I)).first,
        page.locator("mat-option").filter(has_text=re.compile(r"კატეგორია\s*B\b", re.I)).first,
        page.locator("mat-option").filter(has_text="B კატეგორია").first,
    ]
    for loc in order:
        try:
            if await loc.is_visible(timeout=2000):
                return loc
        except Exception:
            continue
    return None


async def find_mat_select_by_placeholder(page, keyword: str):
    """
    keyword: ნაწყვეტი placeholder-იდან (მაგ: 'თარიღი', 'დრო', 'საგამოცდო ცენტრი')
    """
    try:
        selects = page.locator("mat-select")
        count = await selects.count()
        for i in range(count):
            ph = await selects.nth(i).get_attribute("placeholder")
            if ph and keyword in ph:
                return selects.nth(i)
    except:
        pass
    return None


async def _overlay_scroll_step(page):
    try:
        await page.evaluate(
            """() => {
                const p = document.querySelector(
                    '.cdk-overlay-pane .mat-mdc-select-panel, .mat-select-panel, .mat-mdc-select-panel'
                );
                if (p) p.scrollTop = Math.min(p.scrollTop + Math.floor(p.clientHeight * 0.9), p.scrollHeight);
            }"""
        )
    except Exception:
        pass


def _is_dd_mm_yyyy_text(s: str) -> bool:
    return bool(re.search(r"\d{1,2}-\d{1,2}-\d{4}", (s or "").strip()))


def _parse_dd_mm_yyyy(date_str: str):
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})", date_str or "")
    if not m:
        return None
    try:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime.date(y, mo, d)
    except Exception:
        return None


async def collect_available_dates_quick(page, autobook_cfg: dict):
    """
    ერთი გახსნით აგროვებს თარიღის ვარიანტებს (overlay-ში scroll) — საათებს არ ხსნის.
    """
    date_dropdown = await find_mat_select_by_placeholder(page, "თარიღი")
    if not date_dropdown:
        return []

    if not await robust_click(page, date_dropdown, label="თარიღის მენიუ (სწრაფი)"):
        return []
    await asyncio.sleep(0.35)

    seen = set()
    last_size = -1
    stable = 0
    for _ in range(36):
        opts = page.locator("mat-option")
        cnt = await opts.count()
        for i in range(cnt):
            try:
                txt = (await opts.nth(i).inner_text()).strip()
                if txt and _is_dd_mm_yyyy_text(txt) and "გასუფთავება" not in txt:
                    seen.add(txt)
            except Exception:
                continue
        await _overlay_scroll_step(page)
        await asyncio.sleep(0.12)
        if len(seen) == last_size:
            stable += 1
            if stable >= 5:
                break
        else:
            stable = 0
        last_size = len(seen)

    await page.keyboard.press("Escape")
    await asyncio.sleep(0.2)

    dates = sorted(seen, key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d))
    target_dates = [d.strip() for d in (autobook_cfg.get("target_dates") or []) if str(d).strip()]
    if target_dates:
        dates = [d for d in dates if any(td in d for td in target_dates)]
    target_months = [m.strip().zfill(2) for m in (autobook_cfg.get("target_months") or []) if str(m).strip()]
    if target_months:
        mf = []
        for d in dates:
            parsed = _parse_dd_mm_yyyy(d)
            if parsed and f"{parsed.month:02d}" in target_months:
                mf.append(d)
        dates = mf
    return dates


async def collect_all_dates_and_times(
    page,
    autobook_cfg: dict,
    fast: bool = False,
    restrict_to_dates: list | None = None,
):
    """
    აბრუნებს list[tuple(date_str, list[times_raw], list[valid_time_locators])]
    times_raw: ის ტექსტებია რაც dropdown-ში ჩანს (მაგ "10:35 (250 ლარი)" ან "09:45")
    restrict_to_dates: თუ მითითებულია, საათებს მხოლოდ ამ თარიღ(ებ)ზე იკითხავს.
    """
    results = []
    open_wait = 0.4 if fast else 1.0
    between_wait = 0.45 if fast else 0.8
    after_date_wait = 0.65 if fast else 1.4
    time_menu_wait = 0.55 if fast else 1.0
    close_wait = 0.2 if fast else 0.35

    date_dropdown = await find_mat_select_by_placeholder(page, "თარიღი")
    if not date_dropdown:
        return results

    # გახსენი თარიღების dropdown და ამოიღე ყველა ვარიანტი
    if not await robust_click(page, date_dropdown, label="თარიღის მენიუ"):
        return results
    await asyncio.sleep(open_wait)

    date_options = page.locator("mat-option")
    seen_dates = set()
    last_sz = -1
    stable = 0
    for _ in range(40):
        nopts = await date_options.count()
        for i in range(nopts):
            try:
                txt = (await date_options.nth(i).inner_text()).strip()
                if txt and _is_dd_mm_yyyy_text(txt) and "გასუფთავება" not in txt:
                    seen_dates.add(txt)
            except Exception:
                continue
        await _overlay_scroll_step(page)
        await asyncio.sleep(0.1 if fast else 0.15)
        if len(seen_dates) == last_sz:
            stable += 1
            if stable >= (4 if fast else 5):
                break
        else:
            stable = 0
        last_sz = len(seen_dates)

    if not seen_dates:
        await page.keyboard.press("Escape")
        return results

    dates = sorted(seen_dates, key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d))

    # დახურე dropdown სანამ ციკლში შევალთ (მერე თავიდან გავხსნით)
    await page.keyboard.press("Escape")
    await asyncio.sleep(close_wait)

    # optional filters from autobook config
    target_dates = [d.strip() for d in (autobook_cfg.get("target_dates") or []) if str(d).strip()]
    if target_dates:
        dates = [d for d in dates if any(td in d for td in target_dates)]
    target_months = [m.strip().zfill(2) for m in (autobook_cfg.get("target_months") or []) if str(m).strip()]
    if target_months:
        month_filtered = []
        for d in dates:
            parsed = _parse_dd_mm_yyyy(d)
            if parsed and f"{parsed.month:02d}" in target_months:
                month_filtered.append(d)
        dates = month_filtered

    if restrict_to_dates:
        allow = {str(x).strip() for x in restrict_to_dates if str(x).strip()}
        dates = [d for d in dates if d in allow]

    for date_val in dates:
        # გახსენი და აირჩიე კონკრეტული თარიღი
        date_dropdown = await find_mat_select_by_placeholder(page, "თარიღი")
        if not date_dropdown:
            break
        await robust_click(page, date_dropdown, label=f"თარიღის მენიუ ({date_val})")
        await asyncio.sleep(between_wait)

        target_date_opt = page.locator("mat-option").filter(has_text=date_val).first
        if not await target_date_opt.is_visible():
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.25)
            continue

        await robust_click(page, target_date_opt, label=f"თარიღი {date_val}")
        await asyncio.sleep(after_date_wait)

        # Time dropdown ხშირად ქვემოთაა — ვასკროლოთ და მერე დავაჭიროთ
        time_dropdown = await find_mat_select_by_placeholder(page, "დრო")
        if not time_dropdown:
            continue
        try:
            await time_dropdown.scroll_into_view_if_needed()
        except Exception:
            pass
        if not fast:
            await human_scroll(page)

        if not await robust_click(page, time_dropdown, label="დროის მენიუ"):
            await close_overlays(page)
            continue
        await asyncio.sleep(time_menu_wait)

        time_options = page.locator("mat-option")
        time_count = await time_options.count()
        times = []
        valid_slot_locators = []
        for t_idx in range(time_count):
            try:
                t_text = (await time_options.nth(t_idx).inner_text()).strip()
            except Exception:
                continue
            # 'გასუფთავება' მსგავს ელემენტებს ვაცილებთ
            if not t_text or "გასუფთავება" in t_text:
                continue
            if re.search(r"\d{1,2}:\d{2}", t_text):
                times.append(t_text)
                valid_slot_locators.append(time_options.nth(t_idx))

        # dropdown დახურე (შემდეგ თარიღზე გადასასვლელად)
        await page.keyboard.press("Escape")
        await asyncio.sleep(close_wait)

        # ფასებზე/საათებზე ფილტრები აქ, რომ შედეგი ერთნაირად წავიდეს send_premium_msg-ში
        target_prices = autobook_cfg.get("target_prices", [])
        if target_prices:
            filtered = [t for t in times if any(p in t for p in target_prices)]
            if filtered:
                times = filtered

        target_hours = [h.strip() for h in (autobook_cfg.get("target_hours") or []) if str(h).strip()]
        if target_hours:
            filtered_hours = [t for t in times if any(h in t for h in target_hours)]
            if filtered_hours:
                times = filtered_hours
        results.append((date_val, times, valid_slot_locators))

    return results


async def robust_click(page, locator, label="element"):
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
            except Exception:
                await close_overlays(page)
                await asyncio.sleep(0.3 * attempt)
    return False


async def click_book_button(page, button_substring: str, *, gentle: bool = False) -> bool:
    """
    დაჯავშნა ხშირად span-შია ან disabled იქნება საათამდე — რამდენიმე სელექტორი და retry.
    gentle=True: ნაკლები რაუნდი/უფრო ნელი — სერვერის ლოკის შესამცირებლად.
    """
    raw = (button_substring or "დაჯავშნა").strip()
    needle = raw[:6] if len(raw) >= 3 else raw
    pat = re.compile(re.escape(needle), re.IGNORECASE)
    outer_max = 2 if gentle else 3
    dis_waits = 5 if gentle else 8
    dis_pause = 0.55 if gentle else 0.35

    async def try_click(loc) -> bool:
        try:
            await loc.wait_for(state="visible", timeout=6000)
        except Exception:
            return False
        try:
            await loc.scroll_into_view_if_needed()
        except Exception:
            pass
        await asyncio.sleep(0.35 if gentle else 0.2)
        for _ in range(dis_waits):
            try:
                dis = await loc.evaluate(
                    "el => el.disabled || el.getAttribute('aria-disabled') === 'true'"
                )
            except Exception:
                dis = True
            if not dis:
                await human_move_and_click(page, loc, raw)
                return True
            await asyncio.sleep(dis_pause)
        if not gentle:
            try:
                await loc.click(force=True, timeout=3000)
                print(f"✅ დავაჭირე (force): {raw}")
                return True
            except Exception:
                pass
        return False

    order = [
        page.get_by_role("button", name=pat),
        page.locator(f"button:has-text('{raw}')"),
        page.locator("button").filter(has_text=pat),
    ]
    for attempt in range(1, outer_max + 1):
        for variant in order:
            try:
                loc = variant.first
                if await try_click(loc):
                    return True
            except Exception:
                continue
        await asyncio.sleep(0.85 if gentle else 0.5)
        if not gentle or attempt == outer_max:
            try:
                did = await page.evaluate(
                    """(t) => {
                    const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
                    const b = buttons.find(x => (x.textContent || '').includes(t));
                    if (b) { b.scrollIntoView({block:'center'}); b.click(); return true;}
                    return false;
                }""",
                    raw,
                )
                if did:
                    await asyncio.sleep(0.25)
                    print(f"✅ დავაჭირე (JS): {raw}")
                    return True
            except Exception:
                pass
    msg = f"⚠️ ჯავშნის ღილაკი ('{raw}') ვერ ვიპოვე ან ჩანს disabled"
    print(msg)
    send_log_msg(msg)
    return False


async def autobook_select_time_slot(page, first_time_raw: str) -> bool:
    """დროის mat-option ხშირად ცოტა სიგანით იტვირთება — needle + გამეორებითი გახსნა."""
    needle = _slot_time_needle(first_time_raw)
    if not needle:
        return False
    for attempt in range(1, 6):
        try:
            loc = page.locator("mat-option").filter(has_text=needle).first
            if await loc.is_visible(timeout=3000):
                try:
                    await loc.scroll_into_view_if_needed()
                except Exception:
                    pass
                await human_move_and_click(page, loc, "საათის არჩევა (autobook)")
                return True
        except Exception:
            pass
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.18 + 0.1 * attempt)
        time_dropdown = await find_mat_select_by_placeholder(page, "დრო")
        if not time_dropdown:
            continue
        try:
            await time_dropdown.scroll_into_view_if_needed()
        except Exception:
            pass
        if await robust_click(page, time_dropdown, label=f"დროის მენიუ (autobook retry {attempt})"):
            await asyncio.sleep(_ab_delay(0.75 if attempt < 4 else 1.05))
    return False


async def human_scroll(page):
    try:
        scroll_y = random.randint(220, 720)
        chunks = random.randint(2, 5)
        for i in range(chunks):
            step = scroll_y // max(chunks, 1) + random.randint(-18, 18)
            await page.mouse.wheel(0, max(40, step))
            if random.random() < 0.18:
                await page.mouse.wheel(random.randint(-8, 8), 0)
            await sleep_between(0.22, 0.62)
        if random.random() < 0.55:
            await page.mouse.wheel(0, -(random.randint(40, scroll_y // 3)))
            await sleep_between(0.18, 0.45)
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
            scroll_y + random.randint(-30, 30),
        )
        await sleep_between(0.12, 0.42)
    except:
        pass


async def human_pause():
    await sleep_between(0.3, 1.35)


async def random_idle(page):
    try:
        vp = page.viewport_size
        w, h = int(vp["width"]), int(vp["height"])
    except Exception:
        w, h = 1280, 800
    margin = 80
    x = random.randint(margin, max(margin + 1, w - margin))
    y = random.randint(margin, max(margin + 1, h - margin))
    await page.mouse.move(x, y, steps=random.randint(8, 22))
    await sleep_between(0.12, 0.45)
    if random.random() < 0.35:
        await page.mouse.move(
            x + random.randint(-25, 25),
            y + random.randint(-18, 18),
            steps=random.randint(4, 12),
        )
        await sleep_between(0.08, 0.22)


async def anti_bot_break(page):
    if random.random() < 0.2:
        await random_idle(page)
        await sleep_between(0.85, 2.8)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# "ვეთანხმები"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def handle_agreement(page):
    try:
        modal = page.locator('mat-dialog-container, [role="dialog"], .mat-mdc-dialog-container').first
        try:
            await modal.wait_for(state="visible", timeout=10000)
        except Exception:
            print("ℹ️ წესების ფანჯარა არ ჩანს, ვაგრძელებ...")
            return True

        print("📜 წესები — JS-ით ვასქროლებ modal-ის შიგნით...")

        async def scroll_dialog_down():
            await page.evaluate("""
                () => {
                    const selectors = [
                        '.mat-mdc-dialog-content',
                        '.mat-dialog-content',
                        'mat-dialog-content',
                        'div[appcustomscroll]',
                        '.cdk-overlay-pane [class*="dialog-content"]',
                        '.cdk-overlay-pane [class*="content"]',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.scrollHeight > el.clientHeight) {
                            el.scrollTop = Math.min(
                                el.scrollTop + Math.ceil(el.clientHeight * 0.85),
                                el.scrollHeight
                            );
                            return;
                        }
                    }
                    // fallback — ყველა scrollable element modal-ში
                    const pane = document.querySelector('.cdk-overlay-pane, mat-dialog-container');
                    if (pane) {
                        const all = pane.querySelectorAll('*');
                        for (const el of all) {
                            if (el.scrollHeight > el.clientHeight + 10) {
                                el.scrollTop = Math.min(
                                    el.scrollTop + Math.ceil(el.clientHeight * 0.85),
                                    el.scrollHeight
                                );
                                return;
                            }
                        }
                    }
                }
            """)

        agree_btn = page.locator('button:has-text("ვეთანხმები")').first

        for rnd in range(25):
            await scroll_dialog_down()
            await asyncio.sleep(0.25)

            try:
                dis = await agree_btn.evaluate(
                    "el => el.disabled || el.getAttribute('aria-disabled') === 'true'"
                )
            except Exception:
                dis = True

            if not dis and await agree_btn.is_visible():
                print(f"✅ ვეთანხმები მზადაა (სქროლი {rnd}). ვაჭერ.")
                await agree_btn.scroll_into_view_if_needed()
                await asyncio.sleep(0.4)
                await human_move_and_click(page, agree_btn, "ვეთანხმები")
                await asyncio.sleep(2.8)
                try:
                    if not await modal.is_visible(timeout=1500):
                        return True
                except Exception:
                    return True

            await asyncio.sleep(0.2)

        print("⚠️ ვეთანხმები 25 სქროლის შემდეგ ვერ დაიჭირა")
        return False

    except Exception as e:
        print(f"⚠️ შეცდომა handle_agreement-ში: {e}")
        return False


async def setup_category_and_stage(page):
    try:
        print("⚙️ ვაყენებ კატეგორია B-ს და მეორე ეტაპს...")
        await asyncio.sleep(1.5)
        lock = await detect_practical_booking_lock_message(page)
        if lock:
            msg = (
                "🔒 საიტის შეტყობინება (პირად ნომერზე ლოკი): მითითებულ პირად ნომერზე მიმდინარეობს დაჯავშნა / ცადეთ 1 საათის შემდეგ — "
                "სერვერი დროებით კრძალავს ახალ მოთხოვნებს. არ ნიშნავს ყოველთვის რომ გიჯავშნია: ხშირად ბოტის ცდა (ქალაქი/საათი/დაჯავშნა) "
                "იგივე PN-ზე გახსნის \"მიმდინარე\" სესიას. კატეგორია B ამიტომ „არ იჭერა“. დაელოდე ~1სთ ან შეამოწმე პორტალზე ჯავშანი."
            )
            print(msg)
            send_log_msg(msg, force=True)
            return False
        cat_drop = await find_category_mat_select(page, timeout=12000)
        if not cat_drop:
            print("⚠️ კატეგორიის dropdown ვერ ვიპოვე.")
            return False
        opened = await robust_click(page, cat_drop, label="კატეგორიის მენიუ")
        if not opened:
            await close_overlays(page)
            await asyncio.sleep(0.3)
            await robust_click(page, cat_drop, label="კატეგორიის მენიუ (retry)")
        await asyncio.sleep(1.0)
        b_option = await pick_category_b_mat_option(page)
        if not b_option:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.25)
            await robust_click(page, cat_drop, label="კატეგორიის მენიუ (reopen)")
            await asyncio.sleep(0.9)
            b_option = await pick_category_b_mat_option(page)
        if not b_option:
            print("⚠️ B კატეგორიის ვარიანტი mat-option-ში ვერ ვიპოვე.")
            lock2 = await detect_practical_booking_lock_message(page)
            if lock2:
                send_log_msg(
                    f"🔒 B ვარიანტი არ ჩანს — სავარაუდოდ საიტის ბლოკი: {lock2}",
                    force=True,
                )
            return False
        await b_option.wait_for(state="visible", timeout=7000)
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
# FIX 1: keepalive — confirm_logged_out შემოწმებით
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

        # ━━ სესიის შემოწმება navigate-ის შემდეგ ━━
        if await confirm_logged_out(page):
            msg = "🔒 Keep-alive: სესია გავიდა navigate-ის შემდეგ!"
            print(msg)
            send_log_msg(msg, force=True)
            last_agree_click_time = time.time()
            return True, True

        # არ ვასქროლავთ მთავარ გვერდს — თავიდან არ გავაქტიუროთ ბმულები/რეფრეში ეფექტი
        await asyncio.sleep(0.6)

        practic_btn = page.locator('text=პრაქტიკული გამოცდა').first
        if await practic_btn.is_visible(timeout=5000):
            await human_move_and_click(page, practic_btn, "პრაქტიკული გამოცდა")
            await sleep_between(3, 5)

        # ━━ სესიის შემოწმება გადასვლის შემდეგ ━━
        if await confirm_logged_out(page):
            msg = "🔒 Keep-alive: სესია გავიდა პრაქტიკულის შემდეგ!"
            print(msg)
            send_log_msg(msg, force=True)
            last_agree_click_time = time.time()
            return True, True

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
        phone_input = page.locator(
            'input[type="tel"], input[placeholder*="ტელეფ"], input[placeholder*="პირად"]'
        ).first
        if await phone_input.is_visible(timeout=1500):
            if not quiet:
                _rate_limited_logout_print("🔒 logout სიგნალი: login ფორმა ჩანს")
            return True
        return False
    except:
        return False


async def confirm_logged_out(page, checks=3, delay=1.2):
    hits = 0
    for _ in range(checks):
        if await is_logged_out(page, quiet=True):
            hits += 1
        await asyncio.sleep(delay)
    return hits >= 2


async def wait_for_manual_login(page):
    global last_hard_navigation_time
    session_duration = int(time.time() - last_hard_navigation_time)
    mins = session_duration // 60
    secs = session_duration % 60
    msg = (
        f"🔐 <b>სესია დაიხურა!</b>\n\n"
        f"⏱ <b>სესიის ხანგრძლივობა:</b> {mins} წუთი {secs} წამი\n"
        f"🔒 <b>მიზეზი:</b> ავტორიზაცია საჭიროა\n\n"
        f"გაიარე login/SMS კოდი — ბოტი ავტომატურად გააგრძელებს."
    )
    print(msg)
    send_log_msg(msg, force=True)
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "HTML"},
        timeout=10
    )
    while True:
        try:
            if page.is_closed():
                return
            await asyncio.sleep(5)
            if not await confirm_logged_out(page):
                ok_msg = "✅ ავტორიზაცია დაფიქსირდა! ვაგრძელებ მუშაობას..."
                print(ok_msg)
                send_log_msg(ok_msg, force=True)
                await asyncio.sleep(2)
                last_hard_navigation_time = time.time()
                return
        except:
            return


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


async def relaunch_browser_context(playwright, user_data_dir):
    print("🌐 ვტვირთავ ბრაუზერს (persistent session)...")
    os.makedirs(user_data_dir, exist_ok=True)
    is_server = (os.name != "nt") and (not os.environ.get("DISPLAY"))
    headless = is_server
    print(f"🖥 რეჟიმი: {'სერვერი — headless=True' if headless else 'PC — headless=False (ბრაუზერი ჩანს)'}")
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
        extra_args += ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
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
    context = await playwright.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)
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


def get_autobook_config():
    if not os.path.exists(AUTOBOOK_FILE):
        default_config = {
            "enabled": False,
            "target_user_id": "",
            "target_cities": ["რუსთავი", "გორი", "საჩხერე", "თელავი"],
            "target_only": False,
            "target_prices": ["90", "250"],
            "target_dates": [],
            "target_months": [],
            "target_hours": [],
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


def get_autobook_user_city_list(autobook_cfg: dict) -> list | None:
    """
    users.json-დან target_user_id-ის ქალაქები (რიგით).
    None — იუზერი ფაილში არაა / uid ცარიელი → ადმინის ფოლბექი (დაჯავშნა target_cities-ით).
    [] — იუზერია, მაგრამ ქალაქები არ აქვს → დაჯავშნა nowhere.
    """
    uid = str(autobook_cfg.get("target_user_id") or "").strip()
    if not uid or not os.path.exists(FILE_NAME):
        return None
    try:
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            users_data = json.load(f)
        if uid not in users_data:
            return None
        raw = users_data.get(uid) or []
        return [str(c).strip() for c in raw if str(c).strip()]
    except Exception:
        return None


def get_autobook_booking_cities(autobook_cfg: dict) -> set:
    """
    სადაც დააჭერს „დაჯავშნას“: users.json-ის იუზერის ყველა არჩეული ქალაქი.
    autobook.json target_cities აქ აღარ ჭრის სიას — მხოლოდ პრიორიტეტის რიგია (იხ. build_autobook_user_priority_wave).
    იუზერი ფაილში არაა → target_cities (ადმინის რეჟიმი).
    """
    tc = [str(c).strip() for c in (autobook_cfg.get("target_cities") or []) if str(c).strip()]
    ul = get_autobook_user_city_list(autobook_cfg)
    if ul is None:
        return set(tc)
    return set(ul)

def build_autobook_user_priority_wave(autobook_cfg: dict) -> list:
    ul = get_autobook_user_city_list(autobook_cfg)
    if ul is None or not ul:
        return []
    book_set = set(ul)
    priority = [str(c).strip() for c in (autobook_cfg.get("target_cities") or []) if str(c).strip()]
    prio_ordered = [c for c in priority if c in book_set]
    if not prio_ordered:
        prio_ordered = list(dict.fromkeys(ul))
    return [prio_ordered[0]] * 1
def get_cities_to_check():
    ordered = []
    seen = set()

    def add(c):
        if not c:
            return
        c = str(c).strip()
        if not c or c in seen:
            return
        seen.add(c)
        ordered.append(c)

    autobook_config = get_autobook_config()
    target_user_id = str(autobook_config.get("target_user_id", ""))
    if os.path.exists(FILE_NAME):
        try:
            with open(FILE_NAME, "r", encoding="utf-8") as f:
                users_data = json.load(f)
            for uid, user_cities in users_data.items():
                for c in user_cities or []:
                    add(c)
            if autobook_config.get("enabled") and target_user_id in users_data:
                for c in users_data.get(target_user_id) or []:
                    add(c)
        except Exception as e:
            print(f"შეცდომა ფაილის წაკითხვისას: {e}")
    for city in autobook_config.get("target_cities", []):
        add(city)
    if not autobook_config.get("target_only", False):
        for c in CITIES_LIST:
            add(c)
    return ordered


def build_priority_triple_wave(priority):
    """
    autobook.json-ის target_cities რიგით: პირველი ქალაქი ყოველ ტრიოში,
    დანარჩენი ერთმანეთის მიყოლებით იროტირდება (მაგ. თელავი,რ,გ → თ,რ,გ | თ,გ,ს ...).
    """
    if not priority:
        return []
    if len(priority) == 1:
        return [priority[0]] * 3
    p0 = priority[0]
    rest = priority[1:]
    n = len(rest)
    wave = []
    for k in range(n):
        wave.append(p0)
        wave.append(rest[k % n])
        wave.append(rest[(k + 1) % n])
    return wave


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 2: build_check_sequence — პრიორიტეტის ტალღა, დანარჩენი ქალაქები ბოლოს (თავისუფლები ყველაზე ბოლოს)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_check_sequence(priority_cities, all_cities_ordered):
    if not all_cities_ordered:
        return []
    all_set = set(all_cities_ordered)
    priority = [c for c in priority_cities if c in all_set]
    prio_set = set(priority)
    others = [c for c in all_cities_ordered if c not in prio_set]
    free_cities = [c for c in others if c in _cities_with_slots]
    busy_others = [c for c in others if c not in _cities_with_slots]
    tail = busy_others + free_cities
    wave = build_priority_triple_wave(priority)
    if wave:
        return wave[:2] + tail
    return tail


def get_cycle_wait_seconds(cycle_count):
    if EXACT_TIMING:
        return FIXED_CYCLE_WAIT_SECONDS
    return random.randint(30, 45)


def is_night_maintenance():
    return 2 <= datetime.datetime.now().hour < 8


async def is_block_or_captcha(page):
    try:
        url = (page.url or "").lower()
        if any(k in url for k in ["captcha", "blocked", "access-denied"]):
            return True
        content = await page.inner_text("body")
        content = content.lower()
        bad_phrases = ["your ip is blocked", "access denied", "too many requests"]
        if any(p in content for p in bad_phrases):
            return True
    except:
        pass
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 3: ფასის პარსინგი slot ტექსტიდან
# "10:35 (250 ლარი)" → "10:35 — არაგეგმიური (250 ₾)"
# "09:45"            → "09:45 — სტანდარტული (90 ₾)"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def format_slot_with_price(raw: str) -> str:
    price_match = re.search(r'(\d+)\s*ლარი', raw)
    time_match = re.search(r'\d{1,2}:\d{2}', raw)
    if not time_match:
        return raw.strip()
    t = time_match.group()
    if price_match:
        price = int(price_match.group(1))
        return f"{t} — არაგეგმიური ({price} ₾)"
    return f"{t} — სტანდარტული (90 ₾)"


def format_slots_pretty_lines(times_sorted: list) -> str:
    lines = []
    for t in times_sorted:
        lines.append(f"  • {format_slot_with_price(t)}")
    return "\n".join(lines) if lines else "  —"


def build_premium_report_txt(city: str, date_to_times: dict) -> str:
    lines = [
        f"პრაქტიკული გამოცდა — {city}",
        "=" * 48,
        "",
    ]
    for date_val in sorted(
        date_to_times.keys(),
        key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d),
    ):
        times_list = date_to_times.get(date_val) or []
        if not times_list:
            continue
        cur = sorted(set(times_list))
        lines.append(f"📅 {date_val}")
        for t in cur:
            lines.append(f"   • {format_slot_with_price(t)}")
        lines.append("")
    lines.append("my.sa.gov.ge — დაჯავშნა")
    return "\n".join(lines)


def build_quick_dates_txt(city: str, dates: list) -> str:
    ds = sorted(
        {str(d).strip() for d in dates if str(d).strip()},
        key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d),
    )
    body = "\n".join(f"  • {d}" for d in ds)
    return f"თავისუფალი თარიღები — {city}\n{'=' * 40}\n\n{body}\n\n(საათების სია საიტზე გახსენი)"


def _slot_times_are_real(times_set) -> bool:
    if not times_set:
        return False
    if DATE_QUICK_MARKER in times_set:
        return False
    return any(":" in str(t) for t in times_set)


def send_city_dates_quick_summary(city: str, dates: list):
    """
    სწრაფი სკანი: მხოლოდ თარიღების სია (საათების გახსნის გარეშე).
    """
    global SEEN_SLOTS, _cities_with_slots

    if not dates:
        return

    now = time.time()
    city_data = SEEN_SLOTS.setdefault(city, {})
    dates_sorted = sorted(
        {str(d).strip() for d in dates if str(d).strip()},
        key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d),
    )
    lines_dt = []
    for date_val in dates_sorted:
        entry = city_data.get(date_val)
        if entry and _slot_times_are_real(entry.get("times") or set()):
            continue
        lines_dt.append(date_val)

    if not lines_dt:
        return

    trig = False
    for date_val in lines_dt:
        entry = city_data.get(date_val)
        if entry is None:
            trig = True
            break
        if (now - float(entry.get("last_sent") or 0.0)) >= RESEND_INTERVAL:
            trig = True
            break

    if FORCE_SEND_ON_START and city not in _force_sent_cities:
        trig = True

    if not trig:
        return

    _cities_with_slots.add(city)

    keyboard = {"inline_keyboard": [[{"text": "🚀 my.sa.gov.ge", "url": "https://my.sa.gov.ge"}]]}
    keyboard_json = json.dumps(keyboard)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    n_dt = len(lines_dt)

    if n_dt > TG_DATES_FILE_THRESHOLD:
        raw_txt = build_quick_dates_txt(city, lines_dt).encode("utf-8")
        fname = "dates.txt"
        cap = (
            f"📋 <b>თავისუფალი თარიღები</b>\n"
            "────────────────────\n"
            f"🏛 <code>{city}</code>\n"
            f"📎 <b>{n_dt}</b> თარიღი — სრული სია ფაილში.\n\n"
            "<i>საათების სია საიტზე გახსენი.</i>"
        )
        safe_telegram_send_document(
            ADMIN_ID, fname, raw_txt, caption_html=cap, reply_markup_json=keyboard_json, context="admin-dates-quick-doc"
        )
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, "r", encoding="utf-8") as f:
                data = json.load(f)
            for chat_id in data:
                if city in data[chat_id]:
                    safe_telegram_send_document(
                        int(chat_id),
                        fname,
                        raw_txt,
                        caption_html=cap,
                        reply_markup_json=keyboard_json,
                        context=f"user-dates-quick-doc-{chat_id}",
                    )
    else:
        body = "\n".join(f"  • <code>{d}</code>" for d in lines_dt)
        msg = (
            f"📋 <b>თავისუფალი თარიღები</b>\n"
            "────────────────────\n\n"
            f"🏛 <b>ქალაქი:</b> <code>{city}</code>\n\n"
            f"{body}\n\n"
            "<i>საათები ამ შეტყობინებაში არაა — გახსენი საიტზე.</i>"
        )
        safe_telegram_post(
            url,
            data={
                "chat_id": ADMIN_ID,
                "text": msg,
                "parse_mode": "HTML",
                "reply_markup": keyboard_json,
            },
            context="admin-dates-quick",
        )
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, "r", encoding="utf-8") as f:
                data = json.load(f)
            for chat_id in data:
                if city in data[chat_id]:
                    safe_telegram_post(
                        url,
                        data={
                            "chat_id": chat_id,
                            "text": msg,
                            "parse_mode": "HTML",
                            "reply_markup": keyboard_json,
                        },
                        context=f"user-dates-quick-{chat_id}",
                    )

    for date_val in lines_dt:
        dd = city_data.setdefault(date_val, {"times": set(), "last_sent": 0.0})
        if not _slot_times_are_real(dd.get("times") or set()):
            dd["times"] = {DATE_QUICK_MARKER}
        dd["last_sent"] = now


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 4: city summary send — 2 საათის throttle + "დაემატა" ლოგიკა
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def send_city_premium_summary(city: str, date_to_times: dict):
    """
    ქალაქზე ერთხელ აგზავნის შედეგს (ყველა თარიღი/საათი ერთად).
    გაგზავნის ტრიგერი (ნებისმიერ თარიღზე):
      - ახალი სლოტი დაემატა → მაშინვე
      - იგივე სლოტები → 2 საათში ერთხელ
    """
    global SEEN_SLOTS, _cities_with_slots

    if not date_to_times:
        return

    now = time.time()
    city_data = SEEN_SLOTS.setdefault(city, {})

    # თარიღების თანმიმდევრობა: ჯერ კალენდარული (თუ dd-mm-yyyy), თორემ როგორც სტრინგი
    dates_sorted = sorted(
        list(date_to_times.keys()),
        key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d)
    )

    # ცვლილებების დადგენა per-date (ვიყენებთ მხოლოდ იმ თარიღებს სადაც რეალურად არის საათები)
    any_new = False
    any_resend_due = False
    new_by_date = {}
    for date_val in dates_sorted:
        times_list = date_to_times.get(date_val) or []
        current_times = set(times_list)
        if not current_times:
            continue
        date_data = city_data.setdefault(date_val, {"times": set(), "last_sent": 0.0})
        known_times = date_data["times"]
        new_times = current_times - known_times
        if new_times:
            any_new = True
            new_by_date[date_val] = new_times
        if (now - float(date_data.get("last_sent") or 0.0)) >= RESEND_INTERVAL:
            any_resend_due = True

    # სტარტზე ერთჯერადი "force send" რომ ახლავე მივიდეს სრული ინფო
    if FORCE_SEND_ON_START and city not in _force_sent_cities:
        any_resend_due = True
        _force_sent_cities.add(city)

    if not any_new and not any_resend_due:
        return

    _cities_with_slots.add(city)

    # Header ტიპი
    is_first_find = all(not city_data.get(d, {}).get("times") for d in dates_sorted)
    if any_new and not is_first_find:
        title = "🆕 <b>ახალი ადგილები დაემატა!</b>"
        subtitle = ""
    elif is_first_find:
        title = "🔔 <b>ჯავშანი გაიხსნა!</b>"
        subtitle = ""
    else:
        title = "⏰ <b>შეხსენება — ადგილები კვლავ თავისუფალია</b>"
        subtitle = "\n<i>ახალი თარიღი/დრო ამ შემოწმებაზე არ დაფიქსირდა.</i>\n"

    body_lines = []
    dates_with_slots = []
    for date_val in dates_sorted:
        times_list = date_to_times.get(date_val) or []
        current_times_sorted = sorted(set(times_list))
        if not current_times_sorted:
            continue
        dates_with_slots.append(date_val)
        slots_text = format_slots_pretty_lines(current_times_sorted)

        if date_val in new_by_date:
            added_lines = format_slots_pretty_lines(sorted(new_by_date[date_val]))
            section = (
                f"📅 <b>{date_val}</b>\n"
                f"<b>✨ ახალი</b>\n{added_lines}\n"
                f"<b>სლოტები</b>\n{slots_text}"
            )
        else:
            section = f"📅 <b>{date_val}</b>\n{slots_text}"

        body_lines.append(section)

    if not body_lines:
        return

    keyboard = {"inline_keyboard": [[{"text": "🚀 დაჯავშნე ახლავე", "url": "https://my.sa.gov.ge"}]]}
    keyboard_json = json.dumps(keyboard)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    use_file = len(dates_with_slots) > TG_DATES_FILE_THRESHOLD

    if use_file:
        raw_txt = build_premium_report_txt(city, date_to_times).encode("utf-8")
        fname = "slots.txt"
        new_hint = ""
        if any_new and new_by_date:
            bits = []
            for dv, nt in sorted(new_by_date.items(), key=lambda x: (_parse_dd_mm_yyyy(x[0]) or datetime.date(2100, 1, 1), x[0])):
                bits.append(f"{dv}: " + ", ".join(sorted(nt)[:6]))
            new_hint = "\n✨ <b>ახალი:</b> " + " · ".join(bits)[:400]
        cap = (
            f"{title}\n"
            "────────────────────\n"
            f"🏛 <code>{city}</code>\n"
            f"📎 <b>{len(dates_with_slots)}</b> თარიღი — ყველა საათი ფაილში (მოწესრიგებული სია)."
            + (subtitle or "")
            + new_hint
        )
        safe_telegram_send_document(
            ADMIN_ID,
            fname,
            raw_txt,
            caption_html=cap,
            reply_markup_json=keyboard_json,
            context="admin-premium-doc",
        )
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, "r", encoding="utf-8") as f:
                data = json.load(f)
            for chat_id in data:
                if city in data[chat_id]:
                    safe_telegram_send_document(
                        int(chat_id),
                        fname,
                        raw_txt,
                        caption_html=cap,
                        reply_markup_json=keyboard_json,
                        context=f"user-premium-doc-{chat_id}",
                    )
    else:
        msg = (
            f"{title}\n"
            "────────────────────\n\n"
            f"🏛 <b>ქალაქი:</b> <code>{city}</code>\n\n"
            + (subtitle or "")
            + "\n\n".join(body_lines)
            + "\n\n⚡ <a href='https://my.sa.gov.ge'>სასწრაფოდ დაჯავშნა</a>"
        )
        safe_telegram_post(
            url,
            data={
                "chat_id": ADMIN_ID,
                "text": msg,
                "parse_mode": "HTML",
                "reply_markup": keyboard_json,
            },
            context="admin-premium",
        )
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, "r", encoding="utf-8") as f:
                data = json.load(f)
            for chat_id in data:
                if city in data[chat_id]:
                    safe_telegram_post(
                        url,
                        data={
                            "chat_id": chat_id,
                            "text": msg,
                            "parse_mode": "HTML",
                            "reply_markup": keyboard_json,
                        },
                        context=f"user-{chat_id}",
                    )

    # სტეიტის განახლება: მხოლოდ იმ თარიღებზე სადაც არის საათები
    for date_val in dates_sorted:
        times_list = date_to_times.get(date_val) or []
        current_times = set(times_list)
        if not current_times:
            continue
        date_data = city_data.setdefault(date_val, {"times": set(), "last_sent": 0.0})
        date_data["times"] = current_times
        date_data["last_sent"] = now


def send_booked_msg(city, date_val, time_val, autobook_cfg: dict | None = None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        msg = (
            "✅ <b>Autobook — დადასტურება გავიდა</b>\n"
            "────────────────────\n\n"
            f"🏛 <b>ქალაქი:</b> <code>{city}</code>\n"
            f"📅 <b>თარიღი:</b> <code>{date_val}</code>\n"
            f"⏰ <b>დრო:</b> <code>{time_val}</code>\n\n"
            "────────────────────\n"
            "<i>შეამოწმე SMS და პორტალზე ჯავშანი.</i>\n"
        )
        keyboard = {"inline_keyboard": [[{"text": "🚀 my.sa.gov.ge", "url": BOOKING_DIRECT_URL}]]}
        markup = json.dumps(keyboard)
        safe_telegram_post(url, data={
            "chat_id": ADMIN_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": markup
        }, context="admin-booked")

        sent_uid = set()
        if autobook_cfg:
            tuid = str(autobook_cfg.get("target_user_id") or "").strip()
            if tuid.isdigit():
                safe_telegram_post(url, data={
                    "chat_id": tuid,
                    "text": msg,
                    "parse_mode": "HTML",
                    "reply_markup": markup
                }, context="autobook-booked-target")
                sent_uid.add(tuid)

        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for chat_id in data:
                if str(chat_id) in sent_uid:
                    continue
                if city in data[chat_id]:
                    safe_telegram_post(url, data={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "reply_markup": markup
                    }, context=f"user-booked-{chat_id}")
    except Exception:
        pass


def send_status_report(cities_checked, found_cities, found_details: dict | None = None):
    global last_report_time
    now = time.time()
    has_findings = bool(found_cities)
    if not has_findings:
        if is_user_quiet_hours():
            return
        if now - last_report_time < STATUS_REPORT_INTERVAL:
            return
    last_report_time = now
    fd = found_details or {}

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    keyboard = {"inline_keyboard": [[{"text": "🚀 დაჯავშნა", "url": "https://my.sa.gov.ge"}]]}
    keyboard_json = json.dumps(keyboard)

    if found_cities:
        blocks = []
        for c in sorted(found_cities):
            det = fd.get(c)
            if det:
                blocks.append(f"🏛 <b>{c}</b>\n{det}")
            else:
                blocks.append(f"🏛 <b>{c}</b>")
        status = "✅ <b>ნაპოვნია (ციკლის შედეგი)</b>\n\n" + "\n\n".join(blocks)
    else:
        status = "ℹ️ <b>ახალი თარიღი/საათი ამ ციკლზე არ დაემატა</b>"

    admin_msg = (
        f"📊 <b>სტატუს რეპორტი</b>\n"
        f"────────────────────\n\n"
        f"{status}\n\n"
        f"────────────────────\n"
        f"🏙 <b>შემოწმებული ქალაქები:</b>\n<code>{', '.join(cities_checked)}</code>\n"
        f"⏰ <code>{datetime.datetime.now().strftime('%H:%M:%S')}</code>"
    )

    use_doc = bool(found_cities) and len(admin_msg) > 3600
    doc_bytes = None
    if use_doc:
        lines = [
            f"სტატუს რეპორტი — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 52,
            "",
        ]
        for c in sorted(found_cities):
            lines.append(f"【 {c} 】")
            lines.append(fd.get(c) or "—")
            lines.append("")
        lines.append("შემოწმებული ქალაქები: " + ", ".join(cities_checked))
        doc_bytes = "\n".join(lines).encode("utf-8")

    if use_doc and doc_bytes:
        cap = (
            f"📊 <b>სტატუს რეპორტი</b>\n"
            "────────────────────\n"
            f"✅ ნაპოვნია <b>{len(found_cities)}</b> ქალაქში — სრული დეტალი ფაილში.\n"
            f"⏰ <code>{datetime.datetime.now().strftime('%H:%M:%S')}</code>"
        )
        safe_telegram_send_document(
            ADMIN_ID,
            "status_report.txt",
            doc_bytes,
            caption_html=cap,
            reply_markup_json=keyboard_json,
            context="admin-status-doc",
        )
    else:
        safe_telegram_post(
            url,
            data={
                "chat_id": ADMIN_ID,
                "text": admin_msg,
                "parse_mode": "HTML",
                "reply_markup": keyboard_json if found_cities else None,
            },
            context="admin-status",
        )

    if not found_cities or not os.path.exists(FILE_NAME):
        return
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        users_data = json.load(f)

    for chat_id, user_cities in users_data.items():
        if int(chat_id) == ADMIN_ID:
            continue
        user_found = [c for c in found_cities if c in user_cities]
        if not user_found:
            continue

        user_blocks = []
        for c in user_found:
            det = fd.get(c)
            if det:
                user_blocks.append(f"🏛 <b>{c}</b>\n{det}")
            else:
                user_blocks.append(f"🏛 <b>{c}</b>")

        user_msg = (
            f"🔔 <b>შენს ქალაქ(ებ)ში ადგილია!</b>\n"
            f"────────────────────\n\n"
            + "\n\n".join(user_blocks)
            + f"\n\n⏰ <code>{datetime.datetime.now().strftime('%H:%M:%S')}</code>"
        )
        if use_doc and doc_bytes:
            ucap = (
                f"🔔 <b>შენს ქალაქ(ებ)ში ადგილია!</b>\n"
                "────────────────────\n"
                f"ქალაქები: <b>{', '.join(user_found)}</b>\n"
                "დეტალები ფაილში.\n"
                f"⏰ <code>{datetime.datetime.now().strftime('%H:%M:%S')}</code>"
            )
            safe_telegram_send_document(
                int(chat_id),
                "status_report.txt",
                doc_bytes,
                caption_html=ucap,
                reply_markup_json=keyboard_json,
                context=f"user-status-doc-{chat_id}",
            )
        else:
            safe_telegram_post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": user_msg,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard_json,
                },
                context=f"user-status-{chat_id}",
            )


def build_cycle_found_details(pending_city_notifications: dict, pending_quick_dates: dict) -> dict:
    """ციკლის ბოლოს რეპორტისთვის: ქალაქი → ტექსტი (თარიღები / საათებით)."""
    found_lines = {}
    for c, dtt in (pending_city_notifications or {}).items():
        parts = []
        for dv in sorted(
            dtt.keys(),
            key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d),
        ):
            times = dtt.get(dv) or []
            tail = ", ".join(times[:8])
            if len(times) > 8:
                tail += " …"
            parts.append(f"  📅 {dv}: {tail}")
        found_lines[c] = "\n".join(parts) if parts else ""
    for c, dlist in (pending_quick_dates or {}).items():
        if c in found_lines and found_lines[c]:
            continue
        ds = sorted(
            dlist,
            key=lambda d: (_parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1), d),
        )
        shown = ", ".join(ds[:18])
        if len(ds) > 18:
            shown += " …"
        found_lines[c] = f"📅 თარიღები: {shown}"
    return found_lines


def send_user_reminder():
    global last_reminder_time
    if is_user_quiet_hours():
        return
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
            "⏳ <b>ძიება მიმდინარეობს...</b>\n────────────────────\n\n"
            "🤖 ბოტი აქტიურად ეძებს თავისუფალ ადგილს\n\n"
            f"🏙 <b>შენი ქალაქები:</b>\n{cities_fmt}\n\n"
            "────────────────────\n"
            "🔔 ადგილის გამოჩენისთანავე შეგატყობინებთ!"
        )
        safe_telegram_post(url, data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML"
        }, context=f"user-reminder-{chat_id}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# მთავარი checker — შენი ორიგინალი, უცვლელი
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def run_checker():
    async with async_playwright() as p:
        print("🌐 Opening Browser...")
        load_seen_slots()
        user_data_dir = os.path.join(os.getcwd(), "user_data")
        context, page = await relaunch_browser_context(p, user_data_dir)
        await safe_goto(page, 'https://my.sa.gov.ge')
        was_available_cities = set()
        cycle_count = 0
        need_navigation = True

        while True:
            try:
                global last_hard_navigation_time
                logout_detected = False
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

                if await is_logged_out(page):
                    print("🔒  Session Expired!")
                    await wait_for_manual_login(page)
                    need_navigation = True
                    continue

                if (
                    SESSION_FORCE_NAV_SECONDS > 0
                    and last_hard_navigation_time > 0
                    and (time.time() - last_hard_navigation_time) >= SESSION_FORCE_NAV_SECONDS
                ):
                    print(
                        f"🔄 პლანირებული სესიის სრული განახლება "
                        f"(SESSION_FORCE_NAV_SECONDS={SESSION_FORCE_NAV_SECONDS})."
                    )
                    need_navigation = True

                if await is_block_or_captcha(page):
                    msg = "⚠️ ბლოკი/კაფტჩა გამოვლინდა, ველოდებით..."
                    print(msg)
                    send_log_msg(msg, force=True)
                    need_navigation = True
                    await asyncio.sleep(random.uniform(45, 80))
                    continue

                if KEEPALIVE_ENABLED:
                    keep_trig, keep_out = await keepalive_agree_click(page)
                    if keep_out:
                        await wait_for_manual_login(page)
                        need_navigation = True
                        continue
                    if keep_trig:
                        need_navigation = True

                if need_navigation:
                    print("🚀 ვაკეთებ სესიის სრულ გაცოცხლებას (Hard Refresh)...")
                    await page.goto('https://my.sa.gov.ge', wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    practic_btn = page.locator('text=პრაქტიკული გამოცდა').first
                    await human_move_and_click(page, practic_btn, "პრაქტიკული გამოცდა")
                    await asyncio.sleep(3)
                    if await handle_agreement(page):
                        setup_ok = await setup_category_and_stage(page)
                        if not setup_ok:
                            print("⚠️ კატეგორიის/ეტაპის დაყენება ვერ მოხერხდა, თავიდან ვცდი...")
                            need_navigation = True
                            continue
                        need_navigation = False
                        last_agree_click_time = time.time()
                        last_hard_navigation_time = time.time()
                        print("✅ სესია განახლებულია!")
                    else:
                        print("⚠️ რეფრეში ვერ მოხერხდა, ვცდი თავიდან...")
                        continue

                modal_visible = await page.locator(
                    ".mat-mdc-dialog-content, mat-dialog-content"
                ).first.is_visible()
                if modal_visible:
                    print("🚨 წესების ფანჯარა მოულოდნელად გამოჩნდა! ვასწორებ...")
                    await handle_agreement(page)
                    await setup_category_and_stage(page)

                autobook_cfg = get_autobook_config()
                all_requested = get_cities_to_check()
                priority_cities = autobook_cfg.get("target_cities", [])
                autobook_book_set = get_autobook_booking_cities(autobook_cfg)
                base_check_list = build_check_sequence(priority_cities, all_requested)
                if not base_check_list:
                    base_check_list = list(all_requested)
                user_ab_wave = (
                    build_autobook_user_priority_wave(autobook_cfg)
                    if autobook_cfg.get("enabled")
                    else []
                )
                check_list = user_ab_wave + base_check_list if user_ab_wave else base_check_list
                print(f"📡 სკანირების რიგი: {check_list[:18]}{'…' if len(check_list) > 18 else ''}")
                if autobook_cfg.get("enabled") and not autobook_book_set:
                    print(
                        "⚠️ Autobook ჩართულია, მაგრამ დასაჯავშნი ქალაქი არაა — users.json-ში ამ target_user_id-ს "
                        "ცარიელი სიაა (ან autobook.json target_cities ცარიელია ადმინის რეჟიმში)."
                    )

                current_available_cities = set()
                pending_city_notifications = {}
                pending_quick_dates = {}

                await anti_bot_break(page)

                for city in check_list:
                    if time.time() - last_agree_click_time > AGREE_INTERVAL_SECONDS:
                        print("🚨 რეფრეშის დროა!")
                        need_navigation = True
                        break
                    if await is_logged_out(page):
                        print("🔒 logout დაფიქსირდა ქალაქის შემოწმებისას — ველოდები ხელით login-ს...")
                        logout_detected = True
                        need_navigation = True
                        break

                    print(f"🔎 Checking: {city}")
                    autobook_here_early = autobook_cfg.get("enabled") and city in autobook_book_set

                    city_dropdown = await wait_city_dropdown(page, timeout=10000)
                    if not city_dropdown:
                        need_navigation = True
                        break
                    if not await robust_click(page, city_dropdown, label=f"მენიუ ({city})"):
                        need_navigation = True
                        break

                    option = page.locator("mat-option").filter(has_text=city).first
                    if not await option.is_visible():
                        await page.keyboard.press("Escape")
                        continue
                    await robust_click(page, option, label=city)
                    await asyncio.sleep(_ab_delay(2.0) if autobook_here_early else 1.8)

                    dates_quick = await collect_available_dates_quick(page, autobook_cfg)
                    if not dates_quick:
                        await close_overlays(page)
                        continue

                    autobook_here = autobook_cfg.get("enabled") and city in autobook_book_set
                    n_dates = len(dates_quick)
                    # ≤2 თარიღი → საათების წაკითხვა და სრული შეტყობინება; >2 → მხოლოდ თარიღების სია
                    date_time_rows = []
                    if n_dates <= 2 or autobook_here:
                        date_time_rows = await collect_all_dates_and_times(
                            page,
                            autobook_cfg,
                            fast=True,
                            restrict_to_dates=list(dates_quick)[:2] if n_dates > 2 else list(dates_quick),
                        )
                    elif autobook_here:
                        ds_probe = sorted(
                            dates_quick,
                            key=lambda d: (
                                _parse_dd_mm_yyyy(d) or datetime.date(2100, 1, 1),
                                d,
                            ),
                        )[:2]
                        date_time_rows = await collect_all_dates_and_times(
                            page,
                            autobook_cfg,
                            fast=True,
                            restrict_to_dates=ds_probe,
                        )

                    date_to_times = {}
                    for date_val, times, _valid_slot_locators in date_time_rows:
                        if times:
                            date_to_times[date_val] = times

                    if n_dates <= 2:
                        if date_to_times:
                            current_available_cities.add(city)
                            pending_city_notifications[city] = date_to_times
                        else:
                            current_available_cities.add(city)
                            pending_quick_dates[city] = list(dates_quick)
                    else:
                        current_available_cities.add(city)
                        pending_quick_dates[city] = list(dates_quick)

                    # სიახლე — ციკლის ბოლოს არ ველოდებით (send_* თავად დააბრუნებს თუ უკვე გაგზავნილია)
                    if city in pending_city_notifications:
                        send_city_premium_summary(city, pending_city_notifications[city])
                    elif city in pending_quick_dates:
                        send_city_dates_quick_summary(city, pending_quick_dates[city])

                    # autobook — პირველივე შესაბამის სლოტზე ცდა (ნელი ნაბიჯები + Telegram)
                    if autobook_here:
                        for date_val, times, _valid_slot_locators in date_time_rows:
                            if not times:
                                continue
                            print(f"⚡ ვცდილობ დაჯავშნას: {city} | {date_val} ...")
                            first_time = times[0]
                            send_autobook_notify(
                                autobook_cfg,
                                (
                                    "⏳ <b>Autobook</b> — სლოტი შერჩეულია, ვაკეთებ დაჯავშნის ნაბიჯებს\n"
                                    "────────────────────\n"
                                    f"🏛 <code>{city}</code>\n📅 <code>{date_val}</code>\n⏰ <code>{first_time}</code>"
                                ),
                                "progress",
                            )
                            date_dropdown = await find_mat_select_by_placeholder(page, "თარიღი")
                            if date_dropdown:
                                try:
                                    await date_dropdown.scroll_into_view_if_needed()
                                except Exception:
                                    pass
                                await robust_click(page, date_dropdown, label="თარიღის მენიუ (autobook)")
                                await asyncio.sleep(_ab_delay(0.55))
                                date_opt = page.locator("mat-option").filter(has_text=date_val).first
                                if await date_opt.is_visible():
                                    await robust_click(page, date_opt, label=f"თარიღი {date_val} (autobook)")
                                    await asyncio.sleep(_ab_delay(0.85))

                            time_dropdown = await find_mat_select_by_placeholder(page, "დრო")
                            if time_dropdown:
                                try:
                                    await time_dropdown.scroll_into_view_if_needed()
                                except Exception:
                                    pass
                                await robust_click(page, time_dropdown, label="დროის მენიუ (autobook)")
                                await asyncio.sleep(_ab_delay(0.85))
                                if await autobook_select_time_slot(page, first_time):
                                    await asyncio.sleep(_ab_delay(1.0))
                                    send_autobook_notify(
                                        autobook_cfg,
                                        (
                                            "🔔 <b>Autobook</b> — „დაჯავშნა“-ზე ვაჭერ "
                                            "(მიმდინარეობს დაჯავშნის პროცესი)\n"
                                            "────────────────────\n"
                                            f"🏛 <code>{city}</code> · 📅 <code>{date_val}</code> · ⏰ <code>{first_time}</code>"
                                        ),
                                        "progress",
                                    )
                                    booked = await click_book_button(
                                        page,
                                        autobook_cfg.get("button_text", "დაჯავშნა"),
                                        gentle=True,
                                    )
                                    if not booked:
                                        lock_h = await detect_practical_booking_lock_message(page)
                                        extra = f"\n🔒 საიტის ტექსტი: <i>{lock_h}</i>" if lock_h else ""
                                        send_autobook_notify(
                                            autobook_cfg,
                                            "❌ <b>Autobook</b> — „დაჯავშნა“ ვერ დაიჭირა (disabled, არ ჩანს ან დაბლოკილია)."
                                            + extra,
                                            "error",
                                        )
                                    else:
                                        await asyncio.sleep(_ab_delay(0.8))
                                        confirm = page.locator(
                                            'button:has-text("დიახ"), button:has-text("დადასტურება")'
                                        ).first
                                        confirmed = True
                                        try:
                                            if await confirm.is_visible(timeout=3000):
                                                await confirm.click()                                           
                                        except Exception:
                                            pass
                                        if confirmed:
                                            send_booked_msg(
                                                city,
                                                date_val,
                                                first_time,
                                                autobook_cfg=autobook_cfg,
                                            )
                                            if autobook_cfg.get("stop_after_booking"):
                                                autobook_cfg["enabled"] = False
                                                with open(AUTOBOOK_FILE, "w", encoding="utf-8") as f:
                                                    json.dump(
                                                        autobook_cfg, f, ensure_ascii=False, indent=4
                                                    )
                                        else:
                                            lock_h = await detect_practical_booking_lock_message(page)
                                            send_autobook_notify(
                                                autobook_cfg,
                                                (
                                                    "⚠️ <b>Autobook</b> — „დაჯავშნა“ დაიჭირა, "
                                                    "მაგრამ „დიახ/დადასტურება“ არ ჩანს.\n"
                                                    "სლოტი შეიძლება ჩახურული იყოს ან სერვერმა უარი თქვა."
                                                    + (f"\n🔒 <i>{lock_h}</i>" if lock_h else "")
                                                ),
                                                "error",
                                            )
                                else:
                                    send_autobook_notify(
                                        autobook_cfg,
                                        (
                                            "❌ <b>Autobook</b> — საათის ვარიანტი ვეღარ ვიპოვე "
                                            f"(სავარაუდოდ ჩახურულია): <code>{first_time}</code>"
                                        ),
                                        "error",
                                    )
                            if not autobook_cfg.get("enabled"):
                                break

                    if winsound and city in current_available_cities:
                        winsound.Beep(1000, 500)

                    await asyncio.sleep(1)
                    await close_overlays(page)

                # თუ ციკლის შუაში გამოვარდა auth-ზე, აღარ ველოდებით შემდეგ ციკლს
                if logout_detected or await is_logged_out(page, quiet=True):
                    print("🔐 სესია გასულია. გთხოვ ხელით გაიარო login/SMS; ბოტი ავტომატურად გააგრძელებს.")
                    await wait_for_manual_login(page)
                    need_navigation = True
                    continue

                # ━━━ ციკლის დასრულება ━━━
                # ერთიანი გაგზავნა ციკლის ბოლოს (ქალაქების მიხედვით)
                for city_name, summary in pending_city_notifications.items():
                    send_city_premium_summary(city_name, summary)
                for city_name, dlist in pending_quick_dates.items():
                    if city_name in pending_city_notifications:
                        continue
                    send_city_dates_quick_summary(city_name, dlist)

                # ქალაქები რომლებსაც სლოტი არ ჰქონდათ — _cities_with_slots-დან გასუფთავება
                for city in all_requested:
                    if city not in current_available_cities and city in _cities_with_slots:
                        _cities_with_slots.discard(city)

                was_available_cities = current_available_cities
                cycle_found = build_cycle_found_details(
                    pending_city_notifications, pending_quick_dates
                )
                send_status_report(
                    list(all_requested),
                    list(current_available_cities),
                    cycle_found,
                )
                send_user_reminder()
                save_seen_slots()

                wait = get_cycle_wait_seconds(cycle_count)
                time_passed = time.time() - last_agree_click_time
                next_keepalive = max(0, int(AGREE_INTERVAL_SECONDS - time_passed))
                cycle_count += 1

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