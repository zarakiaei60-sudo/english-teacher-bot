# -*- coding: utf-8 -*-
"""English Teacher Bot — pure-stdlib Telegram polling bot (no dependencies).

Runs 24/7 via GitHub Actions (public repo = free unlimited minutes).
Features: beginner conversation scenarios (with Persian translation +
transliteration), sentence drills with fuzzy checking, phrasebook with
audio (Google TTS via sendAudio URL), common-mistake fixes.
Admin-only commands gated by ADMIN_ID.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error

TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
API = f"https://api.telegram.org/bot{TOKEN}"
RUN_SECONDS = 5 * 3600 + 45 * 60  # 5h45m — exit cleanly before the job timeout
START = time.time()

sessions = {}   # user_id -> {"mode":..., "scen":..., "step":..., "good":..., "drill":..., "score":..., "streak":...}
stats = {"users": set(), "answers": 0, "started": time.time()}

# ----------------------------- content -----------------------------

FA_TR = {  # transliteration helper for menus is inline; per-item below
}

def tr_en(text):
    """Very small English->Persian-letters transliteration for pronunciation."""
    s = text.lower()
    s = re.sub(r"th", "ث", s); s = re.sub(r"sh", "ش", s); s = re.sub(r"ch", "چ", s)
    s = re.sub(r"oo", "وو", s); s = re.sub(r"ee", "یی", s); s = re.sub(r"ou", "او", s)
    s = re.sub(r"ai", "ِای", s); s = re.sub(r"ay", "ِای", s); s = re.sub(r"ow", "او", s)
    s = re.sub(r"ph", "ف", s); s = re.sub(r"ck", "ک", s); s = re.sub(r"qu", "کو", s)
    mapping = {
        "a": "اِ", "b": "ب", "c": "ک", "d": "د", "e": "اِ", "f": "ف", "g": "گ",
        "h": "ه", "i": "ای", "j": "ج", "k": "ک", "l": "ل", "m": "م", "n": "ن",
        "o": "او", "p": "پ", "q": "ک", "r": "ر", "s": "س", "t": "ت", "u": "آ",
        "v": "و", "w": "و", "x": "کس", "y": "ای", "z": "ز",
        " ": "  ", ",": "،", "!": "!", "?": "؟", ".": ".", "'": "'", "-": "-",
    }
    out = []
    for ch in s:
        out.append(mapping.get(ch, ch))
    return "".join(out)

SCEN = {
    "first": {"title": "🌱 اولین قدم", "steps": [
        {"q": "Hello!", "fa": "سلام!", "ans": "Hello!", "hint": "Hello!", "re": r"hello|hi", "tip": ""},
        {"q": "How are you?", "fa": "حالت چطوره؟", "ans": "I'm fine, thank you.", "hint": "I'm fine, thank you", "re": r"i'?m fine|fine", "tip": "«How are you?» یعنی «حالت چطوره؟»"},
        {"q": "What's your name?", "fa": "اسمت چیه؟", "ans": "My name is Kimia.", "hint": "My name is Kimia", "re": r"(my name is|i'?m)\s+\w+", "tip": ""},
        {"q": "Do you like art?", "fa": "هنر دوست داری؟", "ans": "Yes, I love art!", "hint": "Yes, I love art", "re": r"yes,? i (love|like)", "tip": "جوابِ «Do you...?» با Yes/No شروع می‌شه"},
        {"q": "Thank you! Goodbye!", "fa": "ممنون! خداحافظ!", "ans": "Goodbye!", "hint": "Goodbye", "re": r"(good ?bye|bye)", "tip": ""},
    ]},
    "intro": {"title": "🙋 آشنا شدن", "steps": [
        {"q": "Hi! I'm Sara. What's your name?", "fa": "سلام! من سارام. اسمت چیه؟", "ans": "My name is Kimia.", "hint": "My name is Kimia", "re": r"(my name is|i'?m)\s+\w+", "tip": ""},
        {"q": "Nice to meet you! Where are you from?", "fa": "از آشنایی‌ات خوشحالم! اهل کجایی؟", "ans": "I'm from Iran.", "hint": "I'm from Iran", "re": r"from\s+\w+", "tip": "«from» یعنی «از» — I'm from Iran"},
        {"q": "Iran is beautiful! How old are you?", "fa": "ایران قشنگه! چند سالته؟", "ans": "I'm 25 years old.", "hint": "I'm 25 years old", "re": r"(i'?m|i am)\s*\d+|years?\s*old", "tip": ""},
        {"q": "What's your job?", "fa": "شغلت چیه؟", "ans": "I'm a painter.", "hint": "I'm a painter", "re": r"(i'?m an?|i work|painter|artist|student|teacher)", "tip": "شغل: I'm a painter — «a» یادت نره!"},
        {"q": "Do you like coffee or tea?", "fa": "قهوه دوست داری یا چای؟", "ans": "I like tea.", "hint": "I like tea", "re": r"(tea|coffee|both)", "tip": ""},
        {"q": "Goodbye! Have a nice day!", "fa": "خداحافظ! روز خوبی داشته باشی!", "ans": "Bye! You too!", "hint": "Bye! You too", "re": r"(bye|good ?bye|see you)", "tip": ""},
    ]},
    "cafe": {"title": "☕ کافه", "steps": [
        {"q": "Welcome to Sunny Café! What would you like?", "fa": "به کافه خوش اومدی! چی می‌خوای؟", "ans": "A coffee, please.", "hint": "A coffee, please", "re": r"(i'?d like|can i have|coffee|tea|cake|water)", "tip": "«please» آخرِ جمله = ادب"},
        {"q": "Great choice! Small, medium or large?", "fa": "انتخابِ خوبی بود! کوچیک، متوسط یا بزرگ؟", "ans": "Small, please.", "hint": "Small, please", "re": r"(small|medium|large)", "tip": ""},
        {"q": "Anything else?", "fa": "چیزِ دیگه‌ای هم می‌خوای؟", "ans": "No, thanks!", "hint": "No, thanks", "re": r"(no|nothing|yes|cake|and)", "tip": "«Anything else?» = «چیز دیگه‌ای هم؟»"},
        {"q": "Perfect. That's 5 dollars, please.", "fa": "عالیه. ۵ دلار شد لطفاً.", "ans": "Here you are.", "hint": "Here you are", "re": r"(here|you are|thank|ok|sure)", "tip": ""},
        {"q": "Here's your coffee. Enjoy your day!", "fa": "قهوه‌ت. روز خوبی داشته باشی!", "ans": "Thank you! Bye!", "hint": "Thank you! Bye", "re": r"(thank|thanks|bye)", "tip": ""},
    ]},
    "shop": {"title": "🛍 خرید", "steps": [
        {"q": "Hello! Can I help you?", "fa": "سلام! کمکت کنم؟", "ans": "Yes, please. I'm looking for a gift.", "hint": "Yes, please. I'm looking for a gift", "re": r"(yes|looking|gift|just|no thanks)", "tip": "«I'm looking for...» = «دنبالِ ... می‌گردم»"},
        {"q": "Sure! Who is the gift for?", "fa": "باشه! هدیه برای کیه؟", "ans": "For my mother.", "hint": "For my mother", "re": r"(for my|mother|mom|father|sister|brother|friend|wife)", "tip": ""},
        {"q": "How about this beautiful mug?", "fa": "این ماگِ قشنگ چطوره؟", "ans": "How much is it?", "hint": "How much is it", "re": r"(how much|price|nice|beautiful|yes|ok)", "tip": "«How much is it?» = «چنده؟»"},
        {"q": "It's 20 dollars.", "fa": "۲۰ دلاره.", "ans": "OK, I'll take it!", "hint": "OK, I'll take it", "re": r"(ok|okay|i'?ll take|take it|expensive|too much)", "tip": ""},
        {"q": "Perfect choice! Have a nice day!", "fa": "انتخابِ عالی! روز خوبی داشته باشی!", "ans": "Thanks, you too! Bye!", "hint": "Thanks, you too! Bye", "re": r"(thank|bye|you too)", "tip": ""},
    ]},
}

DRILLS = [
    ["سلام، حالت چطوره؟", "Hi, how are you?"],
    ["من خوبم، ممنون.", "I am fine, thank you."],
    ["اسم من کیمیاست.", "My name is Kimia."],
    ["از ایران هستم.", "I am from Iran."],
    ["من نقاشم.", "I am a painter."],
    ["یه قهوه لطفاً.", "A coffee, please."],
    ["چقدره؟", "How much is it?"],
    ["خیلی گرونه!", "It is too expensive!"],
    ["دنبال یه هدیه می‌گردم.", "I am looking for a gift."],
    ["خوشحالم که آشنا شدیم.", "Nice to meet you."],
    ["امروز هوا قشنگه.", "The weather is nice today."],
    ["ببخشید که دیر کردم.", "Sorry, I am late."],
    ["دوسش دارم!", "I love it!"],
    ["می‌تونم یه سؤال بپرسم؟", "Can I ask a question?"],
    ["منظورت چیه؟", "What do you mean?"],
    ["می‌تونید آروم‌تر حرف بزنید؟", "Can you speak slowly, please?"],
    ["من هر روز انگلیسی تمرین می‌کنم.", "I practice English every day."],
    ["این خیلی قشنگه!", "This is very beautiful!"],
    ["یه لحظه صبر کنید، لطفاً.", "Wait a moment, please."],
    ["روز خوبی داشته باشی!", "Have a nice day!"],
    ["فردا می‌بینمت!", "See you tomorrow!"],
    ["موفق باشی!", "Good luck!"],
]

BOOK = [
    ["🌱 ۱۰ کلمه‌ی اول", [
        ["Yes.", "بله."], ["No.", "نه."], ["Please.", "لطفاً."], ["Thank you.", "ممنون."],
        ["Hello.", "سلام."], ["Goodbye.", "خداحافظ."], ["Sorry.", "ببخشید."], ["OK.", "باشه."],
        ["I don't know.", "نمی‌دونم."], ["How much?", "چنده؟"],
    ]],
    ["👋 سلام و احوال‌پرسی", [
        ["Hi! How are you?", "سلام! حالت چطوره؟"],
        ["I'm fine, thank you.", "من خوبم، ممنون."],
        ["Nice to meet you.", "خوشحالم که آشنا شدیم."],
        ["See you later!", "بعداً می‌بینمت!"],
        ["Have a nice day!", "روز خوبی داشته باشی!"],
    ]],
    ["☕ کافه و رستوران", [
        ["A coffee, please.", "یه قهوه لطفاً."],
        ["Can I have the menu?", "لیست غذا رو می‌تونم داشته باشم؟"],
        ["It's delicious!", "خوشمزه‌ست!"],
        ["The bill, please.", "صورت‌حساب لطفاً."],
        ["Can I pay by card?", "با کارت پرداخت کنم؟"],
    ]],
    ["🛍 خرید", [
        ["How much is it?", "چقدره؟"],
        ["It's too expensive.", "خیلی گرونه."],
        ["I'll take it.", "اینو می‌گیرم."],
        ["Just looking, thanks.", "فقط نگاه می‌کنم، ممنون."],
        ["Do you have another color?", "رنگِ دیگه‌ش رو دارید؟"],
    ]],
    ["✈️ سفر", [
        ["Where is the station?", "ایستگاه کجاست؟"],
        ["Can you help me?", "می‌تونید کمکی کنید؟"],
        ["I'm lost.", "گم شدم."],
        ["What time is it?", "ساعت چنده؟"],
        ["I'd like a ticket.", "یه بلیط می‌خوام."],
    ]],
    ["💗 احساسات", [
        ["I'm happy today.", "امروز شادم."],
        ["I'm a little tired.", "یه ذره خسته‌ام."],
        ["I love this!", "اینو عاشقم!"],
        ["I'm so excited!", "خیلی هیجان‌زاده‌ام!"],
        ["Don't worry.", "نگران نباش."],
    ]],
]

FIXES = [
    [r"\bi\b(?!\w)", "✏️ حرف «I» (من) همیشه بزرگ نوشته می‌شه"],
    [r"i'm agree|i am agree", "✏️ «I agree» — بدون am"],
    [r"have \d+ years? old", "✏️ «I am 20 years old» — با am نه have"],
    [r"\binformations\b", "✏️ «information» جمع نمی‌شه"],
    [r"\bpeoples\b", "✏️ «people» خودش جمعه"],
    [r"didn'?t went", "✏️ بعد از didn't فعل ساده: «didn't go»"],
    [r"more better", "✏️ فقط «better» — خودش تفضیلیه"],
    [r"\badvices\b", "✏️ «advice» جمع نمی‌شه"],
]

PRAISE = ["Great! 👏", "Perfect! ✨", "Well done! 🌟", "Nice! 👍", "Awesome! 😍", "Excellent! 🎉"]

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
def fa_num(n):
    return str(n).translate(FA_DIGITS)

def norm(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s']", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def lev(a, b):
    m, n = len(a), len(b)
    d = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): d[i][0] = i
    for j in range(n + 1): d[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1, d[i-1][j-1] + (a[i-1] != b[j-1]))
    return d[m][n]

# ----------------------------- telegram api -----------------------------

def tg(method, **params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send(chat_id, text, reply_markup=None):
    if len(text) > 4000:
        text = text[:4000]
    return tg("sendMessage", chat_id=chat_id, text=text,
              reply_markup=reply_markup, parse_mode="")

def send_audio_url(chat_id, text, caption):
    url = ("https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=en&q="
           + urllib.parse.quote(text[:180]))
    return tg("sendAudio", chat_id=chat_id, audio=url, caption=caption)

def kb(rows):
    return {"inline_keyboard": rows}

def btn(text, data):
    return {"text": text, "callback_data": data}

MAIN_KB = kb([
    [btn("🐣 مکالمه", "menu:chat"), btn("🎯 تمرین جمله", "menu:drill")],
    [btn("📚 عبارت‌ها", "menu:book")],
])

def scen_kb():
    rows = [[btn(s["title"], f"scen:{k}")] for k, s in SCEN.items()]
    rows.append([btn("🔙 منوی اصلی", "menu:main")])
    return kb(rows)

def book_kb():
    rows = [[btn(c[0], f"book:{i}")] for i, c in enumerate(BOOK)]
    rows.append([btn("🔙 منوی اصلی", "menu:main")])
    return kb(rows)

def step_kb(scen_key, step):
    return kb([
        [btn("🆘 جوابِ نمونه", f"hint:{scen_key}:{step}"), btn("🔁 دوباره بپرس", f"again:{scen_key}:{step}")],
        [btn("⏭ رد کردن", f"skip:{scen_key}:{step}")],
        [btn("🔙 منوی اصلی", "menu:main")],
    ])

# ----------------------------- handlers -----------------------------

def cmd_start(chat_id):
    send(chat_id,
         "🗣 به معلمِ انگلیسیِ تو خوش اومدی!\n\n"
         "این ربات مخصوصِ مبتدی‌هاست:\n"
         "🐣 مکالمه — معلم می‌پرسه، تو جواب می‌دی (فارسی‌ش هم زیرش نوشته شده!)\n"
         "🎯 تمرین جمله — جمله‌ی فارسی رو انگلیسی بگو\n"
         "📚 عبارت‌ها — عبارت‌های کاربردی با تلفظ و صدا 🎧\n\n"
         "✍️ جواب‌ها رو تایپ کن و بفرست. غلط کنی، آروم درستت می‌کنه 🌸\n"
         "برای دیدنِ منو /start رو بفرست.", MAIN_KB)

def scen_question(chat_id, uid):
    s = sessions[uid]
    scen = SCEN[s["scen"]]
    st = scen["steps"][s["step"]]
    text = (f"🗣 {st['q']}\n\n"
            f"🇮🇷 {st['fa']}\n"
            f"🔤 تلفظ: {tr_en(st['q'])}\n\n"
            f"✍️ جوابت رو انگلیسی بنویس و بفرست")
    send(chat_id, text, step_kb(s["scen"], s["step"]))

def scen_answer(uid, chat_id, text):
    s = sessions[uid]
    scen = SCEN[s["scen"]]
    st = scen["steps"][s["step"]]
    fixes = [msg for pat, msg in FIXES if re.search(pat, text, re.I)]
    for f in fixes:
        send(chat_id, f)
    if re.search(st["re"], text, re.I):
        s["good"] += 1
        s["step"] += 1
        send(chat_id, PRAISE[s["step"] % len(PRAISE)] if s["step"] else PRAISE[0])
        if st["tip"]:
            send(chat_id, st["tip"])
        if s["step"] >= len(scen["steps"]):
            total = len(scen["steps"])
            send(chat_id, f"تموم شد! 🎊 {fa_num(s['good'])} از {fa_num(total)} جوابِ کامل — " +
                 ("عالی بود! 🏆" if s["good"] == total else "خوب بود، دوباره تمرین کن 💪"), MAIN_KB)
            s["mode"] = None
        else:
            scen_question(chat_id, uid)
    else:
        send(chat_id, "نزدیک بود! یه بارِ دیگه امتحان کن، یا دکمه‌ی 🆘 رو بزن 💪")

def drill_ask(chat_id, uid):
    s = sessions[uid]
    fa, en = DRILLS[s["drill"] % len(DRILLS)]
    send(chat_id,
         f"🎯 این جمله رو انگلیسی بگو:\n\n« {fa} »\n\n✍️ بنویس و بفرست\n"
         f"(امتیاز: {fa_num(s['score'])} | 🔥 {fa_num(s['streak'])} پشت‌سرهم)",
         kb([[btn("💡 جواب رو نشون بده", "drill:answer"), btn("⏭ بعدی", "drill:next")],
             [btn("🔙 منوی اصلی", "menu:main")]]))

def drill_check(uid, chat_id, text):
    s = sessions[uid]
    fa, en = DRILLS[s["drill"] % len(DRILLS)]
    got, want = norm(text), norm(en)
    tol = 4 if len(want) > 28 else 3 if len(want) > 16 else 2
    if got == want or lev(got, want) <= tol:
        s["score"] += 1
        s["streak"] += 1
        s["drill"] += 1
        send(chat_id, "✅ درست! عالی بود 🎉")
        drill_ask(chat_id, uid)
    else:
        s["streak"] = 0
        send(chat_id, f"❌ درستش:\n\n🇬🇧 {en}\n🔤 {tr_en(en)}")

def show_book_cat(chat_id, idx):
    cat, items = BOOK[idx % len(BOOK)]
    rows = []
    for i, (en, fa) in enumerate(items):
        rows.append([btn(f"🎧 {en}", f"audio:{idx}:{i}")])
    rows.append([btn("🔙 دسته‌ها", "menu:book")])
    text = f"{cat}\n\nبرای شنیدنِ تلفظ، روی هر عبارت بزن 👇"
    send(chat_id, text, kb(rows))

# ----------------------------- update router -----------------------------

def handle_update(upd):
    msg = upd.get("message") or upd.get("edited_message")
    cbq = upd.get("callback_query")
    if cbq:
        uid = cbq["from"]["id"]
        chat_id = cbq["message"]["chat"]["id"]
        data = cbq.get("data", "")
        tg("answerCallbackQuery", callback_query_id=cbq["id"])
        stats["users"].add(uid)
        if data == "menu:main":
            sessions[uid] = {"mode": None}
            cmd_start(chat_id)
        elif data == "menu:chat":
            sessions[uid] = {"mode": None}
            send(chat_id, "یکی رو انتخاب کن 👇", scen_kb())
        elif data == "menu:drill":
            sessions[uid] = {"mode": "drill", "drill": 0, "score": 0, "streak": 0}
            drill_ask(chat_id, uid)
        elif data == "menu:book":
            sessions[uid] = {"mode": None}
            send(chat_id, "یه دسته انتخاب کن 👇", book_kb())
        elif data.startswith("scen:"):
            k = data.split(":", 1)[1]
            sessions[uid] = {"mode": "chat", "scen": k, "step": 0, "good": 0}
            scen_question(chat_id, uid)
        elif data.startswith("hint:"):
            _, k, st = data.split(":")
            stp = SCEN[k]["steps"][int(st)]
            send(chat_id, f"💡 جوابِ نمونه:\n\n🇬🇧 {stp['ans']}\n🔤 {tr_en(stp['ans'])}\n\nحالا خودت با کلماتِ خودت بنویسش!")
        elif data.startswith("again:"):
            _, k, st = data.split(":")
            stp = SCEN[k]["steps"][int(st)]
            send(chat_id, f"🗣 {stp['q']}\n🇮🇷 {stp['fa']}")
        elif data.startswith("skip:"):
            _, k, st = data.split(":")
            s = sessions.setdefault(uid, {"mode": "chat", "scen": k, "step": int(st), "good": 0})
            s["scen"], s["mode"] = k, "chat"
            stp = SCEN[k]["steps"][int(st)]
            send(chat_id, f"جوابِ درست: {stp['ans']}")
            s["step"] = int(st) + 1
            if s["step"] >= len(SCEN[k]["steps"]):
                send(chat_id, "تمام شد! برای شروعِ دوباره /start رو بزن 🌸", MAIN_KB)
                s["mode"] = None
            else:
                scen_question(chat_id, uid)
        elif data.startswith("book:"):
            show_book_cat(chat_id, int(data.split(":")[1]))
        elif data.startswith("audio:"):
            _, ci, ii = data.split(":")
            en, fa = BOOK[int(ci)][1][int(ii)]
            r = send_audio_url(chat_id, en, f"🎧 {en}\n🇮🇷 {fa}\n🔤 {tr_en(en)}")
            if not r.get("ok"):
                send(chat_id, f"🎧 {en}\n🇮🇷 {fa}\n🔤 {tr_en(en)}\n\n(صدا موقتاً در دسترس نیست)")
        elif data == "drill:answer":
            s = sessions.setdefault(uid, {"mode": "drill", "drill": 0, "score": 0, "streak": 0})
            fa, en = DRILLS[s["drill"] % len(DRILLS)]
            send(chat_id, f"💡 {en}\n🔤 {tr_en(en)}")
        elif data == "drill:next":
            s = sessions.setdefault(uid, {"mode": "drill", "drill": 0, "score": 0, "streak": 0})
            s["drill"] += 1
            drill_ask(chat_id, uid)
        return

    if not msg:
        return
    uid = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    stats["users"].add(uid)

    if msg.get("voice") or msg.get("audio"):
        send(chat_id, "فعلاً فقط متن! ✍️ جوابت رو تایپ کن 🌸")
        return

    if text.startswith("/start"):
        sessions[uid] = {"mode": None}
        cmd_start(chat_id)
        return
    if text.startswith("/help"):
        send(chat_id, "🐣 مکالمه • 🎯 تمرین • 📚 عبارت‌ها\nهمه از منوی /start در دسترسه 🌸", MAIN_KB)
        return
    if text.startswith("/stats"):
        if uid == ADMIN_ID:
            mins = int((time.time() - stats["started"]) / 60)
            send(chat_id, f"📊 کاربرانِ این دوره: {fa_num(len(stats['users']))}\n"
                          f"⏱ فعال: {fa_num(mins)} دقیقه\n🤖 در حال اجرا ✅")
        else:
            send(chat_id, "🔒 این دستور فقط برای مدیرِ رباته.")
        return
    if text.startswith("/"):
        send(chat_id, "این دستور رو نمی‌شناسم — /start رو بزن 🌸")
        return

    s = sessions.get(uid)
    if s and s.get("mode") == "chat":
        stats["answers"] += 1
        scen_answer(uid, chat_id, text)
    elif s and s.get("mode") == "drill":
        stats["answers"] += 1
        drill_check(uid, chat_id, text)
    else:
        send(chat_id, "اول یه بخش انتخاب کن 🌸", MAIN_KB)

# ----------------------------- main loop -----------------------------

def main():
    if not TOKEN:
        print("BOT_TOKEN not set")
        return
    tg("deleteWebhook")
    print("polling started", flush=True)
    offset = None
    fails = 0
    while time.time() - START < RUN_SECONDS:
        try:
            params = {"timeout": 50, "allowed_updates": json.dumps(["message", "callback_query"])}
            if offset:
                params["offset"] = offset
            req = urllib.request.Request(
                f"{API}/getUpdates?" + urllib.parse.urlencode(params))
            with urllib.request.urlopen(req, timeout=65) as r:
                data = json.loads(r.read().decode())
            fails = 0
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    handle_update(upd)
                except Exception as e:
                    print("update error:", e, flush=True)
        except Exception as e:
            fails += 1
            print("poll error:", e, flush=True)
            time.sleep(min(30, 3 * fails))
    print("run window finished", flush=True)

if __name__ == "__main__":
    main()
