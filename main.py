import sqlite3
import os
import sys
import random
import io
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import re
import matplotlib.pyplot as plt
import csv

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
users = set()
ADMIN_ID = 7853887140
OWNER_USERNAME = "@ARPANMODX"
UPI_ID = "7908684711@fam"
QR_IMAGE_PATH = "upi_qr.png"
REF_BONUS = 1  # ₹1 per referral
pending_payments = {}
payment_history = []
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
    
    conn.commit()

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

# ================= PROMO TRACKER ================= #
awaiting_promo = set()  # users waiting to send promo code
def create_invoice_image(username, uid, code, amount, order_id):
    width, height = 800, 400
    img = Image.new("RGB", (width, height), color="#1a1a1a")
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype("arial.ttf", 40)
    subtitle_font = ImageFont.truetype("arial.ttf", 24)
    small_font = ImageFont.truetype("arial.ttf", 20)

    # Banner
    draw.rectangle([(0,0),(width,80)], fill="#ffcc00")
    draw.text((width//2,20), "💎 PREMIUM INVOICE 💎", font=title_font, fill="black", anchor="ms")

    # Body
    y = 120
    draw.text((50, y), f"User: @{username}", font=subtitle_font, fill="white")
    y += 50
    draw.text((50, y), f"User ID: {uid}", font=subtitle_font, fill="white")
    y += 50
    draw.text((50, y), f"Promo Code: {code}", font=subtitle_font, fill="white")
    y += 50
    draw.text((50, y), f"Amount Added: ₹{amount}", font=subtitle_font, fill="white")
    y += 50
    draw.text((50, y), f"Order ID: #{order_id}", font=subtitle_font, fill="white")
    y += 60
    draw.text((50, y), f"💬 Contact Owner: @{OWNER_USERNAME}", font=small_font, fill="white")

    # Footer
    draw.rectangle([(0,height-40),(width,height)], fill="#ffcc00")
    draw.text((width//2,height-30), "Thank you for using Premium Services!", font=small_font, fill="black", anchor="ms")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ================= START ================= #
# ✅ REPLACE START FUNCTION HERE
# 🔹 Start command
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
            [InlineKeyboardButton("📢 Join Channel (Optional)", url=CHANNEL_LINK)]
        ])

        await update.message.reply_text(
            "🔐 Please verify yourself first\n\nTap below button 👇",
            reply_markup=keyboard
        )

        await update.message.reply_text(
            "📢 Join our channel for updates (optional)",
            reply_markup=join_btn
        )
        return

    # ✅ AFTER VERIFIED (NO IMAGE)
    caption = (
        "🔥 *WELCOME TO ARPAN MODX STORE* 🔥\n\n"
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

    # 📸 Get File ID from image
# 👇 ADD THIS FUNCTION
async def capture_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if text.isdigit():
        pending_payments[uid] = {
            "amount": int(text),
            "photo": None,
            "status": "waiting_screenshot"
        }

        await update.message.reply_text(
            "💳 *Payment Initiated!*\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💰 Amount Received\n"
            "📸 Please send your *payment screenshot*\n"
            "━━━━━━━━━━━━━━━\n\n"
            "⚡ Make sure screenshot is clear",
            parse_mode="Markdown"
        )


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    if uid not in pending_payments:
        await update.message.reply_text(
            "⚠️ *No Amount Found!*\n\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 Please enter the *payment amount* first\n"
            "Then send screenshot 📸",
            parse_mode="Markdown"
        )
        return

    photo = update.message.photo[-1].file_id
    file = await context.bot.get_file(photo)
    image_bytes = await file.download_as_bytearray()

    # 🧠 AI OCR (extract text)
    img = Image.open(BytesIO(image_bytes))
    text = pytesseract.image_to_string(img)

    # 💰 detect amount from image
    match = re.findall(r"\d+", text)
    detected_amount = int(match[0]) if match else None

    user_amount = pending_payments[uid]["amount"]

    pending_payments[uid]["photo"] = photo
    pending_payments[uid]["detected"] = detected_amount

    # ⚠️ fraud check
    warning = ""
    if detected_amount and detected_amount != user_amount:
        warning = f"⚠️ *Mismatch detected!* (User: ₹{user_amount}, AI: ₹{detected_amount})"

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
        ]
    ]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"""🔥 *NEW PAYMENT REQUEST* 🔥

━━━━━━━━━━━━━━━
👤 User ID: `{uid}`
💰 Amount Sent: ₹{user_amount}
🤖 AI Detected: ₹{detected_amount}
━━━━━━━━━━━━━━━

{warning}

⚡ *Action Required Below 👇*
""",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ *Payment Submitted Successfully!*\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🕒 Waiting for admin approval\n"
        "💰 Funds will be added automatically\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚡ Please wait a few minutes",
        parse_mode="Markdown"
    )
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
    await update.message.reply_text("♻️ Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# ================= MENU ================= #
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
)
import random

order_id = random.randint(18000, 19000)

