import sqlite3
import os
import sys
import random
import io
from io import BytesIO
from datetime import datetime
import re
import time

from PIL import Image, ImageDraw, ImageFont
import pytesseract
import matplotlib.pyplot as plt   # charts/stats
import csv                        # file export
import numpy as np                # advanced math
import random
from datetime import datetime
import qrcode
from moviepy.editor import ImageSequenceClip
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
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
ADMIN_ID = 7853887140
OWNER_USERNAME = "@ARPANMODX"
UPI_ID = "7908684711@fam"
QR_IMAGE_PATH = "upi_qr.png"
REF_BONUS = 1  # ₹1 per referral
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

# Wallet table
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
cursor.execute("""
 CREATE TABLE IF NOT EXISTS verified_users (
    user_id INTEGER PRIMARY KEY
)
""")    

conn.commit(){}

# ================= PRICES ================= #
PRICES = {
    "facebook": 25,
    "google": 25,
    "twitter": 25,
    "guest": 20
}

# ================= HELPERS ================= #
REF_BONUS = 1  # Example referral bonus, adjust as needed

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
            cur.execute("UPDATE users SET balance=balance+?, referred_count=referred_count+1 WHERE user_id=?", (REF_BONUS, ref))
            cur.execute("INSERT INTO referrals (referrer, referred) VALUES (?,?)", (ref, uid))
    conn.commit()

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
    cur.execute("DELETE FROM stock WHERE id=?", (r[0],))
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
   
