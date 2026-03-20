import sqlite3
import os
import sys
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.ext import MessageHandler, filters

# ================= CONFIG ================= #
BOT_TOKEN = "8769768942:AAE9my7p64TxDgi4vGbh-maJQVDVE9EVxjA"
ADMIN_ID = 7853887140
users = set()
OWNER_USERNAME = "@ARPANMODX"
UPI_ID = "7908684711@fam"
QR_IMAGE_PATH = "upi_qr.png"
REF_BONUS = 1  # ₹1 per referral

# ================= DATABASE ================= #
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

# Users table
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    referrer_id INTEGER,
    referred_count INTEGER DEFAULT 0
)
""")

# Stock table
cur.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    data TEXT
)
""")

# Promo codes
cur.execute("""
CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT PRIMARY KEY,
    amount INTEGER,
    max_uses INTEGER,
    used INTEGER DEFAULT 0
)
""")

# Track used promos
cur.execute("""
CREATE TABLE IF NOT EXISTS promo_used (
    user_id INTEGER,
    code TEXT,
    UNIQUE(user_id, code)
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
cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product TEXT,
    account TEXT,
    price INTEGER
)
""")


conn.commit()

# ================= PRICES ================= #
PRICES = {
    "facebook": 25,
    "google": 25,
    "twitter": 25,
    "guest": 20
}

# ================= HELPERS ================= #
def add_user(uid, ref=None):
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))
    if cur.fetchone():
        return
    cur.execute("INSERT INTO users VALUES (?,?,?,?)", (uid, 0, ref, 0))
    if ref and ref != uid:
        cur.execute("SELECT 1 FROM referrals WHERE referrer=? AND referred=?", (ref, uid))
        if not cur.fetchone():
            cur.execute("UPDATE users SET balance=balance+?, referred_count=referred_count+1 WHERE user_id=?", (REF_BONUS, ref))
            cur.execute("INSERT INTO referrals VALUES (?,?)", (ref, uid))
    conn.commit()

def balance(uid):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()[0]

def add_balance(uid, amt):
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
    conn.commit()

def deduct(uid, amt):
    cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid))
    conn.commit()

def add_stock(t, d):
    cur.execute("INSERT INTO stock (type,data) VALUES (?,?)", (t, d))
    conn.commit()

def get_stock(t):
    cur.execute("SELECT id,data FROM stock WHERE type=? LIMIT 1", (t,))
    r = cur.fetchone()
    if not r:
        return None
    cur.execute("DELETE FROM stock WHERE id=?", (r[0],))
    conn.commit()
    return r[1]

def stock_count(t):
    cur.execute("SELECT COUNT(*) FROM stock WHERE type=?", (t,))
    return cur.fetchone()[0]

def referral_count(uid):
    cur.execute("SELECT referred_count FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()[0]
    def increase_sold(t):
    cur.execute("SELECT count FROM sold WHERE type=?", (t,))
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE sold SET count = count + 1 WHERE type=?", (t,))
    else:
        cur.execute("INSERT INTO sold (type, count) VALUES (?, 1)", (t,))

    conn.commit()

def sold_count(t):
    cur.execute("SELECT count FROM sold WHERE type=?", (t,))
    row = cur.fetchone()
    return row[0] if row else 0
    
def save_order(uid, product, acc, price):
    cur.execute(
        "INSERT INTO orders (user_id, product, account, price) VALUES (?,?,?,?)",
        (uid, product, acc, price)
    )
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

# ================= START ================= #
# ✅ REPLACE START FUNCTION HERE
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = """🔥 *WELCOME TO ARPAN MODX STORE* 🔥

━━━━━━━━━━━━━━━
⚡ Instant Delivery  
🔒 100% Secure  
💎 Premium Services  
━━━━━━━━━━━━━━━

🛒 Buy Now • Fast Delivery • Trusted"""

    keyboard = [
        [InlineKeyboardButton("🛒 Buy Now", url="https://t.me/ARPANMODX")],
        [InlineKeyboardButton("📩 Contact Owner", url="https://t.me/ARPANMODX")]
    ]

    await update.message.reply_photo(
        photo="AgACAgUAAxkBAAID1mm9gfVGn9GXIMFMo2qrxg9XUKLPAAKyDWsbHnbQVVujTTnkBUSpAQADAgADeQADOgQ",
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    add_user(uid, ref)
    await update.message.reply_text(
        f"""🔥 *WELCOME TO ARPAN MODX 8 LEVEL ID STORE* 🔥

━━━━━━━━━━━━━━━
⚡ Instant Delivery  
🔒 100% Secure  
💎 Premium Services  
━━━━━━━━━━━━━━━

🛒 Buy Now • Fast Delivery • Trusted""",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )
    # 📸 Get File ID from image
# 👇 ADD THIS FUNCTION
async def get_file_id(update, context):
    if update.message and update.message.photo:
        file_id = update.message.photo[-1].file_id
        await update.message.reply_text(f"FILE ID:\n{file_id}")
        print(file_id)
        
   pending_payments = {} 
   async def payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if update.message.photo:
        file_id = update.message.photo[-1].file_id

        pending_payments[uid] = file_id

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}")],
            [InlineKeyboardButton("❌ REJECT", callback_data=f"reject_{uid}")]
        ])

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=f"💰 Payment Request\nUser: {uid}",
            reply_markup=keyboard
        )

        await update.message.reply_text("✅ Sent to admin for approval")
       
         async def payment_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if query.from_user.id != ADMIN_ID:
        return

    uid = int(data.split("_")[1])

    if "approve" in data:
        add_balance(uid, 50)
        await context.bot.send_message(uid, "✅ Payment Approved ₹50 added")
        await query.edit_message_caption("✅ Approved")

    elif "reject" in data:
        await context.bot.send_message(uid, "❌ Payment Rejected")
        await query.edit_message_caption("❌ Rejected")
        
        async def auto_screenshot_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    photo = update.message.photo[-1].file_id

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo,
        caption=f"📸 Screenshot\n\n🆔 ID: {user.id}\n👤 @{user.username}"
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
        await update.message.reply_text(f"💰 Balance: ₹{balance(uid)}")

