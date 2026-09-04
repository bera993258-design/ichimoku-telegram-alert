import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

SYMBOL = "BTCUSDT"
INTERVAL = "5m"
LIMIT = 100
STATE_FILE = Path("alert_state.json")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

url = (
    "https://api.binance.com/api/v3/klines"
    f"?symbol={SYMBOL}&interval={INTERVAL}&limit={LIMIT}"
)

request = urllib.request.Request(
    url,
    headers={"User-Agent": "Mozilla/5.0"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    candles = json.loads(response.read().decode("utf-8"))

closed_candles = candles[:-1]

highs = [float(c[2]) for c in closed_candles]
lows = [float(c[3]) for c in closed_candles]
closes = [float(c[4]) for c in closed_candles]
times = [int(c[0]) for c in closed_candles]

def midpoint(index, period):
    highest = max(highs[index - period + 1:index + 1])
    lowest = min(lows[index - period + 1:index + 1])
    return (highest + lowest) / 2

last_index = len(closed_candles) - 1

tenkan_now = midpoint(last_index, 9)
kijun_now = midpoint(last_index, 26)
tenkan_previous = midpoint(last_index - 1, 9)
kijun_previous = midpoint(last_index - 1, 26)

bullish_cross = tenkan_previous <= kijun_previous and tenkan_now > kijun_now
bearish_cross = tenkan_previous >= kijun_previous and tenkan_now < kijun_now

if bullish_cross:
    signal = "BULLISH: Tenkan crossed ABOVE Kijun"
elif bearish_cross:
    signal = "BEARISH: Tenkan crossed BELOW Kijun"
else:
    signal = None

if signal:
    candle_id = str(times[last_index])
    state = {}

    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    if state.get("last_alert_candle") != candle_id:
        message = (
            "ICHIMOKU ALERT
"
            "Pair: " + SYMBOL + "
"
            "Timeframe: " + INTERVAL + "
"
            "Signal: " + signal + "
"
            "Close: " + format(closes[last_index], ",.2f") + "
"
            "Tenkan: " + format(tenkan_now, ",.2f") + "
"
            "Kijun: " + format(kijun_now, ",.2f") + "
"
            "Candle: closed"
        )

        payload = urllib.parse.urlencode(
            {"chat_id": CHAT_ID, "text": message}
        ).encode("utf-8")

        telegram_request = urllib.request.Request(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        with urllib.request.urlopen(telegram_request, timeout=30):
            pass

        STATE_FILE.write_text(
            json.dumps({"last_alert_candle": candle_id}),
            encoding="utf-8"
        )
