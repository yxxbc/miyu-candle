#!/usr/bin/env python3
# Description: Compute a technical indicator over Binance candles with TradingView-compatible math (MA, EMA, WMA, RSI, MACD, BOLL, ATR, KDJ, OBV, VWAP) and return the latest value plus a tail of the series.
# Display name: Market indicator
# 显示名称：指标数值
# 描述：按 TradingView 口径在 Binance K 线上算指标（MA、EMA、WMA、RSI、MACD、BOLL、ATR、KDJ、OBV、VWAP），返回最新值和最近几十根。
# Timeout: 45
# Parameters:
# {"type": "object", "properties": {
#   "symbol": {"type": "string", "description": "Ticker such as BTCUSDT; btc becomes BTCUSDT; BTCUSDT.P means USDT-M perpetual"},
#   "interval": {"type": "string", "enum": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"], "description": "Default 1d"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Default spot"},
#   "indicator": {"type": "string", "enum": ["ma", "ema", "wma", "rsi", "macd", "boll", "atr", "kdj", "obv", "vwap"], "description": "Which indicator"},
#   "length": {"type": "integer", "description": "Main period, default 20 for ma/ema/wma, 14 for rsi/atr, 20 for boll, 9 for kdj"},
#   "fast": {"type": "integer", "description": "macd fast EMA, default 12"},
#   "slow": {"type": "integer", "description": "macd slow EMA, default 26"},
#   "signal": {"type": "integer", "description": "macd signal EMA, default 9"},
#   "mult": {"type": "number", "description": "boll band width in standard deviations, default 2"},
#   "source": {"type": "string", "enum": ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"], "description": "Price source for ma/ema/wma/rsi, default close"},
#   "limit": {"type": "integer", "description": "Candles to load, 50-1000, default 300"}
# }, "required": ["symbol", "indicator"]}
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

SPOT = "https://data-api.binance.vision"
FAPI = "https://fapi.binance.com"
QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "BTC", "ETH", "BNB", "EUR", "USD", "TRY", "BRL", "JPY")
INTERVALS = ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")


class Fail(Exception):
    pass


def args():
    raw = os.environ.get("MIYU_ARGS_JSON")
    if raw is None:
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
    return json.loads(raw) if raw and raw.strip() else {}


def http(path, params):
    url = path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "miyu-candle/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(body).get("msg") or body
        except Exception:
            msg = body
        raise Fail("Binance: %s (HTTP %d)" % (msg, e.code))
    except urllib.error.URLError as e:
        raise Fail("network: %s (Binance needs the system proxy in mainland China)" % (e.reason,))


def resolve(symbol, market):
    s = "".join((symbol or "").split()).upper().replace("/", "").replace("-", "").replace("_", "")
    if not s:
        raise Fail("symbol is empty")
    if s.endswith(".P"):
        s, market = s[:-2], "perp"
    if not any(s.endswith(q) and len(s) > len(q) for q in QUOTES):
        s += "USDT"
    return s, (market or "spot")


def interval_of(value):
    v = (value or "1d").strip()
    if v == "1M":
        return v
    low = v.lower()
    if low in INTERVALS:
        return low
    raise Fail("interval %r is not one of %s" % (value, ", ".join(INTERVALS)))


