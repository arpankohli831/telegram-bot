from telegram.ext import Updater, CommandHandler

TOKEN = "8769768942:AAE9my7p64TxDgi4vGbh-maJQVDVE9EVxjA"

def start(update, context):
    update.message.reply_text("Hello")

updater = Updater(TOKEN, use_context=True)

dp = updater.dispatcher
dp.add_handler(CommandHandler("start", start))

print("Bot Running...")
updater.start_polling()
updater.idle()