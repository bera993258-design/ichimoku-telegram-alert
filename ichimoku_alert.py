import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

PAIR = "B-BTC_INR"
INTERVAL = "5m"
LIMIT = 100
STATE_FILE = Path("alert_state.json")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

url = (
    "https://public.coindcx.com/market_data/candles"
    "?pair=" + PAIR
    + "&interval=" + INTERVAL
    + "&limit=" + str(LIMIT)
)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    raw_candles = json.loads(response.read().decode("utf-8"))

if not isinstance(raw_candles, list) or len(raw_candles) < 60:
    raise RuntimeError("CoinDCX candle data not received")

raw_candles.sort(key=lambda candle: int(candle[0]))

closed_candles = raw_candles[:-1]

highs = [float(candle[2]) for candle in closed_candles]
lows = [float(candle[3]) for candle in closed_candles]
closes = [float(candle[4]) for candle in closed_candles]
times = [int(candle[0]) for candle in closed_candles]

def midpoint(index, period):
    high = max(highs[index - period + 1:index + 1])
    low = min(lows[index - period + 1:index + 1])
    return (high + low) / 2

last_index = len(closed_candles) - 1

tenkan_now = midpoint(last_index, 9)
kijun_now = midpoint(last_index, 26)
tenkan_old = midpoint(last_index - 1, 9)
kijun_old = midpoint(last_index - 1, 26)

if tenkan_old <= kijun_old and tenkan_now > kijun_now:
    signal = "BULLISH_TENKAN_ABOVE_KIJUN"
elif tenkan_old >= kijun_old and tenkan_now < kijun_now:
    signal = "BEARISH_TENKAN_BELOW_KIJUN"
else:
    signal = ""

if signal != "":
    candle_id = str(times[last_index])
    state = {}

    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

    if state.get("last_alert_candle") != candle_id:
        text = (
            "ICHIMOKU ALERT | "
            + PAIR
            + " | "
            + INTERVAL
            + " | "
            + signal
            + " | CLOSE="
            + str(closes[last_index])
        )

        data = urllib.parse.urlencode(
            {"chat_id": CHAT_ID, "text": text}
        ).encode("utf-8")

        telegram_url = (
            "https://api.telegram.org/bot"
            + BOT_TOKEN
            + "/sendMessage"
        )

        telegram_request = urllib.request.Request(
            telegram_url,
            data=data
        )

        with urllib.request.urlopen(
            telegram_request,
            timeout=30
        ) as response:
            response.read()

        STATE_FILE.write_text(
            json.dumps({"last_alert_candle": candle_id})
        )
