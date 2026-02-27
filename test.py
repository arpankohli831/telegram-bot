from telegram import Bot

TOKEN = "8701288395:AAGabCphFdZmJ6tG1A5NH5SzKAAtk0g-JjM"

bot = Bot(TOKEN)

print("Checking token...")
print(bot.get_me())