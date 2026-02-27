from flask import Flask
from threading import Thread
import os

app = Flask("keep_alive_bot")

@app.route("/")
def home():
    return "Bot is alive"

def run():
    port = int(os.environ.get("PORT", 8080))  # Railway assigns this port
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run).start()