def is_verified(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM verified_users WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None


def add_verified(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO verified_users (user_id) VALUES (?)", (user_id,))
    
#_______invoice________#
def mask_text(text):
    if len(text) <= 4:
        return "****"
    return text[:2] + "****" + text[-2:]    
    
    conn.commit()
    
# ================= PREMIUM INVOICE =================
def invoice_img(uid, name, username, product, price, bal):
    # ===== GENERATE IDS =====
    order_id = random.randint(18000, 19000)
    txn_id = f"TXN{random.randint(100000,999999)}"

    # ===== BASE IMAGE =====
    img = Image.new("RGB", (1100, 650), "#0a0a0a")
    d = ImageDraw.Draw(img)

    gold = (255, 215, 0)
    soft_gold = (212, 175, 55)
    white = (255, 255, 255)
    gray = (140, 140, 140)

    # ===== FONTS =====
    try:
        title = ImageFont.truetype("arial.ttf", 52)
        sub = ImageFont.truetype("arial.ttf", 28)
        small = ImageFont.truetype("arial.ttf", 22)
        big = ImageFont.truetype("arial.ttf", 36)
    except:
        title = sub = small = big = ImageFont.load_default()

    # ===== HEADER GLOW =====
    for i in range(6):
        d.text((300-i, 25-i), "💎 *ARPAN MODX 8 LEVEL SELL BOT* 💎", font=title, fill=(255, 215, 0))
    d.text((300, 25), "💎 *ARPAN MODX 8 LEVEL SELL BOT* 💎", font=title, fill=gold)

    # ===== DIVIDER =====
    d.line((80, 110, 1020, 110), fill=soft_gold, width=3)

    # ===== LEFT BOX (USER INFO) =====
    d.rectangle((60, 140, 550, 300), outline=soft_gold, width=2)

    d.text((80, 160), f"👤 Name: {name}", fill=white, font=sub)
    d.text((80, 200), f"🔗 Username: @{username}", fill=white, font=sub)
    d.text((80, 240), f"🆔 User ID: {uid}", fill=white, font=sub)

    # ===== RIGHT BOX (ORDER INFO) =====
    d.rectangle((580, 140, 1020, 300), outline=soft_gold, width=2)

    d.text((600, 160), f"🧾 Order ID: {order_id}", fill=gold, font=sub)
    d.text((600, 200), f"🔐 Txn ID: {txn_id}", fill=white, font=sub)
    d.text((600, 240), datetime.now().strftime("📅 %d %b %Y"), fill=gray, font=sub)

    # ===== PRODUCT BOX =====
    d.rectangle((60, 330, 1020, 480), outline=soft_gold, width=2)

    d.text((80, 350), f"📦 Product: {product}", fill=white, font=sub)
    d.text((80, 390), f"💰 Amount Paid: ₹{price}", fill=gold, font=big)
    d.text((80, 430), f"💎 Remaining Balance: ₹{bal}", fill=white, font=sub)

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
    d.text((750, 60), stamp_text, font=big, fill=(0, 255, 120))

    # ===== WATERMARK =====
    for i in range(0, 1100, 300):
        d.text((i, 580), "👑 ARPANMODX", font=small, fill=(40, 40, 40))

    # ===== FOOTER =====
    d.rectangle((0, 590, 1100, 650), fill=gold)
    d.text((350, 605), "ARPANMODX ULTRA PREMIUM SYSTEM", fill="black", font=sub)

    # ===== SAVE =====
    file = f"ultra_invoice_{order_id}.png"
    img.save(file)

    return file

def promo_invoice(uid, code, amt, before, after):
    width, height = 1000, 620

    # 🖤 Base background + blur
    base = Image.new("RGB", (width, height), "#050505")
    img = base.filter(ImageFilter.GaussianBlur(2))
    draw = ImageDraw.Draw(img)

    gold = (255, 215, 0)

    # 🎟 Invoice + TXN
    invoice_id = random.randint(18000, 19000)
    txn_id = "TXN" + str(random.randint(100000, 999999))
    time_now = datetime.now().strftime("%d %b %Y | %I:%M %p")

    try:
        title = ImageFont.truetype("arial.ttf", 44)
        bold = ImageFont.truetype("arial.ttf", 30)
        text = ImageFont.truetype("arial.ttf", 24)
        small = ImageFont.truetype("arial.ttf", 20)
    except:
        title = bold = text = small = ImageFont.load_default()

    # ✨ GOLD HEADER GRADIENT
    for i in range(160):
        draw.rectangle([(0, i), (width, i+1)], fill=(255, 200 - i//3, 0))

    draw.text((260, 50), "💎 *ARPAN MODX 8 LEVEL SELL BOT* 💎", fill="black", font=title)

    # 🧾 GLASS CARD
    card = Image.new("RGBA", (900, 400), (20, 20, 20, 230))
    img.paste(card, (50, 170), card)

    draw = ImageDraw.Draw(img)

    # 🟡 BORDER GLOW
    for i in range(3):
        draw.rectangle([(50-i,170-i),(950+i,570+i)], outline=gold)

    # 👤 LEFT SIDE INFO
    y = 210
    gap = 45

    draw.text((90, y), f"👤 User ID: {uid}", fill="white", font=bold); y += gap
    draw.text((90, y), f"🎟 Promo: {code}", fill=gold, font=bold); y += gap
    draw.text((90, y), f"🧾 Invoice: #{invoice_id}", fill="white", font=text); y += gap
    draw.text((90, y), f"🔖 TXN: {txn_id}", fill=gold, font=text); y += gap

    draw.text((90, y), f"💰 Added: ₹{amt}", fill=gold, font=bold); y += gap
    draw.text((90, y), f"📉 Before: ₹{before}", fill="gray", font=text); y += gap
    draw.text((90, y), f"📈 After: ₹{after}", fill=gold, font=bold); y += gap

    draw.text((90, y), f"⏰ {time_now}", fill="gray", font=small)

    # 💎 RIGHT BONUS BOX
    draw.rounded_rectangle([(600,240),(900,450)], radius=25, outline=gold, width=3)

    draw.text((660, 260), "💎 BONUS", fill=gold, font=bold)
    draw.text((680, 330), f"+ ₹{amt}", fill="white", font=title)

    # 🔳 QR CODE (TXN BASED)
    qr = qrcode.make(txn_id).resize((120,120))
    img.paste(qr, (780, 460))

    # ✨ GLOW EFFECT
    for i in range(25):
        draw.ellipse((650-i, 260-i, 920+i, 480+i), outline=(255,215,0,40))

    # 🟡 FOOTER
    draw.rectangle([(0, height-70), (width, height)], fill=gold)
    draw.text((250, height-50), "✔ VERIFIED • PREMIUM SYSTEM • SECURE BY ARPAN MODX", fill="black", font=small)

    file = f"promo_{uid}.png"
    img.save(file)
    return file

# ================= KEYBOARD ================= #
def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🟢 ADD FUNDS"],
            ["🔵 FACEBOOK ₹25", "🔵 GOOGLE ₹25"],
            ["🔵 TWITTER ₹25", "🔵 GUEST ₹20"],
            ["🟡 STOCK", "🟡 MY BALANCE"],
            ["🟣 PROMO CODE", "🟣 REFER & EARN"],
            ["⭐ PAID PUSH⭐", "🔗 CHANNEL"],
            ["⚫ CONTACT OWNER"]
        ],
        resize_keyboard=True
    )

# ================= START ================= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 🔒 Verification check
    if not is_verified(user_id):
        contact_button = KeyboardButton("📱 Share Phone Number", request_contact=True)

        keyboard = ReplyKeyboardMarkup(
            [[contact_button]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        # Optional join button
        join_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel ", url=CHANNEL_LINK)]
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

    # ✅ AFTER VERIFIED (NO IMAGE)
    caption = (
        "⚡🔥 *WELCOME TO ARPAN MODX STORE* 🔥⚡\n\n"
        "━━━━━━━━━━━━━━━\n"
        "⚡ Instant Delivery\n"
        "🔒 100% Secure\n"
        "💎 Premium Services\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🛒 Buy Now • Fast Delivery • Trusted"
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
    # screenshot code here
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

    # 🤖 OCR AI
    file = await context.bot.get_file(photo)
    image_bytes = await file.download_as_bytearray()

    img = Image.open(BytesIO(image_bytes))
    text = pytesseract.image_to_string(img)

    match = re.findall(r"\d+", text)
    detected_amount = int(match[0]) if match else 0

    user_amount = pending_payments[uid]["amount"]

    # ⚠️ Smart Warning
    warning = ""
    if detected_amount == 0:
        warning = "⚠️ *AI could not detect amount clearly*"
    elif detected_amount != user_amount:
        warning = f"⚠️ *Mismatch!* (User ₹{user_amount} / AI ₹{detected_amount})"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")
        ]
    ])

    # 👑 ADMIN VIEW (PREMIUM)
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"""🔥 *NEW PAYMENT REQUEST*

━━━━━━━━━━━━━━━
👤 *User:* @{user.username if user.username else 'NoUsername'}
🆔 *User ID:* `{uid}`
💰 *Amount:* ₹{user_amount}
🤖 *AI Detected:* ₹{detected_amount}
━━━━━━━━━━━━━━━

{warning}

⚡ *Choose action below 👇*""",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    # 👤 USER CONFIRMATION (PREMIUM)
    await update.message.reply_text(
        """✅ *PAYMENT SUBMITTED*

━━━━━━━━━━━━━━━
🕒 Waiting for admin approval
💰 Balance will be updated soon
━━━━━━━━━━━━━━━

⚡ Please wait patiently""",
        parse_mode="Markdown"
    )    ...

# 👇 SECOND FUNCTION (NOT INSIDE ABOVE)
async def payment_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # approve/reject code here
    query = update.callback_query
    data = query.data

    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    uid = int(data.split("_")[1])

    if uid not in pending_payments:
        return

    amount = pending_payments[uid]["amount"]

    # ✅ APPROVE
    if data.startswith("approve"):
        add_balance(uid, amount)

        # 👤 USER MESSAGE (PREMIUM)
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

        # 👑 ADMIN UPDATE (PREMIUM)
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
        # 👤 USER MESSAGE (PREMIUM)
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

        # 👑 ADMIN UPDATE (PREMIUM)
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

    name = user.first_name
    username = user.username if user.username else "No Username"
    user_id = user.id
    phone = contact.phone_number

    # ✅ SAVE IN DATABASE
    add_verified(user_id)

    text = (
        f"🆕 New User Verified!\n\n"
        f"👤 Name: {name}\n"
        f"🔗 Username: @{username}\n"
        f"🆔 User ID: {user_id}\n"
        f"📞 Phone: {phone}"
    )

    # Send to owner
    await context.bot.send_message(chat_id=OWNER_ID, text=text)

    # Forward contact
    await update.message.forward(chat_id=OWNER_ID)

    # 🔥 Go to start again
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
        f"👥 REFER & EARN\n\n🔗 {link}\n\nEarn ₹{REF_BONUS} per referral\nTotal Referrals: {referral_count(uid)}"
    )

async def update_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("♻️ Restarting bot... press /start")
    os.execl(sys.executable, sys.executable, *sys.argv)

# ================= MENU ================= #
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 ADMIN PANEL",
        reply_markup=admin_panel()
    )
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
text = update.message.text.strip()