user = update.effective_user

invoice_text = f"""🧾 INVOICE

👤 User: {user.first_name}
🆔 ID: {user.id}

Order ID: #{order_id}
Product: {t.upper()}
Price: ₹{PRICES[t]}

✅ Completed
"""

# Send to user
await update.message.reply_text(invoice_text)

# Send to owner
await context.bot.send_message(chat_id=OWNER_ID, text=invoice_text)

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
async def apply_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else update.effective_user.first_name
    code = update.message.text.strip().upper()

    # Fetch promo info
    cur.execute("SELECT amount, max_uses, used, active FROM promo_codes WHERE code=?", (code,))
    row = cur.fetchone()

    # INVALID promo
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

    # EXPIRED or INACTIVE promo
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

    # ALREADY USED by this user
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

    # ✅ Add user to promo_used
    cur.execute("INSERT INTO promo_used (user_id, username, code) VALUES (?, ?, ?)", (uid, username, code))
    cur.execute("UPDATE promo_codes SET used=used+1 WHERE code=?", (code,))
    conn.commit()

    # Auto-disable promo if max uses reached
    if used + 1 >= max_uses:
        cur.execute("UPDATE promo_codes SET active=0 WHERE code=?", (code,))
        conn.commit()

    # ✅ Update wallet
    add_balance(uid, amount)

    # Generate order ID
    order_id = random.randint(18000, 19000)

    # Create premium invoice image
    invoice_img = create_invoice_image(username, uid, code, amount, order_id)
    await update.message.reply_photo(
        photo=invoice_img,
        caption=(
            f"🎉 *PROMO APPLIED SUCCESSFULLY!* 🎉\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Amount Added: *₹{amount}*\n"
            "💎 Bonus credited to your wallet\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "🛒 You can now use your balance to buy accounts\n"
            "🔥 Enjoy fast & secure shopping!"
        ),
        parse_mode="Markdown"
    )

    # Auto-forward invoice to OWNER
    await context.bot.send_photo(
        OWNER_ID,
        photo=invoice_img,
        caption=(
            f"🆕 *New Promo Applied!* 💎\n\n"
            f"👤 @{username}\n"
            f"🆔 {uid}\n"
            f"🎟 Promo Code: {code}\n"
            f"💰 Amount: ₹{amount}\n"
            f"🧾 Order ID: #{order_id}\n"
            f"💬 Contact: @{OWNER_USERNAME}"
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

# ================= ADMIN ================= #

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Access Denied")
        return
    await update.message.reply_text(
        f"👑 *ADMIN PANEL*\n\nSelect an option 👇\n\n💬 Contact: @{OWNER_USERNAME}",
        reply_markup=admin_panel(),
        parse_mode="Markdown"
    )
    
async def payment_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if query.from_user.id != ADMIN_ID:
        return

    uid = int(data.split("_")[1])

    if uid not in pending_payments:
        return

    amount = pending_payments[uid]["amount"]

if data.startswith("approve"):
    add_balance(uid, amount)

    await context.bot.send_message(
        uid,
        f"""✅ *PAYMENT APPROVED*

━━━━━━━━━━━━━━━
💰 Amount Added: ₹{amount}
🏦 Wallet Updated Successfully
━━━━━━━━━━━━━━━

⚡ You can now use your balance!
""",
        parse_mode="Markdown"
    )

    await query.edit_message_caption(
        f"""✅ *APPROVED*

━━━━━━━━━━━━━━━
💰 Amount: ₹{amount}
📌 Status: Success
━━━━━━━━━━━━━━━
""",
        parse_mode="Markdown"
    )

    pending_payments.pop(uid)

elif data.startswith("reject"):
    await context.bot.send_message(
        uid,
        """❌ *PAYMENT REJECTED*

━━━━━━━━━━━━━━━
⚠️ Your payment could not be verified
📸 Please send a clear screenshot
━━━━━━━━━━━━━━━

🔁 Try again
""",
        parse_mode="Markdown"
    )

    await query.edit_message_caption(
        """❌ *REJECTED*

━━━━━━━━━━━━━━━
📌 Status: Failed
━━━━━━━━━━━━━━━
""",
        parse_mode="Markdown"
    )

    pending_payments.pop(uid)
        
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
        await update.message.reply_text("❌ Admin only!")
        return

    success = 0
    failed = 0

    # Buttons
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Now", url="https://t.me/ARPANMODX")],
        [InlineKeyboardButton("📩 Contact", url="https://t.me/ARPANMODX")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("stockstats", stock_stats))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(MessageHandler(filters.PHOTO, get_file_id))  # 🔥 IMPORTANT
app.add_handler(MessageHandler(filters.PHOTO, auto_screenshot_to_admin))
app.add_handler(CallbackQueryHandler(payment_buttons))
app.add_handler(MessageHandler(filters.PHOTO, payment_screenshot))
# Message Handler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_text))
app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
print("✅ Bot running...")
    app.run_polling()

if__name__== "__main__":
    main()