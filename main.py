import sqlite3
import os
import sys
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive
keep_alive()

# ================= CONFIG ================= #
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 7853887140
OWNER_USERNAME = "@ARPANMODX"
UPI_ID = "7908684711@fam"
QR_IMAGE_PATH = "upi_qr.png"
REF_BONUS = 1

# ================= DATABASE ================= #
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    referrer_id INTEGER,
    referred_count INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    data TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT PRIMARY KEY,
    amount INTEGER,
    max_uses INTEGER,
    used INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS promo_used (
    user_id INTEGER,
    code TEXT,
    UNIQUE(user_id, code)
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
    if ref:
        cur.execute("UPDATE users SET balance=balance+?, referred_count=referred_count+1 WHERE user_id=?", (REF_BONUS, ref))
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

# ================= KEYBOARD ================= #
def main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🟢 ADD FUNDS"],
            ["🔵 FACEBOOK ₹25", "🔵 GOOGLE ₹25"],
            ["🔵 TWITTER ₹25", "🔵 GUEST ₹20"],
            ["🟡 STOCK", "🟡 MY BALANCE"],
            ["🟣 PROMO CODE", "🟣 REFER & EARN"],
            ["🔴 PAID PUSH"],
            ["⚫ CONTACT OWNER"]
        ],
        resize_keyboard=True
    )

# ================= START ================= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    add_user(uid, ref)
    await update.message.reply_text(
        "🔥 *WELCOME TO 8 LEVEL ID SELLER BOT*\n\nChoose option 👇",
        reply_markup=main_keyboard(),
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
        await update.message.reply_text(f"💰 Balance: ₹{balance(uid)}")

    elif text == "🟡 STOCK":
        await update.message.reply_text(
            f"📦 STOCK\n\n"
            f"Facebook: {stock_count('facebook')}\n"
            f"Google: {stock_count('google')}\n"
            f"Twitter: {stock_count('twitter')}\n"
            f"Guest: {stock_count('guest')}"
        )

    elif text == "🟢 ADD FUNDS":
        await update.message.reply_photo(
            photo=open(QR_IMAGE_PATH, "rb"),
            caption=f"💰 Scan & Pay\n\nUPI: {UPI_ID}\nSend UTR to {OWNER_USERNAME}"
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
        await update.message.reply_text(f"✅ PURCHASED\n\n{acc}\nRemaining Balance: ₹{balance(uid)}")

    elif text == "🟣 REFER & EARN":
        await refer_command(update, context)

    elif text == "🔴 PAID PUSH":
        kb = [
            [InlineKeyboardButton("⭐ 1 STAR — ₹2", url="https://t.me/ARPANMODX")],
            [InlineKeyboardButton("⭐⭐ 10 STAR — ₹20", url="https://t.me/ARPANMODX")],
            [InlineKeyboardButton("⭐⭐⭐ 25 STAR — ₹50", url="https://t.me/ARPANMODX")]
        ]
        await update.message.reply_text(
            "⭐ PAID PUSH PRICES\n\nContact Owner: @ARPANMODX",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif text == "⚫ CONTACT OWNER":
        await update.message.reply_text(f"Contact Owner: {OWNER_USERNAME}")

# ================= MESSAGE HANDLER ================= #
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid, amt = int(context.args[0]), int(context.args[1])
    add_balance(uid, amt)
    await update.message.reply_text("✅ Balance added")

# ================= RUN ================= #
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("refer", refer_command))
app.add_handler(CommandHandler("update", update_bot))
app.add_handler(CommandHandler("addpromo", addpromo))
app.add_handler(CommandHandler("addstock", addstock_cmd))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("Bot running...")
app.run_polling()