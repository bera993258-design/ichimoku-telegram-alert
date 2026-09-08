import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

# -------------------------
# CONFIG
# -------------------------
PAIRS = [
    "B-BTC_USDT",
    "B-ETH_USDT",
    "B-SOL_USDT",
    "B-XAU_USDT",
]

INTERVAL = "15m"
LIMIT = 120

CONVERSION_PERIOD = 9
BASE_PERIOD = 27
SPAN_B_PERIOD = 54
LAGGING_PERIOD = 27
LEADING_SHIFT = 27  # 26 → 27

STATE_FILE = Path("alert_state.json")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# -------------------------
# HELPERS
# -------------------------

def fetch_candles(pair: str):
    url = (
        "https://public.coindcx.com/market_data/candles"
        + "?pair=" + pair
        + "&interval=" + INTERVAL
        + "&limit=" + str(LIMIT)
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    # CoinDCX response: {"candles": [[ts, o, h, l, c], ...]}
    raw_candles = result.get("candles", [])
    if not raw_candles:
        return None

    raw_candles.sort(key=lambda candle: candle[0])

    # CoinDCX সব candle-ই closed ধরে নেওয়া যেতে পারে
    closed_candles = raw_candles

    # Span B + shift + buffer
    if len(closed_candles) < SPAN_B_PERIOD + LEADING_SHIFT + 2:
        return None

    highs = [candle[2] for candle in closed_candles]
    lows = [candle[3] for candle in closed_candles]
    closes = [candle[4] for candle in closed_candles]
    times = [candle[0] for candle in closed_candles]

    return highs, lows, closes, times

def midpoint(highs, lows, index, period):
    highest = max(highs[index - period + 1:index + 1])
    lowest = min(lows[index - period + 1:index + 1])
    return (highest + lowest) / 2

def check_and_alert(pair: str, highs, lows, closes, times, state: dict):
    last_index = len(closes) - 1

    # ভবিষ্যতের index: last + LEADING_SHIFT
    future_index = last_index + LEADING_SHIFT

    if future_index >= len(closes):
        return

    # ভবিষ্যতের candle-এর জন্য Span A ও B
    tenkan_future = midpoint(highs, lows, future_index, CONVERSION_PERIOD)
    kijun_future = midpoint(highs, lows, future_index, BASE_PERIOD)
    span_a_future = (tenkan_future + kijun_future) / 2
    span_b_future = midpoint(highs, lows, future_index, SPAN_B_PERIOD)

    # আগের candle-এর ভবিষ্যতের index (future_index - 1)
    prev_future_index = future_index - 1
    if prev_future_index < SPAN_B_PERIOD:
        return

    tenkan_prev = midpoint(highs, lows, prev_future_index, CONVERSION_PERIOD)
    kijun_prev = midpoint(highs, lows, prev_future_index, BASE_PERIOD)
    span_a_prev = (tenkan_prev + kijun_prev) / 2
    span_b_prev = midpoint(highs, lows, prev_future_index, SPAN_B_PERIOD)

    # Crossover check (ভবিষ্যতের 27-তম candle-এর জন্য)
    if span_a_prev <= span_b_prev and span_a_future > span_b_future:
        signal = "BULLISH_KUMO_TWIST: LEADING_SPAN_A_CROSSED_ABOVE_LEADING_SPAN_B"
    elif span_a_prev >= span_b_prev and span_a_future < span_b_future:
        signal = "BEARISH_KUMO_TWIST: LEADING_SPAN_A_CROSSED_BELOW_LEADING_SPAN_B"
    else:
        signal = ""

    if signal == "":
        return

    candle_id = str(times[last_index])
    pair_key = pair + "_" + INTERVAL

    if state.get(pair_key) == candle_id:
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
        + str(tenkan_future)
        + " | KIJUN_27="
        + str(kijun_future)
        + " | SPAN_A="
        + str(span_a_future)
        + " | SPAN_B_54="
        + str(span_b_future)
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
        continue

    if data is None:
        continue

    highs, lows, closes, times = data
    check_and_alert(pair, highs, lows, closes, times, state)

STATE_FILE.write_text(json.dumps(state))
