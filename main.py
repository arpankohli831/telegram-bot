import sqlite3
import os
import sys
import time
import re
import csv
import random
from io import BytesIO
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pytesseract
import qrcode

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ================= CONFIG ================= #
BOT_TOKEN = "8769768942:AAE9my7p64TxDgi4vGbh-maJQVDVE9EVxjA" 

pending_payments = {}
payment_history = []
users = set()
awaiting_promo = set()      
admin_state = {}            

ADMIN_ID = 7853887140
OWNER_ID = ADMIN_ID
OWNER_USERNAME = "@ARPANMODX"
UPI_ID = "7908684711@fam"
QR_IMAGE_PATH = "upi_qr.png"

REF_BONUS = 1
CHANNEL_LINK = "https://t.me/+qWBcAAqb33Q3MmE1"

import sqlite3

# ================= DATABASE ================= #
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

# Users table (add username)
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    referrer_id INTEGER,
    referred_count INTEGER DEFAULT 0
)
""")

# Stock table (add active flag)
cur.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    data TEXT,
    active INTEGER DEFAULT 1
)
""")

# Promo codes table
cur.execute("""
CREATE TABLE IF NOT EXISTS promo_codes (
    code TEXT PRIMARY KEY,
    amount INTEGER,
    max_uses INTEGER,
    used INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
)
""")

# Track used promos by user with username (unique per user/code)
cur.execute("""
CREATE TABLE IF NOT EXISTS promo_used (
    user_id INTEGER,
    username TEXT,
    code TEXT,
    UNIQUE(user_id, code)
)
""")

# Wallet table (MAIN BALANCE SYSTEM ✅)
cur.execute("""
CREATE TABLE IF NOT EXISTS wallet (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")

# Track referrals to prevent duplicate referral bonuses
cur.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    referrer INTEGER,
    referred INTEGER,
    UNIQUE(referrer, referred)
)
""")

# Sold stats table
cur.execute("""
CREATE TABLE IF NOT EXISTS sold (
    type TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
)
""")

# Orders table (add created_at timestamp)
cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product TEXT,
    account TEXT,
    price INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Verified users
cur.execute("""
CREATE TABLE IF NOT EXISTS verified_users (
    user_id INTEGER PRIMARY KEY
)
""")

# Banned users
cur.execute("""
CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY
)
""")

# ✅ PERFORMANCE INDEX (ADDED)
cur.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON users(user_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")

conn.commit()

# ================= PRICES ================= #
PRICES = {
    "facebook": 25,
    "google": 25,
    "twitter": 25,
    "guest": 20
}

# ================= HELPERS ================= #

# ----------------- Users ----------------- #
def add_user(uid, username=None, ref=None):
    """Add a new user and handle referral bonus."""
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))
    if cur.fetchone():
        return

    cur.execute(
        "INSERT INTO users (user_id, username, balance, referrer_id, referred_count) VALUES (?,?,?,?,?)",
        (uid, username, 0, ref, 0)
    )

    # Handle referral bonus
    if ref and ref != uid:
        cur.execute("SELECT 1 FROM referrals WHERE referrer=? AND referred=?", (ref, uid))
        if not cur.fetchone():
            add_balance(ref, REF_BONUS)  # ✅ FIX (use wallet)
            cur.execute(
                "UPDATE users SET referred_count=referred_count+1 WHERE user_id=?",
                (ref,)
            )
            cur.execute("INSERT INTO referrals (referrer, referred) VALUES (?,?)", (ref, uid))

    conn.commit()
    users.add(uid)  # ✅ FIX (important for broadcast)


