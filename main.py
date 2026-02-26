import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from keep_alive import keep_alive
keep_alive()
# ================= CONFIG ================= #

BOT_TOKEN = "8769768942:AAE9my7p64TxDgi4vGbh-maJQVDVE9EVxjA"
ADMIN_ID = 123456789
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
CREATE TABLE IF NOT EXISTS sold (
    type TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
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

for t in ["facebook", "google", "twitter", "guest"]:
    cur.execute("INSERT OR IGNORE INTO sold (type,count) VALUES (?,0)", (t,))

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
    if ref == uid:
        ref = None
    cur.execute("INSERT INTO users VALUES (?,?,?,?)", (uid, 0, ref, 0))
    if ref:
        cur.execute("UPDATE users SET balance=balance+?, referred_count=referred_count+1 WHERE user_id=?",
                    (REF_BONUS, ref))
    conn.commit()

def balance(uid):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()[0]

def referral_count(uid):
    cur.execute("SELECT referred_count FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()[0]

def deduct(uid, amt):
    cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, uid))
    conn.commit()

def add_balance(uid, amt):
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt, uid))
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
    cur.execute("UPDATE sold SET count=count+1 WHERE type=?", (t,))
    conn.commit()
    return r[1]

def stock_count(t):
    cur.execute("SELECT COUNT(*) FROM stock WHERE type=?", (t,))
    return cur.fetchone()[0]

def sold_stats():
    cur.execute("SELECT type,count FROM sold")
    return dict(cur.fetchall())

# ================= MAIN MENU ================= #

async def show_menu(chat_id, context):
    kb = [
        [InlineKeyboardButton("💰 ADD FUNDS", callback_data="add_funds")],
        [
            InlineKeyboardButton("📘 Facebook ID", callback_data="buy_facebook"),
            InlineKeyboardButton("📧 Google ID", callback_data="buy_google")
        ],
        [
            InlineKeyboardButton("🐦 Twitter ID", callback_data="buy_twitter"),
            InlineKeyboardButton("🎮 Guest ID ID", callback_data="buy_guest")
        ],
        [
            InlineKeyboardButton("💵 Balance", callback_data="balance"),
            InlineKeyboardButton("📦 Stock", callback_data="stock")
        ],
        [
            InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"),
            InlineKeyboardButton("📊 Statistics", callback_data="stats")
        ],
        [
            InlineKeyboardButton("⭐ PAID PUSH", callback_data="paid_push"),
            InlineKeyboardButton("👤 Owner", url="https://t.me/ARPANMODX")
        ]
    ]
    await context.bot.send_message(chat_id, "🤖 *Main Menu*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================= START ================= #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref = int(context.args[0]) if context.args and context.args[0].isdigit() else None
    add_user(uid, ref)
    await show_menu(update.message.chat_id, context)

# ================= BUTTONS ================= #

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back")]])

    if q.data == "back":
        await show_menu(q.message.chat_id, context)

    elif q.data == "balance":
        await q.edit_message_text(f"💵 Balance: ₹{balance(uid)}", reply_markup=back)

    elif q.data == "stock":
        await q.edit_message_text(
            f"📦 Stock\n\nFacebook: {stock_count('facebook')}\nGoogle: {stock_count('google')}\n"
            f"Twitter: {stock_count('twitter')}\nGuest ID: {stock_count('guest')}",
            reply_markup=back
        )

    elif q.data == "refer":
        link = f"https://t.me/Arpan_8_level_id_sell_bot?start={uid}"
        await q.edit_message_text(
            f"👥 Refer & Earn\n\n{link}\nReferrals: {referral_count(uid)}",
            reply_markup=back
        )

    elif q.data == "stats":
        s = sold_stats()
        total = sum(s.values())
        await q.edit_message_text(
            f"📊 SALES STATS\n\n"
            f"Facebook: {s['facebook']}\nGoogle: {s['google']}\n"
            f"Twitter: {s['twitter']}\nGuest ID: {s['guest']}\n\n"
            f"🔥 Total Sold: {total}",
            reply_markup=back
        )

    elif q.data == "add_funds":
        await q.message.reply_photo(
            photo=open(QR_IMAGE_PATH, "rb"),
            caption="💰 Scan QR\nUPI: 7908684711@fam\nSend UTR after payment"
        )

    elif q.data.startswith("buy_"):
        t = q.data.replace("buy_", "")
        if balance(uid) < PRICES[t]:
            await q.edit_message_text("❌ Not enough balance", reply_markup=back)
            return
        acc = get_stock(t)
        if not acc:
            await q.edit_message_text("❌ Out of stock", reply_markup=back)
            return
        deduct(uid, PRICES[t])
        await q.edit_message_text(f"✅ Purchased\n\n{acc}", reply_markup=back)

    elif q.data == "paid_push":
        kb = [
            [InlineKeyboardButton("⭐ 1 STAR — ₹2", url=f"https://t.me/@ARPANMODX")],
            [InlineKeyboardButton("⭐⭐ 10 STAR — ₹20", url=f"https://t.me/@ARPANMODX")],
            [InlineKeyboardButton("⭐⭐⭐ 25 STAR — ₹50", url=f"https://t.me/@ARPANMODX")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back")]
        ]
        await q.edit_message_text(
            "⭐ PAID PUSH PRICES\n\n1 STAR → ₹2\n10 STAR → ₹20\n25 STAR → ₹50",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ================= ADMIN ================= #

async def addstock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        add_stock(context.args[0], " ".join(context.args[1:]))
        await update.message.reply_text("✅ Stock added")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        uid, amt = int(context.args[0]), int(context.args[1])
        add_balance(uid, amt)
        await context.bot.send_message(uid, f"✅ ₹{amt} added")

# ================= RUN ================= #

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(CommandHandler("addstock", addstock_cmd))
app.add_handler(CommandHandler("approve", approve))

print("Bot running...")
app.run_polling()