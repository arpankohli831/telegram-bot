import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from keep_alive import keep_alive
keep_alive()
# ================= CONFIG ================= #
BOT_TOKEN = "8769768942:AAE9my7p64TxDgi4vGbh-maJQVDVE9EVxjA"
ADMIN_ID = 7853887140
OWNER_USERNAME = "@ARPANMODX"  # Owner username everywhere
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
            ["➕ ADD FUNDS"],
            ["📘 FACEBOOK ₹25/", "📧 GOOGLE ₹25/"],
            ["🐦 TWITTER ₹25/", "🎮 GUEST ₹20/"],
            ["💰 MY BALANCE", "📦 STOCK"],
            ["🎁 PROMO CODE", "👥 REFER & EARN"],
            ["⭐ PAID PUSH", "👤 CONTACT OWNER"]
        ],
        resize_keyboard=True
    )

# ================= START ================= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    add_user(uid, ref)
    await update.message.reply_text(
        f"🔥 *WELCOME TO 8 LEVEL ID SELLER BOT*\n\nChoose option 👇",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

# ================= MENU HANDLER ================= #
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "💰 MY BALANCE":
        await update.message.reply_text(f"💵 Balance: ₹{balance(uid)}")

    elif text == "📦 STOCK":
        await update.message.reply_text(
            f"📦 STOCK\n\n"
            f"Facebook: {stock_count('facebook')}\n"
            f"Google: {stock_count('google')}\n"
            f"Twitter: {stock_count('twitter')}\n"
            f"Guest: {stock_count('guest')}"
        )

    elif text == "➕ ADD FUNDS":
        await update.message.reply_photo(
            photo=open(QR_IMAGE_PATH, "rb"),
            caption=f"💰 Scan & Pay\n\nUPI: {UPI_ID}\nSend UTR to {OWNER_USERNAME}"
        )

    elif text in ["📘 FACEBOOK ID", "📧 GOOGLE ID", "🐦 TWITTER ACCOUNT", "🎮 GUEST ID"]:
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
        await update.message.reply_text(f"✅ PURCHASED\n\n{acc}\n💰 Remaining Balance: ₹{balance(uid)}")

    elif text == "👥 REFER & EARN":
        link = f"https://t.me/Arpan_8_level_id_sell_bot?start={uid}"
        await update.message.reply_text(
            f"👥 Refer & Earn\n\n{link}\nEarn ₹{REF_BONUS} per referral"
        )

    elif text == "🎁 PROMO CODE":
        await update.message.reply_text("✏️ Send promo code:")

    elif text == "⭐ PAID PUSH":
        kb = [
            [InlineKeyboardButton("⭐ 1 STAR — ₹2", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
            [InlineKeyboardButton("⭐⭐ 10 STAR — ₹20", url=f"https://t.me/{OWNER_USERNAME[1:]}")],
            [InlineKeyboardButton("⭐⭐⭐ 25 STAR — ₹50", url=f"https://t.me/{OWNER_USERNAME[1:]}")]
        ]

    elif text == "👤 CONTACT OWNER":
    await update.message.reply_text(
        "👤 Contact Owner\n\n"
        "Username: @ARPANMODX\n"
        "📩 Click to message: https://t.me/ARPANMODX"
    )

# ================= PROMO REDEEM ================= #
async def promo_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    uid = update.effective_user.id

    cur.execute("SELECT amount,max_uses,used FROM promocodes WHERE code=?", (code,))
    promo = cur.fetchone()
    if not promo:
        return
    cur.execute("SELECT 1 FROM promo_used WHERE user_id=? AND code=?", (uid, code))
    if cur.fetchone():
        await update.message.reply_text("❌ Promo already used")
        return
    amount, max_uses, used = promo
    if used >= max_uses:
        await update.message.reply_text("❌ Promo expired")
        return

    cur.execute("INSERT INTO promo_used VALUES (?,?)", (uid, code))
    cur.execute("UPDATE promocodes SET used=used+1 WHERE code=?", (code,))
    add_balance(uid, amount)
    conn.commit()

    await update.message.reply_text(f"✅ Promo applied\n₹{amount} added to your balance!")

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
app.add_handler(CommandHandler("addpromo", addpromo))
app.add_handler(CommandHandler("addstock", addstock_cmd))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, promo_redeem))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

print("Bot running...")
app.run_polling()