def get_balance(uid):
    """Return user's balance from wallet table."""
    cur.execute("SELECT balance FROM wallet WHERE user_id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0


def add_balance(uid, amount):
    """Add balance to user in wallet."""
    cur.execute("SELECT balance FROM wallet WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE wallet SET balance=balance+? WHERE user_id=?", (amount, uid))
    else:
        cur.execute("INSERT INTO wallet (user_id, balance) VALUES (?, ?)", (uid, amount))
    conn.commit()


def deduct_balance(uid, amount):
    """Deduct balance from wallet."""
    cur.execute("UPDATE wallet SET balance=balance-? WHERE user_id=?", (amount, uid))
    conn.commit()


# ----------------- Stock ----------------- #
def add_stock(item_type, data):
    cur.execute("INSERT INTO stock (type, data, active) VALUES (?,?,1)", (item_type, data))
    conn.commit()


def get_stock(item_type):
    cur.execute("SELECT id,data FROM stock WHERE type=? AND active=1 LIMIT 1", (item_type,))
    r = cur.fetchone()
    if not r:
        return None

    cur.execute("UPDATE stock SET active=0 WHERE id=?", (r[0],))  # ✅ FIX
    conn.commit()
    return r[1]


def stock_count(item_type):
    cur.execute("SELECT COUNT(*) FROM stock WHERE type=? AND active=1", (item_type,))
    return cur.fetchone()[0]


# ----------------- Referrals ----------------- #
def referral_count(uid):
    cur.execute("SELECT referred_count FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0


# ----------------- Sold Stats ----------------- #
def increase_sold(item_type):
    cur.execute("SELECT count FROM sold WHERE type=?", (item_type,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE sold SET count=count+1 WHERE type=?", (item_type,))
    else:
        cur.execute("INSERT INTO sold (type, count) VALUES (?,1)", (item_type,))
    conn.commit()


def sold_count(item_type):
    cur.execute("SELECT count FROM sold WHERE type=?", (item_type,))
    row = cur.fetchone()
    return row[0] if row else 0


# ----------------- Orders ----------------- #
def save_order(uid, product, account, price):
    cur.execute(
        "INSERT INTO orders (user_id, product, account, price) VALUES (?,?,?,?)",
        (uid, product, account, price)
    )
    conn.commit()  # ✅ FIX


# ----------------- Verified ----------------- #
def is_verified(user_id: int) -> bool:
    cur.execute("SELECT 1 FROM verified_users WHERE user_id = ?", (user_id,))
    return cur.fetchone() is not None  # ✅ FIX


def add_verified(user_id: int):
    cur.execute("INSERT OR IGNORE INTO verified_users (user_id) VALUES (?)", (user_id,))
    conn.commit()  # ✅ FIX


# ----------------- Ban System ----------------- #
def is_banned(uid):
    cur.execute("SELECT 1 FROM banned_users WHERE user_id=?", (uid,))
    return cur.fetchone() is not None


def ban_user(uid):
    cur.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (uid,))
    conn.commit()


def unban_user(uid):
    cur.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
    conn.commit()


# ------- Invoice Helper ------- #
def mask_text(text):
    if len(text) <= 4:
        return "****"
    return text[:2] + "****" + text[-2:]
    
# ================= PREMIUM INVOICE =================
def invoice_img(uid, name, username, product, price, bal, account_email="", account_password=""):
    # ===== GENERATE IDS =====
    order_id = random.randint(18000, 19000)
    txn_id = f"TXN{random.randint(100000,999999)}"

    # ===== BASE IMAGE WITH GRADIENT =====
    img = Image.new("RGB", (1100, 650), "#fefefe")
    d = ImageDraw.Draw(img)

    # Soft gradient background (luxury feel)
    for y in range(650):
        gradient = int(240 + y*0.025)
        d.line((0, y, 1100, y), fill=(gradient, gradient, gradient))

    # ===== COLORS =====
    gold = (212, 175, 55)
    soft_gold = (255, 215, 180)
    dark_gray = (35, 35, 35)
    gray = (120, 120, 120)
    pastel_blue = (200, 220, 255)
    light_shadow = (180, 180, 180)

    # ===== FONTS =====
    try:
        title = ImageFont.truetype("arialbd.ttf", 52)
        sub = ImageFont.truetype("arial.ttf", 28)
        small = ImageFont.truetype("arial.ttf", 22)
        big = ImageFont.truetype("arialbd.ttf", 36)
    except:
        title = sub = small = big = ImageFont.load_default()

    # ===== PREMIUM HEADER =====
    d.text((300, 25), "💎 ARPAN MODX 8 LEVEL SELL BOT 💎", font=title, fill=gold)

    # ===== DIVIDER =====
    d.line((80, 110, 1020, 110), fill=soft_gold, width=3)

    # ===== LEFT BOX (USER INFO) =====
    d.rounded_rectangle((60, 140, 550, 300), radius=20, outline=gold, width=3, fill=(250,250,250))
    d.text((80, 160), f"👤 Name: {name}", fill=dark_gray, font=sub)
    d.text((80, 200), f"🔗 Username: @{username}", fill=dark_gray, font=sub)
    d.text((80, 240), f"🆔 User ID: {uid}", fill=dark_gray, font=sub)

    # ===== RIGHT BOX (ORDER INFO) =====
    d.rounded_rectangle((580, 140, 1020, 300), radius=20, outline=gold, width=3, fill=(250,250,250))
    d.text((600, 160), f"🧾 Order ID: {order_id}", fill=gold, font=sub)
    d.text((600, 200), f"🔐 Txn ID: {txn_id}", fill=dark_gray, font=sub)
    d.text((600, 240), datetime.now().strftime("📅 %d %b %Y"), fill=gray, font=sub)

    # ===== PRODUCT BOX =====
    d.rounded_rectangle((60, 330, 1020, 480), radius=20, outline=gold, width=3, fill=(245,245,245))
    d.text((80, 350), f"📦 Product: {product}", fill=dark_gray, font=sub)
    d.text((80, 390), f"💰 Amount Paid: ₹{price}", fill=gold, font=big)
    d.text((80, 430), f"💎 Remaining Balance: ₹{bal}", fill=dark_gray, font=sub)

    # ===== ACCOUNT BOX =====
    d.rounded_rectangle((60, 490, 1020, 570), radius=20, outline=gold, width=3, fill=(245,245,245))
    d.text((80, 510), f"📧 Email: {account_email}", fill=dark_gray, font=sub)
    d.text((80, 545), f"🔑 Password: {account_password}", fill=dark_gray, font=sub)

    # ===== QR CODE =====
    qr_data = f"""
    ORDER:{order_id}
    UID:{uid}
    USER:{username}
    PRODUCT:{product}
    AMOUNT:{price}
    TXN:{txn_id}
    """
    qr = qrcode.make(qr_data)
    qr = qr.resize((170, 170))
    img.paste(qr, (820, 330))
    d.text((820, 510), "Scan for verification", fill=gray, font=small)

    # ===== PAID STAMP =====
    stamp_text = "✔ PAID"
    d.text((750, 60), stamp_text, font=big, fill=(0, 180, 120))

    # ===== WATERMARK (FADED LUXURY) =====
    watermark = "👑 ARPANMODX"
    for i in range(0, 1100, 300):
        d.text((i, 580), watermark, font=small, fill=(200, 200, 200, 50))

    # ===== FOOTER =====
    d.rounded_rectangle((0, 590, 1100, 650), radius=0, fill=gold)
    d.text((350, 605), "ARPANMODX ULTRA PREMIUM SYSTEM", fill="black", font=sub)

    # ===== SAVE =====
    file = f"luxury_invoice_{order_id}.png"
    img.save(file)

    return file

def promo_invoice(uid, code, amt, before, after):
    width, height = 1000, 620

    # ===== BASE LUXURY BACKGROUND =====
    img = Image.new("RGB", (width, height), "#0a0a0a")
    draw = ImageDraw.Draw(img)

    # subtle gradient for luxury feel
    for y in range(height):
        gradient = int(15 + y*0.1)
        draw.line((0, y, width, y), fill=(gradient, gradient, gradient))

    # ===== COLORS =====
    gold = (212, 175, 55)
    soft_gold = (255, 215, 180)
    white = (245, 245, 245)
    gray = (160, 160, 160)
    black_overlay = (20, 20, 20, 220)

    # ===== FONTS =====
    try:
        title = ImageFont.truetype("arialbd.ttf", 44)
        bold = ImageFont.truetype("arialbd.ttf", 30)
        text = ImageFont.truetype("arial.ttf", 24)
        small = ImageFont.truetype("arial.ttf", 20)
    except:
        title = bold = text = small = ImageFont.load_default()

    # ===== HEADER =====
    for i in range(3):
        draw.text((220-i*2, 40-i*2), "💎 ARPAN MODX 8 LEVEL SELL BOT 💎", font=title, fill=soft_gold)
    draw.text((220, 40), "💎 ARPAN MODX 8 LEVEL SELL BOT 💎", font=title, fill=gold)

    # ===== GLASS MAIN CARD =====
    card = Image.new("RGBA", (900, 400), black_overlay)
    img.paste(card, (50, 170), card)
    draw = ImageDraw.Draw(img)

    # ===== GOLD BORDER GLOW =====
    for i in range(3):
        draw.rounded_rectangle([(50-i,170-i),(950+i,570+i)], outline=soft_gold, width=3, radius=25)

    # ===== LEFT INFO =====
    y = 210
    gap = 45
    invoice_id = random.randint(18000, 19000)
    txn_id = "TXN" + str(random.randint(100000, 999999))
    time_now = datetime.now().strftime("%d %b %Y | %I:%M %p")

    draw.text((90, y), f"👤 User ID: {uid}", fill=white, font=bold); y += gap
    draw.text((90, y), f"🎟 Promo: {code}", fill=gold, font=bold); y += gap
    draw.text((90, y), f"🧾 Invoice: #{invoice_id}", fill=white, font=text); y += gap
    draw.text((90, y), f"🔖 TXN: {txn_id}", fill=gold, font=text); y += gap
    draw.text((90, y), f"💰 Added: ₹{amt}", fill=gold, font=bold); y += gap
    draw.text((90, y), f"📉 Before: ₹{before}", fill=gray, font=text); y += gap
    draw.text((90, y), f"📈 After: ₹{after}", fill=gold, font=bold); y += gap
    draw.text((90, y), f"⏰ {time_now}", fill=gray, font=small)

    # ===== RIGHT BONUS BOX =====
    draw.rounded_rectangle([(600,240),(900,450)], radius=25, outline=gold, width=3, fill=(40,40,40,200))
    draw.text((660, 260), "💎 BONUS", fill=gold, font=bold)
    draw.text((680, 330), f"+ ₹{amt}", fill=white, font=title)

    # ===== QR CODE =====
    qr = qrcode.make(txn_id).resize((120,120))
    img.paste(qr, (780, 460))

    # ===== BONUS GLOW EFFECT =====
    for i in range(20):
        draw.ellipse((650-i, 260-i, 920+i, 480+i), outline=(255,215,0,50))

    # ===== FOOTER =====
    draw.rectangle([(0, height-70), (width, height)], fill=gold)
    draw.text((180, height-50), "✔ VERIFIED • PREMIUM SYSTEM • SECURE BY ARPAN MODX", fill="black", font=small)

    # ===== WATERMARK =====
    watermark = "👑 ARPANMODX"
    for i in range(0, 1100, 300):
        draw.text((i, 580), watermark, fill=(200,200,200,50), font=small)

    # ===== SAVE =====
    file = f"promo_ultra_luxury_{uid}.png"
    img.save(file)
    return file

# ================= KEYBOARD ================= #

from telegram import ReplyKeyboardMarkup

def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["💰 ADD FUNDS", "💸 MY BALANCE"],  # 2 buttons in same row
            ["🔵 FACEBOOK ₹25", "⚪ GOOGLE ₹25"],  # 2 buttons
            ["⚫ TWITTER ₹25", "🔴 GUEST ₹20"],  # 2 buttons
            ["♈ PROMO CODE", "♍ REFER & EARN", "☣️ PROFILE"],  # 3 buttons
            ["⭐ PAID PUSH", "🔍 CONTACT OWNER"],  # 2 buttons
            ["ℹ️ HOW IT WORKS"]  # 1 button
        ],
        resize_keyboard=True
    )
# ================= START ================= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username

    # 🚫 Ban check (FIXED POSITION)
    if is_banned(user_id):
        await update.message.reply_text(
            "🚫 You are banned from using this bot."
        )
        return

    add_user(user_id, username)  # ✅ FIXED

    # 🔒 Verification check
    if not is_verified(user_id):
        contact_button = KeyboardButton("📱 SHARE YOUR PHONE • GET VIP SUPPORT", request_contact=True)

        keyboard = ReplyKeyboardMarkup(
            [[contact_button]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel for more updates", url=CHANNEL_LINK)]
        ])

        await update.message.reply_text(
            "🔐 Please verify yourself first\n\nTap below button 👇",
            reply_markup=keyboard
        )

        await update.message.reply_text(
            "📢 Join our channel for updates for more updates",
            reply_markup=join_btn
        )
        return

    # ✅ AFTER VERIFIED
    caption = (
    "👑💎 *WELCOME TO ARPANMODX 8 LEVEL ID STORE* 💎👑\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ INSTANT DELIVERY • FAST & SAFE\n"
    "🔒 100% VERIFIED PAYMENTS\n"
    "💎 PREMIUM SERVICES ONLY\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🛒 SHOP NOW • INSTANT ACCESS • TRUSTED 🚀"
)

    inline_keyboard = [
        [InlineKeyboardButton("🛒 Buy Now", url="https://t.me/ARPANMODX")],
        [InlineKeyboardButton("📩 Contact Owner", url="https://t.me/ARPANMODX")],
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]
    ]

    await update.message.reply_text(
        caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

    await update.message.reply_text(
        "📋 Main Menu 👇",
        reply_markup=main_keyboard()
    )
# ===== FUNCTIONS =====

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):  

    if not update.message.photo:
        return  # ✅ FIX

    photo = update.message.photo[-1].file_id

    user = update.effective_user
    uid = user.id

    if uid not in pending_payments:
        await update.message.reply_text(
            """⚠️ *NO PAYMENT FOUND*

━━━━━━━━━━━━━━━
💡 Please enter *amount first*
📸 Then send screenshot
━━━━━━━━━━━━━━━""",
            parse_mode="Markdown"
        )
        return

    # ⏳ TIMEOUT CHECK
    if time.time() - pending_payments[uid]["time"] > 300:
        pending_payments.pop(uid, None)

        await update.message.reply_text(
            """⏳ *PAYMENT EXPIRED*

━━━━━━━━━━━━━━━
⚠️ Time limit exceeded (5 minutes)
💳 Please start again
━━━━━━━━━━━━━━━""",
            parse_mode="Markdown"
        )
        return

    # 🤖 OCR AI (SAFE)
    file = await context.bot.get_file(photo)
    image_bytes = await file.download_as_bytearray()

    try:
        img = Image.open(BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
    except:
        text = ""

    match = re.findall(r"\d+", text)
    detected_amount = int(match[0]) if match else 0

    user_amount = pending_payments[uid]["amount"]

    # ⚠️ Smart Warning
    warning = ""
    if detected_amount == 0:
        warning = "⚠️ *AI could not detect amount clearly*"
    elif detected_amount != user_amount:
        warning = f"⚠️ *Mismatch!* (User ₹{user_amount} / AI ₹{detected_amount})"

    username = user.username if user.username else "NoUsername"  # ✅ FIX

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
        ]
    ])

    # 👑 ADMIN VIEW
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"""🔥 *NEW PAYMENT REQUEST*

━━━━━━━━━━━━━━━
👤 *User:* @{username}
🆔 *User ID:* `{uid}`
💰 *Amount:* ₹{user_amount}
🤖 *AI Detected:* ₹{detected_amount}
━━━━━━━━━━━━━━━

{warning}

⚡ *Choose action below 👇*""",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    # 👤 USER CONFIRMATION
    await update.message.reply_text(
        """✅ *PAYMENT SUBMITTED*

━━━━━━━━━━━━━━━
🕒 Waiting for admin approval
💰 Balance will be updated soon
━━━━━━━━━━━━━━━

⚡ Please wait patiently""",
        parse_mode="Markdown"
    )