# 💰 PAYMENT AMOUNT INPUT
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
    
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id  
    text = update.message.text
    uid = update.effective_user.id

   if text == "🟡 MY BALANCE":
    await update.message.reply_text(
        f"💰 *WALLET DASHBOARD*\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💎 Balance: *₹{balance(uid)}*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🛒 Ready to shop?\n"
        f"⚡ Buy premium accounts instantly!\n\n"
        f"🔥 Thank you for using our service ❤️",
        parse_mode="Markdown"
    )
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
        f"👉 If you buy 10 accounts,\n"
        f"you only pay *₹200*\n\n"
        
        f"🔥 Hurry up before stock ends!"
        ,
        parse_mode="Markdown"
    )
    
elif text == "🟢 ADD FUNDS":
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
                    "2. Pay using any UPI app (GPay / PhonePe / Paytm)\n"
                    "3. Save UTR (Transaction ID)\n"
                    f"4. Send screenshot or UTR to {OWNER_USERNAME}\n\n"
💳 UPI ID: {UPI_ID}
👤 Owner: {OWNER_USERNAME}
                    "━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ Payment will be verified before adding balance."
                ),
                parse_mode="Markdown"
            )


       

    elif text in ["🔵 FACEBOOK ₹25", "🔵 GOOGLE ₹25", "🔵 TWITTER ₹25", "🔵 GUEST ₹20"]:
        t = ("facebook" if "FACEBOOK" in text else
             "google" if "GOOGLE" in text else
             "twitter" if "TWITTER" in text else
             "guest")

        if balance(uid) < PRICES[t]:
    await update.message.reply_text(
        "❌ *INSUFFICIENT BALANCE*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💰 Your wallet balance is too low\n"
        "⚡ Please add funds to continue\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "👉 Use *ADD FUNDS* to recharge your wallet",
        parse_mode="Markdown"
    )
    return