def candles(symbol, interval, limit, market):
    if market == "perp":
        rows = http(FAPI + "/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    else:
        rows = http(SPOT + "/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows]


# --- indicator math ---

def pick(data, source):
    if source == "open":
        return [d[1] for d in data]
    if source == "high":
        return [d[2] for d in data]
    if source == "low":
        return [d[3] for d in data]
    if source == "hl2":
        return [(d[2] + d[3]) / 2 for d in data]
    if source == "hlc3":
        return [(d[2] + d[3] + d[4]) / 3 for d in data]
    if source == "ohlc4":
        return [(d[1] + d[2] + d[3] + d[4]) / 4 for d in data]
    if source == "close":
        return [d[4] for d in data]
    raise Fail("source %r is not one of close, open, high, low, hl2, hlc3, ohlc4" % (source,))


def sma(vals, n):
    out = [None] * len(vals)
    total = 0.0
    for i, v in enumerate(vals):
        total += v
        if i >= n:
            total -= vals[i - n]
        if i >= n - 1:
            out[i] = total / n
    return out


def ema(vals, n):
    """TradingView ta.ema: seed with the SMA of the first n values."""
    out = [None] * len(vals)
    k = 2.0 / (n + 1)
    prev = None
    seen = 0
    for i, v in enumerate(vals):
        if v is None:
            continue
        seen += 1
        if seen < n:
            continue
        if seen == n:
            prev = sum(x for x in vals[: i + 1] if x is not None) / n
        else:
            prev = v * k + prev * (1 - k)
        out[i] = prev
    return out


def rma(vals, n):
    """Wilder smoothing: seed with the SMA, then alpha = 1/n."""
    out = [None] * len(vals)
    prev = None
    seen = 0
    for i, v in enumerate(vals):
        if v is None:
            continue
        seen += 1
        if seen < n:
            continue
        if seen == n:
            prev = sum(x for x in vals[: i + 1] if x is not None) / n
        else:
            prev = (prev * (n - 1) + v) / n
        out[i] = prev
    return out


def wma(vals, n):
    out = [None] * len(vals)
    weight = n * (n + 1) / 2
    for i in range(n - 1, len(vals)):
        if any(v is None for v in vals[i - n + 1: i + 1]):
            continue
        out[i] = sum(vals[i - n + 1 + j] * (j + 1) for j in range(n)) / weight
    return out


def rsi(vals, n):
    gains = [None] * len(vals)
    losses = [None] * len(vals)
    for i in range(1, len(vals)):
        diff = vals[i] - vals[i - 1]
        gains[i] = diff if diff > 0 else 0.0
        losses[i] = -diff if diff < 0 else 0.0
    up = rma(gains, n)
    down = rma(losses, n)
    out = [None] * len(vals)
    for i in range(len(vals)):
        if up[i] is None or down[i] is None:
            continue
        out[i] = 100.0 if down[i] == 0 else 100.0 - 100.0 / (1.0 + up[i] / down[i])
    return out


def boll(vals, n, mult):
    mid = sma(vals, n)
    upper = [None] * len(vals)
    lower = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        window = vals[i - n + 1: i + 1]
        mean = mid[i]
        sd = (sum((v - mean) ** 2 for v in window) / n) ** 0.5
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd
    return upper, mid, lower


def macd(vals, fast, slow, signal):
    fast_line = ema(vals, fast)
    slow_line = ema(vals, slow)
    dif = [None if fast_line[i] is None or slow_line[i] is None else fast_line[i] - slow_line[i] for i in range(len(vals))]
    dea = ema(dif, signal)
    hist = [None if dif[i] is None or dea[i] is None else dif[i] - dea[i] for i in range(len(vals))]
    return dif, dea, hist


def atr(data, n):
    tr = [None] * len(data)
    for i, d in enumerate(data):
        if i == 0:
            tr[i] = d[2] - d[3]
        else:
            prev_close = data[i - 1][4]
            tr[i] = max(d[2] - d[3], abs(d[2] - prev_close), abs(d[3] - prev_close))
    return rma(tr, n)


def kdj(data, n, k_n, d_n):
    k_line = [None] * len(data)
    d_line = [None] * len(data)
    j_line = [None] * len(data)
    k_prev = 0.0
    d_prev = 0.0
    for i in range(len(data)):
        if i < n - 1:
            continue
        window = data[i - n + 1: i + 1]
        hh = max(w[2] for w in window)
        ll = min(w[3] for w in window)
        rsv = 50.0 if hh == ll else (data[i][4] - ll) / (hh - ll) * 100.0
        k_prev = (k_prev * (k_n - 1) + rsv) / k_n
        d_prev = (d_prev * (d_n - 1) + k_prev) / d_n
        k_line[i] = k_prev
        d_line[i] = d_prev
        j_line[i] = 3 * k_prev - 2 * d_prev
    return k_line, d_line, j_line


def obv(data):
    out = [0.0] * len(data)
    for i in range(1, len(data)):
        prev_close, close, volume = data[i - 1][4], data[i][4], data[i][5]
        step = volume if close > prev_close else (-volume if close < prev_close else 0.0)
        out[i] = out[i - 1] + step
    return out


def vwap_daily(data):
    out = [None] * len(data)
    day = None
    pv = 0.0
    vol = 0.0
    for i, d in enumerate(data):
        stamp = datetime.datetime.utcfromtimestamp(d[0] / 1000.0).date()
        if stamp != day:
            day, pv, vol = stamp, 0.0, 0.0
        typical = (d[2] + d[3] + d[4]) / 3.0
        pv += typical * d[5]
        vol += d[5]
        out[i] = pv / vol if vol else None
    return out


def main():
    a = args()
    symbol, market = resolve(a.get("symbol"), a.get("market"))
    interval = interval_of(a.get("interval"))
    name = (a.get("indicator") or "").strip().lower()
    if name not in ("ma", "ema", "wma", "rsi", "macd", "boll", "atr", "kdj", "obv", "vwap"):
        raise Fail("indicator must be one of ma, ema, wma, rsi, macd, boll, atr, kdj, obv, vwap")
    if market not in ("spot", "perp"):
        raise Fail("market must be spot or perp")
    source = (a.get("source") or "close").strip().lower()

    length = int(a.get("length") or {"ma": 20, "ema": 20, "wma": 20, "rsi": 14, "atr": 14, "boll": 20, "kdj": 9}.get(name, 14))
    fast = int(a.get("fast") or 12)
    slow = int(a.get("slow") or 26)
    signal = int(a.get("signal") or 9)
    mult = float(a.get("mult") or 2.0)
    limit = max(50, min(1000, int(a.get("limit") or 300)))

    data = candles(symbol, interval, limit, market)
    need = max(length, slow if name == "macd" else 1) + signal + 5
    if len(data) < need:
        raise Fail("only %d candles back; %s needs about %d" % (len(data), name, need))

    params = {}
    if name in ("ma", "ema", "wma"):
        vals = pick(data, source)
        series = {"ma": sma, "ema": ema, "wma": wma}[name](vals, length)
        parts = [("value", series)]
        params = {"length": length, "source": source}
    elif name == "rsi":
        parts = [("value", rsi(pick(data, source), length))]
        params = {"length": length, "source": source}
    elif name == "boll":
        upper, mid, lower = boll(pick(data, source), length, mult)
        parts = [("upper", upper), ("mid", mid), ("lower", lower)]
        params = {"length": length, "mult": mult, "source": source}
    elif name == "macd":
        dif, dea, hist = macd(pick(data, source), fast, slow, signal)
        parts = [("dif", dif), ("dea", dea), ("hist", hist)]
        params = {"fast": fast, "slow": slow, "signal": signal, "source": source}
    elif name == "atr":
        parts = [("value", atr(data, length))]
        params = {"length": length}
    elif name == "kdj":
        k_line, d_line, j_line = kdj(data, length, 3, 3)
        parts = [("k", k_line), ("d", d_line), ("j", j_line)]
        params = {"length": length, "k_smooth": 3, "d_smooth": 3}
    elif name == "obv":
        parts = [("value", obv(data))]
        params = {}
    else:
        parts = [("value", vwap_daily(data))]
        params = {"session": "UTC day"}

    last = None
    for i in range(len(data) - 1, -1, -1):
        if all(series[i] is not None for _, series in parts):
            last = i
            break
    if last is None:
        raise Fail("%s has no defined value in these %d candles; try a longer limit" % (name, len(data)))

    stamp = lambda ms: datetime.datetime.fromtimestamp(ms / 1000.0).astimezone().isoformat(timespec="seconds")
    tail = []
    for i in range(max(0, last - 19), last + 1):
        row = {"t": data[i][0], "time": stamp(data[i][0])}
        for key, series in parts:
            row[key] = round(series[i], 6)
        tail.append(row)

    latest = dict(tail[-1])
    latest["close"] = round(data[last][4], 8)
    out = {
        "symbol": symbol,
        "market": market,
        "interval": interval,
        "indicator": name,
        "params": params,
        "price": round(data[-1][4], 8),
        "latest": latest,
        "tail": tail,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Fail as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