# 👇 SECOND FUNCTION
async def payment_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    await query.answer()

    # ❌ Only admin allowed
    if query.from_user.id != ADMIN_ID:
        return

    uid = int(data.split("_")[1])

    if uid not in pending_payments:
        await query.edit_message_caption("⚠️ Request expired or not found")
        return

    amount = pending_payments[uid]["amount"]

    # ✅ APPROVE
    if data.startswith("approve"):
        add_balance(uid, amount)

        await context.bot.send_message(
            uid,
            f"""💎 *PAYMENT SUCCESSFUL*

━━━━━━━━━━━━━━━
💰 *Amount Added:* ₹{amount}
🏦 *Wallet Updated Successfully*
━━━━━━━━━━━━━━━

🚀 *You can now purchase instantly!*
🔥 Thank you for trusting us""",
            parse_mode="Markdown"
        )

        await query.edit_message_caption(
            f"""✅ *PAYMENT APPROVED*

━━━━━━━━━━━━━━━
💰 Amount: ₹{amount}
📊 Status: *SUCCESS*
━━━━━━━━━━━━━━━

⚡ Balance credited successfully""",
            parse_mode="Markdown"
        )

        pending_payments.pop(uid, None)

    # ❌ REJECT
    elif data.startswith("reject"):
        await context.bot.send_message(
            uid,
            """❌ *PAYMENT FAILED*

━━━━━━━━━━━━━━━
⚠️ Verification unsuccessful
📸 Please send a *clear screenshot*
━━━━━━━━━━━━━━━

🔁 Try again carefully""",
            parse_mode="Markdown"
        )

        await query.edit_message_caption(
            """❌ *PAYMENT REJECTED*

━━━━━━━━━━━━━━━
📊 Status: *FAILED*
━━━━━━━━━━━━━━━

⚠️ User has been notified""",
            parse_mode="Markdown"
        )

        pending_payments.pop(uid, None)
 