acc = get_stock(t)

if not acc:
    await update.message.reply_text(
        "❌ *OUT OF STOCK*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "😔 This item is currently unavailable\n"
        "📦 All accounts are sold out\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🔔 Please check back later\n"
        "🔥 New stock will be added soon!",
        parse_mode="Markdown"
    )
    return
    return

deduct(uid, PRICES[t])
save_order(uid, t, acc, PRICES[t])
increase_sold(t)  # 🔥 ADD THIS LINE

await update.message.reply_text(
    f"✅ PURCHASED\n\n{acc}\nRemaining Balance: ₹{balance(uid)}"
       deduct(uid,price)
    bal=balance(uid)

    img=invoice_img(uid,t,price,bal)

    await update.message.reply_text(f"✅ {acc}")
    await update.message.reply_photo(open(img,"rb"))

    file = invoice_img(uid, name, username, product, price, bal)

# Send to user
await update.message.reply_photo(
    photo=open(file, "rb"),
    caption=(
       caption=(
    "🚨💎 *ARPAN MODX 8 LEVEL SELL BOT* 💎🚨\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    "👤 *CUSTOMER PROFILE*\n"
    f"┌ Name: {name}\n"
    f"├ Username: @{username}\n"
    f"└ UID: `{uid}`\n\n"

    "🧾 *ORDER SUMMARY*\n"
    f"┌ Order ID: `{order_id}`\n"
    f"├ Product: {product}\n"
    f"├ Amount Paid: ₹{price}\n"
    f"└ Remaining Balance: ₹{bal}\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "💳 Payment Status: ✅ CONFIRMED\n"
    "⚡ System: AUTO PROCESSED\n"
    "📊 Risk Level: LOW\n"
    "👑 Mode: PREMIUM SHOP TRANSACTION\n\n"

    "🔥 @ARPANMODX CONTROL CENTER"
)"
    )

# ===== 🔥 FORWARD TO OWNER =====
await context.bot.send_photo(
    chat_id=ADMIN_ID,
    photo=open(file, "rb"),
    caption=(
       caption=(
    "🚨💎 **ARPAN MODX 8 LEVEL SELL BOT* 💎🚨\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    "👤 *CUSTOMER PROFILE*\n"
    f"┌ Name: {name}\n"
    f"├ Username: @{username}\n"
    f"└ UID: `{uid}`\n\n"

    "🧾 *ORDER SUMMARY*\n"
    f"┌ Order ID: `{order_id}`\n"
    f"├ Product: {product}\n"
    f"├ Amount Paid: ₹{price}\n"
    f"└ Remaining Balance: ₹{bal}\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "💳 Payment Status: ✅ CONFIRMED\n"
    "⚡ System: AUTO PROCESSED\n"
    "📊 Risk Level: LOW\n"
    "👑 Mode: PREMIUM SHOP TRANSACTION\n\n"

    "🔥 @ARPANMODX CONTROL CENTER"
)
    ),
    parse_mode="Markdown"
)

)

    elif text == "🟣 REFER & EARN":
        await refer_command(update, context)

elif text == "🟣 PROMO CODE":
    awaiting_promo.add(uid)
    await update.message.reply_text(
        "🎁 *🎉 PROMO CODE REWARD TIME! 🎉*\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💌 Send your promo code now and stand a chance to win *₹1–1000*!\n"
        "💎 Fast, secure, and instant bonus will be added to your wallet\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "🔥 Don’t miss out! Enter the code now and grab your reward! 💰",
        parse_mode="Markdown"
    )

    elif text == "⭐ PAID PUSH⭐":
        kb = [
            [InlineKeyboardButton("⭐ 1 STAR — ₹2", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
            [InlineKeyboardButton("⭐⭐ 10 STAR — ₹20", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
            [InlineKeyboardButton("⭐⭐⭐ 25 STAR — ₹50", url=f"https://t.me/{OWNER_USERNAME[1:]}")]
        ]

        await update.message.reply_text(
            f"⭐ PAID PUSH PRICES\n\n"
            f"👤 Owner: {OWNER_USERNAME}\n"
            f"📩 Contact: https://t.me/{OWNER_USERNAME[1:]}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif text == "🔗 CHANNEL":
        kb = [[InlineKeyboardButton("Join Channel", url="https://t.me/+qWBcAAqb33Q3MmE1")]]
        await update.message.reply_text(
            "📢 Join our channel for updates:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif text == "⚫ CONTACT OWNER":
    await update.message.reply_text(
        f"👤 Owner: {OWNER_USERNAME}\n📩 Contact: https://t.me/{OWNER_USERNAME[1:]}"
    )
        
import random  # ensure this is imported at the top

# ================= PROMO HANDLER ================= #
awaiting_promo = set()  # users waiting to send promo code

async def apply_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else update.effective_user.first_name
    name = update.effective_user.first_name
    code = update.message.text.strip().upper()

    # Fetch promo info
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

    cur.execute(
        "INSERT INTO promo_used (user_id, username, code) VALUES (?, ?, ?)",
        (uid, username, code)
    )
    cur.execute("UPDATE promo_codes SET used=used+1 WHERE code=?", (code,))
    conn.commit()

    if used + 1 >= max_uses:
        cur.execute("UPDATE promo_codes SET active=0 WHERE code=?", (code,))
        conn.commit()

    add_balance(uid, amount)

    img = promo_invoice(uid, code, amount, before, after)

    # ================= USER MESSAGE =================
    await update.message.reply_photo(
        photo=open(img, "rb"),
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

    # ================= OWNER FORWARD =================
    await context.bot.send_photo(
        chat_id=OWNER_ID,
        photo=open(img, "rb"),
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
# ================= ADMIN BUTTON ================= #



def admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Promo Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📈 Graph Dashboard", callback_data="admin_graph")],
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("💰 Total Earnings", callback_data="admin_earnings")],
        [InlineKeyboardButton("🚫 Disable Promo", callback_data="admin_disable")],
        [InlineKeyboardButton("📤 Export CSV", callback_data="admin_export")]
    ])

# =============== ADMIN BUTTON FUNCTION =================#
await update.message.reply_text(
    f"""👑 *ADMIN CONTROL CENTER*

━━━━━━━━━━━━━━━
🔐 *Restricted Access Granted*
⚡ Authorized Personnel Only
━━━━━━━━━━━━━━━

🧠 *Command Hub:*
• 📊 System Analytics  
• 📈 Performance Dashboard  
• 👥 User Control Panel  
• 💰 Revenue Insights  
• 🚫 System Restrictions  
• 📤 Data Management  

━━━━━━━━━━━━━━━
🛡 *Admin:* @{OWNER_USERNAME}
🟢 *System Status:* Fully Operational
━━━━━━━━━━━━━━━

⚙️ *Execute your command below* 👇""",
    reply_markup=admin_panel(),
    parse_mode="Markdown"
)

# ================= ADMIN ================= #  
async def addpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    code, amt, uses = context.args
    cur.execute("INSERT INTO promocodes VALUES (?,?,?,0)", (code, int(amt), int(uses)))
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
# Save users
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_user.id)
    await update.message.reply_text("✅ Registered!")

# 🔥 Broadcast
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
    await log_security(update, context, "Tried Admin Command")

    await update.message.reply_text(
        """🚫 *ACCESS DENIED*

━━━━━━━━━━━━━━━
🔒 Admin Only Feature
❌ You are not authorized
━━━━━━━━━━━━━━━""",
        parse_mode="Markdown"
    )
    return

    success = 0
    failed = 0

    # Buttons
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Now", url="https://t.me/ARPANMODX")],
        [InlineKeyboardButton("📩 Contact", url="https://t.me/ARPANMODX")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
if query.from_user.id != ADMIN_ID:
    await context.bot.send_message(
        ADMIN_ID,
        f"""🚨 *SECURITY ALERT*

👤 User ID: {query.from_user.id}
⚠️ Tried to use admin buttons""",
        parse_mode="Markdown"
    )
    return        
    
    # ✅ BEST: Reply method (keeps format)
    if update.message.reply_to_message:
        msg = update.message.reply_to_message

        for user_id in users:
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

    # ✅ Text method with line breaks support
    else:
        text = update.message.text.replace('/broadcast ', '', 1)

        for user_id in users:
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
        f"✅ Done!\n✔ Success: {success}\n❌ Failed: {failed}"
    )

# ================= RUN ================= #
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Command Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("refer", refer_command))
app.add_handler(CommandHandler("update", update_bot))
app.add_handler(CommandHandler("addpromo", addpromo))
app.add_handler(CommandHandler("addstock", addstock_cmd))
app.add_handler(CommandHandler("removestock", removestock_cmd))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("stockstats", stock_stats))
app.add_handler(CommandHandler("broadcast", broadcast)) 
app.add_handler(CallbackQueryHandler(payment_buttons))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))

app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
print("✅ Bot running...")
    app.run_polling()

if__name__== "__main__":
    main()