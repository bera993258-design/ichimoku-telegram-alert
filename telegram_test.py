import os
import urllib.parse
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]
chat_id = os.environ["TELEGRAM_CHAT_ID"]

message = "TEST: Telegram alert is working"

data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": message
}).encode("utf-8")

url = "https://api.telegram.org/bot" + token + "/sendMessage"

request = urllib.request.Request(url, data=data)

with urllib.request.urlopen(request, timeout=30) as response:
    response.read()