# ================= CONTACT HANDLER ================= 
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    contact = update.message.contact

    # ❌ Fake number check
    if contact.user_id != user.id:
        await update.message.reply_text("❌ Please share your own number!")
        return

    uid = user.id
    name = user.first_name
    username = user.username if user.username else "NoUsername"
    phone = contact.phone_number

    # ✅ Save verified
    add_verified(uid)

    # ✅ SUCCESS MESSAGE
    await update.message.reply_text(
        "✅ Verification Successful!\n\nWelcome 🎉",
        reply_markup=main_keyboard()
    )

    # ================= ADMIN INFO ================= #
    text = (
        f"🆕 *NEW USER VERIFIED*\n\n"
        f"👤 Name: {name}\n"
        f"🔗 Username: @{username}\n"
        f"🆔 User ID: `{uid}`\n"
        f"📞 Phone: `{phone}`"
    )

    # 📩 Send to admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=text,
        parse_mode="Markdown"
    )

    # 📤 Forward contact (extra proof)
    await update.message.forward(chat_id=ADMIN_ID)

    # 🔁 Go to start (show menu)
    await start(update, context)

# ================= COMMANDS ================= #
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM stock")
    stock = cur.fetchone()[0]
    await update.message.reply_text(f"📊 BOT STATS\n\n👥 Users: {users}\n📦 Stock: {stock}")

