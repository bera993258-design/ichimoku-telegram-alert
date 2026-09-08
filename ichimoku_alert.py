import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

# -------------------------
# CONFIG
# -------------------------
PAIRS = [
    "BTC-USDT",
    "SOL-USDT",
    "ETH-USDT",
    "XAU-USDT",
]

INTERVAL = "15m"
LIMIT = 120

CONVERSION_PERIOD = 9
BASE_PERIOD = 27
SPAN_B_PERIOD = 54
LAGGING_PERIOD = 27
LEADING_SHIFT = 27

STATE_FILE = Path("alert_state.json")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# -------------------------
# HELPERS
# -------------------------

def fetch_candles(pair: str):
    url = (
        "https://www.okx.com/api/v5/market/candles"
        + "?instId=" + pair
        + "&bar=" + INTERVAL
        + "&limit=" + str(LIMIT)
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("code") != "0":
        raise RuntimeError(f"OKX API error for {pair}: " + result.get("msg", "unknown"))

    raw_candles = result.get("data", [])
    raw_candles.sort(key=lambda candle: int(candle[0]))

    closed_candles = [
        candle for candle in raw_candles
        if candle[-1] == "1"
    ]

    if len(closed_candles) < SPAN_B_PERIOD + 2:
        # এই pair-এর জন্য skip, error না তুলে
        return None

    highs = [float(candle[2]) for candle in closed_candles]
    lows = [float(candle[3]) for candle in closed_candles]
    closes = [float(candle[4]) for candle in closed_candles]
    times = [int(candle[0]) for candle in closed_candles]

    return highs, lows, closes, times

def midpoint(highs, lows, index, period):
    highest = max(highs[index - period + 1:index + 1])
    lowest = min(lows[index - period + 1:index + 1])
    return (highest + lowest) / 2

def check_and_alert(pair: str, highs, lows, closes, times, state: dict):
    last_index = len(closes) - 1

    tenkan_now = midpoint(highs, lows, last_index, CONVERSION_PERIOD)
    kijun_now = midpoint(highs, lows, last_index, BASE_PERIOD)
    span_a_now = (tenkan_now + kijun_now) / 2
    span_b_now = midpoint(highs, lows, last_index, SPAN_B_PERIOD)

    tenkan_old = midpoint(highs, lows, last_index - 1, CONVERSION_PERIOD)
    kijun_old = midpoint(highs, lows, last_index - 1, BASE_PERIOD)
    span_a_old = (tenkan_old + kijun_old) / 2
    span_b_old = midpoint(highs, lows, last_index - 1, SPAN_B_PERIOD)

    if span_a_old <= span_b_old and span_a_now > span_b_now:
        signal = "BULLISH_KUMO_TWIST: LEADING_SPAN_A_CROSSED_ABOVE_LEADING_SPAN_B"
    elif span_a_old >= span_b_old and span_a_now < span_b_now:
        signal = "BEARISH_KUMO_TWIST: LEADING_SPAN_A_CROSSED_BELOW_LEADING_SPAN_B"
    else:
        signal = ""

    if signal == "":
        return

    candle_id = str(times[last_index])
    pair_key = pair + "_" + INTERVAL

    if state.get(pair_key) == candle_id:
        # এই candle-এ আগেই alert পাঠানো হয়েছে
        return

    text = (
        "ICHIMOKU KUMO TWIST ALERT | "
        + pair
        + " | "
        + INTERVAL
        + " | "
        + signal
        + " | CLOSE="
        + str(closes[last_index])
        + " | TENKAN_9="
        + str(tenkan_now)
        + " | KIJUN_27="
        + str(kijun_now)
        + " | SPAN_A="
        + str(span_a_now)
        + " | SPAN_B_54="
        + str(span_b_now)
        + " | SHIFT=27"
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

    state[pair_key] = candle_id

# -------------------------
# MAIN
# -------------------------

state = {}
if STATE_FILE.exists():
    state = json.loads(STATE_FILE.read_text())

for pair in PAIRS:
    try:
        data = fetch_candles(pair)
    except Exception as e:
        # একটা pair fail করলে অন্যগুলো যেন চালু থাকে
        # চাইলে এখানে logging / print করা যেতে পারে (GitHub Actions log-এ দেখা যাবে)
        continue

    if data is None:
        continue

    highs, lows, closes, times = data
    check_and_alert(pair, highs, lows, closes, times, state)

STATE_FILE.write_text(json.dumps(state))
