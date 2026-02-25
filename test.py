from telegram import Bot

TOKEN = "8769768942:AAE9my7p64TxDgi4vGbh-maJQVDVE9EVxjA"

bot = Bot(TOKEN)

print("Checking token...")
print(bot.get_me())