async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    link = f"https://t.me/Arpan_8_level_id_sell_bot?start={uid}"
    await update.message.reply_text(
        f"♍ REFER & EARN\n\n🔗 {link}\n\nEarn ₹{REF_BONUS} per referral\nTotal Referrals: {referral_count(uid)}"
    )

async def update_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("♻️ Restarting bot... press /start or how to work bot /how")
    os.execl(sys.executable, sys.executable, *sys.argv)
async def how_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
    "🔥 *WELCOME TO ARPANMODX STORE* 🔥\n\n"
    "💎 *8 LEVEL PREMIUM IDS AVAILABLE*\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚡ EASY BUY PROCESS ⚡\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "1️⃣ Add Money via UPI 💰\n"
    "2️⃣ Send Payment Proof screenshot and amount in bot📸\n"
    "3️⃣ Auto Verify in few Minutes ✅\n"
    "4️⃣ Buy ID & Get Instantly ⚡\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔒 Safe & Trusted System\n"
    "🚀 Instant Delivery Guaranteed\n\n"
    "📩 *any problem or direct buyer Contact:* @ARPANMODX",
    parse_mode="Markdown"
)
# ================= MENU ================= #

async def log_security(update: Update, context: ContextTypes.DEFAULT_TYPE, action="Tried Admin Command"):
    user = update.effective_user

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"""🚨 *SECURITY ALERT*

━━━━━━━━━━━━━━━
👤 User: @{user.username if user.username else 'NoUsername'}
🆔 ID: `{user.id}`
⚠️ Action: {action}
━━━━━━━━━━━━━━━

🔒 Unauthorized access attempt detected""",
        parse_mode="Markdown"
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # PROMO CODE INPUT
    if uid in awaiting_promo:
        await apply_promo(update, context)
        return

    # PAYMENT AMOUNT INPUT
    if text.isdigit():
        if uid in pending_payments:
            await update.message.reply_text(
                "⚠️ You already have a pending payment.\n📸 Send screenshot first."
            )
            return

        pending_payments[uid] = {
            "amount": int(text),
            "photo": None,
            "time": time.time()
        }

        await update.message.reply_text(
            """💳 *PAYMENT INITIATED*

━━━━━━━━━━━━━━━
💰 Amount Accepted
📸 Send Screenshot within *5 minutes*
━━━━━━━━━━━━━━━

⚡ After 5 min request expires""",
            parse_mode="Markdown"
        )
        return

    # 💰 BALANCE
    elif text == "💸 MY BALANCE":
        await update.message.reply_text(
            f"💰 *WALLET DASHBOARD*\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💎 Balance: *₹{get_balance(uid)}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🛒 Ready to shop?\n"
            f"⚡ Buy premium accounts instantly!\n\n"
            f"🔥 Thank you for using our service ❤️",
            parse_mode="Markdown"
        )

    # 📦 STOCK
    elif text == "🟡 STOCK":
        await update.message.reply_text(
            f"📦 *STOCK STATUS*\n\n"
            f"🔵 Facebook → Available: {stock_count('facebook')} | Sold: {sold_count('facebook')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔵 Google → Available: {stock_count('google')} | Sold: {sold_count('google')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔵 Twitter → Available: {stock_count('twitter')} | Sold: {sold_count('twitter')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔵 Guest → Available: {stock_count('guest')} | Sold: {sold_count('guest')}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ *Only few left!*\n\n"
            f"💰 *SPECIAL OFFER*\n"
            f"👉 If you buy 10 accounts, you only pay *₹200*\n\n"
            f"🔥 Hurry up before stock ends!",
            parse_mode="Markdown"
        )

    # 💳 ADD FUNDS
    elif text == "💰 ADD FUNDS":
        if os.path.exists(QR_IMAGE_PATH):
            with open(QR_IMAGE_PATH, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=(
                        "💰 *Scan & Pay*\n\n"
                        f"👤 Owner: {OWNER_USERNAME}\n"
                        f"💳 UPI: `{UPI_ID}`\n\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "🇮🇳 *UPI PAYMENT (INDIA)*\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "✨ *Steps to Deposit:*\n"
                        "1. Copy the UPI ID below\n"
                        "2. Pay using any UPI app\n"
                        "3. Save UTR\n"
                        "4. Send Payment Screenshot and amount in bot\n"
                        "5. After Admin VERIFICATION auto add fund few minutes in your wallet\n\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        "⚠️ Payment will be verified before adding balance."
                    ),
                    parse_mode="Markdown"
                )

    # 🛒 BUY PRODUCTS
    elif text in ["🔵 FACEBOOK ₹25", "⚪ GOOGLE ₹25", "⚫ TWITTER ₹25", "🔴 GUEST ₹20"]:
        await handle_purchase(update, context, text)

    # 🟣 PROMO CODE
    elif text == "♈ PROMO CODE":
        await update.message.reply_text(
            "🔥 *PROMO CODE ACTIVATION* 🔥\n\n"
            "🎁 Enter your code & unlock rewards 💎\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ Chance to win 1-10000 rupees💯\n"
            "⚡ Instant Reward System\n"
            "🔒 Safe & Verified\n"
            "🎉 Bonus Surprises Waiting\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💌 Send your promo code now 👇",
            parse_mode="Markdown"
        )

    # 👥 REFER
    elif text == "♍ REFER & EARN":
        await refer_command(update, context)

    # ⭐ PAID PUSH
    elif text == "⭐ PAID PUSH⭐":
        kb = [
            [InlineKeyboardButton("⭐ 1 STAR — ₹2", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
            [InlineKeyboardButton("⭐⭐ 10 STAR — ₹20", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
            [InlineKeyboardButton("⭐⭐⭐ 25 STAR — ₹50", url=f"https://t.me/{OWNER_USERNAME[1:]}")]
        ]
        await update.message.reply_text(
            f"⭐ PAID PUSH PRICES\n\n👤 Owner: {OWNER_USERNAME}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # ℹ️ HOW IT WORKS
    elif text == "ℹ️ HOW IT WORKS":
        await how_command(update, context)

    # 🔗 CHANNEL
    elif text == "🔍 CONTACT OWNER":
        kb = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]]
        await update.message.reply_text(
            f"📢 *Join Our Channel & Contact Info*\n\n"
            f"👤 Owner: {OWNER_USERNAME}\n"
            f"📩 Contact: [Message Owner](https://t.me/{OWNER_USERNAME[1:]})\n\n"
            f"Stay updated with all latest news, promos, and releases!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )

    # 🟠 PROFILE
    elif text == "☣️ PROFILE":
        user = update.effective_user
        await update.message.reply_text(
            f"💎👑 ARPANMODX ELITE USER PROFILE 👑💎\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 NAME       : {user.first_name}\n"
            f"🔗 USERNAME   : @{user.username if user.username else 'NoUsername'}\n"
            f"🆔 USER ID    : `{user.id}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ PREMIUM STATUS: VERIFIED\n"
            "💎 INSTANT ACCESS TO ALL IDS\n"
            "🚀 SHOP WITH CONFIDENCE",
            parse_mode="Markdown"
        )


# ================= HANDLE TEXT ================= #
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid == ADMIN_ID:
        handled = await admin_text(update, context)
        if handled:
            return

    await menu(update, context)

# ================= PROMO HANDLER ================= #
awaiting_promo = set()  # users waiting to send promo code

async def apply_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else update.effective_user.first_name
    name = update.effective_user.first_name
    code = update.message.text.strip().upper()

    # ❌ Only allow if user clicked promo button
    if uid not in awaiting_promo:
        return

    awaiting_promo.remove(uid)

    # 🔍 Fetch promo
    cur.execute("SELECT amount, max_uses, used, active FROM promo_codes WHERE code=?", (code,))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text(
            "❌ *INVALID PROMO CODE*\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🚫 The code you entered is not valid\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 Need a promo code?\n👉 Contact: @{OWNER_USERNAME}",
            parse_mode="Markdown"
        )
        return

    amount, max_uses, used, active = row

    if active == 0 or used >= max_uses:
        await update.message.reply_text(
            "⏳ *PROMO CODE EXPIRED*\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ This promo code has reached its limit or is inactive\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 Contact admin for a new code: @{OWNER_USERNAME}",
            parse_mode="Markdown"
        )
        return

    # ❌ Already used
    cur.execute("SELECT 1 FROM promo_used WHERE user_id=? AND code=?", (uid, code))
    if cur.fetchone():
        await update.message.reply_text(
            "⚠️ *ALREADY USED*\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🔁 You have already applied this promo code\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 Want another code? Contact: @{OWNER_USERNAME}",
            parse_mode="Markdown"
        )
        return

    # 💰 Balance before
    before = get_balance(uid)

    # ✅ Save usage
    cur.execute(
        "INSERT INTO promo_used (user_id, username, code) VALUES (?, ?, ?)",
        (uid, username, code)
    )

    cur.execute("UPDATE promo_codes SET used=used+1 WHERE code=?", (code,))
    conn.commit()

    # 💰 Add balance
    add_balance(uid, amount)

    # 💰 Balance after
    after = get_balance(uid)

    # 🔒 Auto disable if limit reached
    if used + 1 >= max_uses:
        cur.execute("UPDATE promo_codes SET active=0 WHERE code=?", (code,))
        conn.commit()

    # 🧾 Generate invoice
    img = promo_invoice(uid, code, amount, before, after)

    # ================= USER =================
    try:
        with open(img, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=(
                    "🚨💎 *ARPAN MODX 8 LEVEL SELL BOT* 💎🚨\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                    "👤 *USER INFO*\n"
                    f"• Name: {name}\n"
                    f"• Username: @{username}\n"
                    f"• UID: `{uid}`\n\n"

                    "🎟 *REWARD EVENT*\n"
                    f"• Promo Code: `{code}`\n"
                    f"• Reward Type: BONUS CREDIT\n"
                    f"• Amount Added: ₹{amount}\n\n"

                    "💰 *WALLET UPDATE*\n"
                    f"• Before: ₹{before}\n"
                    f"• After: ₹{after}\n\n"

                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ Status: SUCCESSFULLY PROCESSED\n"
                    "📊 System: AUTO REWARD ENGINE\n"
                    "👑 Tier Engine: ACTIVE\n"
                    "🔥 ARPANMODX FINTECH CORE"
                ),
                parse_mode="Markdown"
            )
    except:
        await update.message.reply_text("❌ Error generating promo invoice")

    # ================= OWNER =================
    try:
        with open(img, "rb") as f:
            await context.bot.send_photo(
                chat_id=OWNER_ID,
                photo=f,
                caption=(
                    "🚨💎 *ARPAN MODX 8 LEVEL SELL BOT* 💎🚨\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

                    "👤 *USER INFO*\n"
                    f"• Name: {name}\n"
                    f"• Username: @{username}\n"
                    f"• UID: `{uid}`\n\n"

                    "🎟 *REWARD EVENT*\n"
                    f"• Promo Code: `{code}`\n"
                    f"• Reward Type: BONUS CREDIT\n"
                    f"• Amount Added: ₹{amount}\n\n"

                    "💰 *WALLET UPDATE*\n"
                    f"• Before: ₹{before}\n"
                    f"• After: ₹{after}\n\n"

                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ Status: SUCCESSFULLY PROCESSED\n"
                    "📊 System: AUTO REWARD ENGINE\n"
                    "👑 Tier Engine: ACTIVE\n"
                    "🔥 ARPANMODX FINTECH CORE"
                ),
                parse_mode="Markdown"
            )
    except:
        pass
# ================= ADMIN BUTTON ================= #
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        # If not admin, send a message and return
        await update.message.reply_text("❌ Access Denied. You are not an admin.")
        return

    # Admin only sees this
    await update.message.reply_text(
        "👑 ADMIN PANEL",
        reply_markup=admin_keyboard()
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📊 Promo Stats", "📈 Total Sales"],
            ["👥 Total Users", "💰 Earnings"],
            ["🚫 Disable Promo", "📤 Export CSV"],
            ["🔴 Ban User", "🟢 Unban User"],
            ["🔙 Back"]
        ],
        resize_keyboard=True
    )


# ================= ADMIN ================= #  
admin_state = {}

async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if uid != ADMIN_ID:
        return False

    if text == "📊 Promo Stats":
        cur.execute("SELECT COUNT(*) FROM promo_codes")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM promo_used")
        used = cur.fetchone()[0]

        await update.message.reply_text(f"📊 Promo Codes: {total}\nUsed: {used}")

    elif text == "📈 Total Sales":
        cur.execute("SELECT SUM(price) FROM orders")
        total = cur.fetchone()[0] or 0

        await update.message.reply_text(f"📈 Total Sales: ₹{total}")

    elif text == "👥 Total Users":
        # Fetch all users
        cur.execute("SELECT first_name, username, user_id FROM users")
        users = cur.fetchall()

        total = len(users)
        message = f"👥 Total Users: {total}\n\n"

        # Add each user's info
        for user in users:
            first_name, username, user_id = user
            username_display = f"@{username}" if username else "No Username"
            message += f"• {first_name} ({username_display}) — ID: {user_id}\n"

        # Split message if too long for Telegram
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(message)

    elif text == "💰 Earnings":
        cur.execute("SELECT SUM(price) FROM orders")
        total = cur.fetchone()[0] or 0

        await update.message.reply_text(f"💰 Earnings: ₹{total}")

    elif text == "🚫 Disable Promo":
        cur.execute("UPDATE promo_codes SET active=0")
        conn.commit()

        await update.message.reply_text("🚫 All promo codes disabled")

    elif text == "📤 Export CSV":
        cur.execute("SELECT * FROM orders")
        rows = cur.fetchall()

        with open("orders.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "User", "Product", "Account", "Price", "Date"])
            writer.writerows(rows)

        with open("orders.csv", "rb") as f:
            await update.message.reply_document(f)

    elif text == "🔴 Ban User":
        admin_state[uid] = "ban"
        await update.message.reply_text("Send User ID to ban")

    elif admin_state.get(uid) == "ban" and text.isdigit():
        ban_user(int(text))
        admin_state.pop(uid)
        await update.message.reply_text(f"🚫 User {text} banned")

    elif text == "🟢 Unban User":
        admin_state[uid] = "unban"
        await update.message.reply_text("Send User ID to unban")

    elif admin_state.get(uid) == "unban" and text.isdigit():
        unban_user(int(text))
        admin_state.pop(uid)
        await update.message.reply_text(f"✅ User {text} unbanned")

    elif text == "🔙 Back":
        await update.message.reply_text(
            "📋 Main Menu",
            reply_markup=main_keyboard()
        )

    else:
        return False

    return True

# ================= ADMIN COMMANDS ================= #

async def addpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    code, amt, uses = context.args
    cur.execute(
        "INSERT INTO promo_codes (code, amount, max_uses, used, active) VALUES (?,?,?,?,1)",
        (code, int(amt), int(uses), 0)
    )
    conn.commit()
    await update.message.reply_text("✅ Promo created")


async def addstock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    add_stock(context.args[0], " ".join(context.args[1:]))
    await update.message.reply_text("✅ Stock added")


async def removestock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removestock <type> <data>")
        return

    stock_type = context.args[0].lower()
    stock_data = " ".join(context.args[1:])

    cur.execute("SELECT id FROM stock WHERE type=? AND data=? LIMIT 1", (stock_type, stock_data))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text("❌ Stock not found")
        return

    cur.execute("DELETE FROM stock WHERE id=?", (row[0],))
    conn.commit()

    await update.message.reply_text(f"✅ Stock removed: {stock_type} → {stock_data}")


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    uid, amt = int(context.args[0]), int(context.args[1])
    add_balance(uid, amt)

    await update.message.reply_text("✅ Balance added")


async def stock_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 STOCK STATS\n\n"
        f"Facebook: {stock_count('facebook')}\n"
        f"Google: {stock_count('google')}\n"
        f"Twitter: {stock_count('twitter')}\n"
        f"Guest: {stock_count('guest')}"
    )


# ================= BROADCAST ================= #
# ✅ METHOD 1: REPLY BROADCAST (BEST)
    if update.message.reply_to_message:
        msg = update.message.reply_to_message

        cur.execute("SELECT user_id FROM users")
        all_users = cur.fetchall()

        for user in all_users:
            user_id = user[0]
            try:
                await context.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    reply_markup=reply_markup
                )
                success += 1
            except:
                failed += 1

    # ✅ METHOD 2: TEXT BROADCAST
    else:
        text = update.message.text.replace('/broadcast ', '', 1)

        cur.execute("SELECT user_id FROM users")
        all_users = cur.fetchall()

        for user in all_users:
            user_id = user[0]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                success += 1
            except:
                failed += 1

    await update.message.reply_text(
        f"✅ Broadcast Done\n\n✔ Success: {success}\n❌ Failed: {failed}"
    )

# ================= RUN ================= #
app = ApplicationBuilder().token(BOT_TOKEN).build()  # ✅ FIX

# Command Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("refer", refer_command))
app.add_handler(CommandHandler("update", update_bot))
app.add_handler(CommandHandler("addpromo", addpromo))
app.add_handler(CommandHandler("addstock", addstock_cmd))
app.add_handler(CommandHandler("removestock", removestock_cmd))
app.add_handler(CommandHandler("admin", admin_command))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("stockstats", stock_stats))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CommandHandler("how", how_command))
# Callback
app.add_handler(CallbackQueryHandler(payment_buttons))

# Priority handlers
app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))

# ✅ SINGLE TEXT HANDLER (IMPORTANT)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("✅ Bot running...")
app.run_polling()