elif text == "🟡 STOCK":
    await update.message.reply_text(
        f"📦 STOCK STATUS\n\n"
        f"🔵 Facebook → Available: {stock_count('facebook')} | Sold: {sold_count('facebook')}\n"
        f"🔵 Google → Available: {stock_count('google')} | Sold: {sold_count('google')}\n"
        f"🔵 Twitter → Available: {stock_count('twitter')} | Sold: {sold_count('twitter')}\n"
        f"🔵 Guest → Available: {stock_count('guest')} | Sold: {sold_count('guest')}"
    )
    if stock_count(t) <= 2:
    await update.message.reply_text("⚠️ Only few left!")

    elif text == "🟢 ADD FUNDS":
        if os.path.exists(QR_IMAGE_PATH):
            with open(QR_IMAGE_PATH, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=(
                        f"💰 Scan & Pay\n\n"
                        f"👤 Owner: {OWNER_USERNAME}\n"
                        f"UPI: {UPI_ID}\n\n"
                        f"Send UTR OR SCREENSHOT to {OWNER_USERNAME}"
                    )
                )
        else:
            await update.message.reply_text(
    f"""🇮🇳 UPI PAYMENT (INDIA)
━━━━━━━━━━━━━━━━━━
✨ Steps to Deposit:
1. Copy the UPI ID below.
2. Pay the amount using any UPI App (PhonePe, GPay, etc).
3. Copy the Transaction ID (UTR) after success.
4. Click 'Confirm Payment' and submit your ID.

💳 UPI ID: {UPI_ID}
👤 Owner: {OWNER_USERNAME}

━━━━━━━━━━━━━━━━━━
⚠️ Note: Please confirm payment and send screenshot for verification."""
)

    elif text in ["🔵 FACEBOOK ₹25", "🔵 GOOGLE ₹25", "🔵 TWITTER ₹25", "🔵 GUEST ₹20"]:
        t = ("facebook" if "FACEBOOK" in text else
             "google" if "GOOGLE" in text else
             "twitter" if "TWITTER" in text else
             "guest")

        if balance(uid) < PRICES[t]:
            await update.message.reply_text("❌ Not enough balance")
            return

        acc = get_stock(t)
if not acc:
    await update.message.reply_text("❌ Out of stock")
    return

deduct(uid, PRICES[t])
save_order(uid, t, acc, PRICES[t])
increase_sold(t)  # 🔥 ADD THIS LINE

await update.message.reply_text(
    f"✅ PURCHASED\n\n{acc}\nRemaining Balance: ₹{balance(uid)}"
)
import random

order_id = random.randint(100000, 999999)

await update.message.reply_text(
    f"""🧾 INVOICE

Order ID: #{order_id}
Product: {t.upper()}
Price: ₹{PRICES[t]}

✅ Completed
"""
)
    elif text == "🟣 REFER & EARN":
        await refer_command(update, context)

    elif text == "🟣 PROMO CODE":
        awaiting_promo.add(uid)
        await update.message.reply_text("💌 Send your promo code now:")

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
        
# ================= MESSAGE HANDLER ================= #
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # Check if user is sending a promo code
    if uid in awaiting_promo:
        awaiting_promo.remove(uid)
        code = text.upper()
        cur.execute("SELECT amount, max_uses, used FROM promocodes WHERE code=?", (code,))
        row = cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Invalid promo code")
            return
        amount, max_uses, used = row
        if used >= max_uses:
            await update.message.reply_text("❌ Promo code expired")
            return
        cur.execute("SELECT 1 FROM promo_used WHERE user_id=? AND code=?", (uid, code))
        if cur.fetchone():
            await update.message.reply_text("❌ You have already used this promo code")
            return
        add_balance(uid, amount)
        cur.execute("UPDATE promocodes SET used=used+1 WHERE code=?", (code,))
        cur.execute("INSERT INTO promo_used VALUES (?,?)", (uid, code))
        conn.commit()
        await update.message.reply_text(f"✅ Promo applied! ₹{amount} added to your balance")
        return

    # Otherwise, handle as normal menu
    await menu(update, context)

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

# Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("broadcast", broadcast))
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

print("Bot running...")
app.run_polling()