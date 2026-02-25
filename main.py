import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("8769768942:AAFjWjZPI0weRZXkavJLD8kiyjSZVSKFB0s")
ADMIN_ID = @ARPANMODX  # 🔴 PUT YOUR TELEGRAM ID HERE

# ---------------- DATABASE ---------------- #

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_type TEXT,
    account_data TEXT
)
""")

conn.commit()

# ---------------- PRICES ---------------- #

PRICES = {
    "facebook": 25,
    "google": 25,
    "twitter": 25
}

# ---------------- FUNCTIONS ---------------- #

def add_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def add_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def deduct_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def add_stock(account_type, data):
    cursor.execute("INSERT INTO stock (account_type, account_data) VALUES (?, ?)", (account_type, data))
    conn.commit()

def get_stock(account_type):
    cursor.execute("SELECT * FROM stock WHERE account_type=? LIMIT 1", (account_type,))
    item = cursor.fetchone()
    if item:
        cursor.execute("DELETE FROM stock WHERE id=?", (item[0],))
        conn.commit()
        return item[2]
    return None

def get_stock_count(account_type):
    cursor.execute("SELECT COUNT(*) FROM stock WHERE account_type=?", (account_type,))
    return cursor.fetchone()[0]

# ---------------- START ---------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)

    keyboard = [
        [InlineKeyboardButton("💰 ADD FUNDS", callback_data="add_funds")],
        [
            InlineKeyboardButton(f"📘 FACEBOOK ID - ₹{PRICES['facebook']}", callback_data="buy_facebook"),
            InlineKeyboardButton(f"📧 GOOGLE ID - ₹{PRICES['google']}", callback_data="buy_google"),
        ],
        [InlineKeyboardButton(f"🐦 TWITTER ACCOUNT - ₹{PRICES['twitter']}", callback_data="buy_twitter")],
        [
            InlineKeyboardButton("💵 MY BALANCE", callback_data="balance"),
            InlineKeyboardButton("📦 STOCK", callback_data="stock"),
        ],
    ]

    await update.message.reply_text(
        "🤖 Welcome to Account Shop Bot",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ---------------- BUTTON HANDLER ---------------- #

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "balance":
        bal = get_balance(user_id)
        await query.edit_message_text(f"💵 Your Balance: ₹{bal}")

    elif query.data == "stock":
        fb = get_stock_count("facebook")
        gg = get_stock_count("google")
        tw = get_stock_count("twitter")
        await query.edit_message_text(
            f"📦 STOCK AVAILABLE:\n\n"
            f"Facebook: {fb}\n"
            f"Google: {gg}\n"
            f"Twitter: {tw}"
        )

    elif query.data == "add_funds":
        await query.edit_message_text(
            "💰 Send payment to UPI ID:\n\n"
            "7908684711@fam"
            "After payment send screenshot here."
     "@ARPANMODX"   )

    elif query.data.startswith("buy_"):
        account_type = query.data.split("_")[1]
        price = PRICES.get(account_type, 100)

        balance = get_balance(user_id)

        if balance < price:
            await query.edit_message_text(
                f"❌ Not enough balance.\n\nPrice: ₹{price}\nYour Balance: ₹{balance}"
            )
            return

        account = get_stock(account_type)

        if not account:
            await query.edit_message_text("❌ Out of stock.")
            return

        deduct_balance(user_id, price)

        await query.edit_message_text(
            f"✅ Purchase Successful!\n\n"
            f"💰 Deducted: ₹{price}\n\n"
            f"🔐 Your Account:\n{account}"
        )

# ---------------- SCREENSHOT ---------------- #

async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        user_id = update.effective_user.id
        await context.bot.send_message(
            ADMIN_ID,
            f"💰 Payment Screenshot Received\n\n"
            f"User ID: {user_id}\n\n"
            f"Approve with:\n/approve {user_id} 100"
        )
        await update.message.reply_text("✅ Screenshot sent to admin.")

# ---------------- ADMIN COMMANDS ---------------- #

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user_id = int(context.args[0])
    amount = int(context.args[1])

    add_balance(user_id, amount)

    await update.message.reply_text("✅ Balance Added Successfully.")
    await context.bot.send_message(
        user_id,
        f"💰 ₹{amount} added to your balance!"
    )

async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    account_type = context.args[0]
    data = " ".join(context.args[1:])

    add_stock(account_type, data)

    await update.message.reply_text("✅ Stock Added Successfully.")

# ---------------- MAIN ---------------- #

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.PHOTO, screenshot_handler))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("addstock", addstock))

print("Bot Running...")
app.run_polling()