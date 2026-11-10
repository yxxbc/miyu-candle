"""Shared market data for the candle_* tools.

Two public sources, both without a key:

- Binance: data-api.binance.vision (spot) and fapi.binance.com (USDT-M perpetual).
- Eastmoney: push2his (candles), push2 (quotes), searchapi (names) — 沪深 A 股、指数、港股,
  prices are forward adjusted (前复权) like the usual Chinese charting software.

Everything returns candles as [ts_ms, open, high, low, close, volume, quote_volume].
"""
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

BINANCE_SPOT = "https://data-api.binance.vision"
BINANCE_FAPI = "https://fapi.binance.com"
EM_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EM_QUOTE = "https://push2.eastmoney.com/api/qt/stock/get"
EM_SEARCH = "https://searchapi.eastmoney.com/api/suggest/get"

BINANCE_QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "BTC", "ETH", "BNB", "EUR", "USD", "TRY", "BRL", "JPY")
BINANCE_INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M")
EM_INTERVALS = ("1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w", "1M")
EM_KLTS = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 101, "1w": 102, "1M": 103}
EM_COMPOSED = {"2h": ("1h", 2), "4h": ("1h", 4), "3d": ("1d", 3)}
EM_SEARCH_CLASSES = ("AStock", "Index", "UniversalIndex", "HK")

INDEX_ALIASES = {
    "上证": "1.000001", "上证指数": "1.000001", "上证综指": "1.000001", "沪指": "1.000001",
    "深证": "0.399001", "深证成指": "0.399001", "深成指": "0.399001", "深指": "0.399001",
    "创业板": "0.399006", "创业板指": "0.399006",
    "沪深300": "1.000300", "中证500": "1.000905", "科创50": "1.000688",
    "恒生": "100.HSI", "恒生指数": "100.HSI",
    "恒生科技": "124.HSTECH", "恒生科技指数": "124.HSTECH",
    "国企指数": "100.HSCEI", "恒指": "100.HSI",
}


class Fail(Exception):
    pass


def args():
    raw = os.environ.get("MIYU_ARGS_JSON")
    if raw is None:
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
    return json.loads(raw) if raw and raw.strip() else {}


def work_dir():
    for key in ("MIYU_CACHE_DIR", "MIYU_STATE_DIR", "MIYU_WORKSPACE_DIR"):
        value = os.environ.get(key)
        if value:
            return value
    return os.path.join(tempfile.gettempdir(), "miyu-candle")


def http_json(url, params, headers=None):
    query_url = url + "?" + urllib.parse.urlencode(params)
    request_headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) miyu-candle/1.0",
                       "Referer": "https://quote.eastmoney.com/"}
    request_headers.update(headers or {})
    request = urllib.request.Request(query_url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            message = json.loads(body).get("msg") or body
        except Exception:
            message = body
        raise Fail("%s (HTTP %d)" % (message, e.code))
    except urllib.error.URLError as e:
        raise Fail("network: %s" % (e.reason,))
    except ValueError:
        raise Fail("the endpoint answered something that is not JSON")


def is_cjk(text):
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


# --- symbols ---

def resolve(symbol, market=None):
    """Turn what a person types into a source and its id."""
    raw = (symbol or "").strip()
    if not raw:
        raise Fail("symbol is empty")
    result = _resolve_eastmoney(raw) or _resolve_binance(raw, market)
    return result


def _em(secid, code, market, name=None, volume_unit="lot"):
    return {"source": "eastmoney", "secid": secid, "symbol": code, "market": market,
            "name": name, "volume_unit": volume_unit}


def _resolve_eastmoney(raw):
    low = raw.lower()
    if raw in INDEX_ALIASES:
        secid = INDEX_ALIASES[raw]
        return _em(secid, secid.split(".")[1], "hk" if secid.startswith("100.") or secid.startswith("124.") else "cn", raw)
    match = re.match(r"^(sh|sse|sz|szse|bj|hk|hkex)[:.]?(\d{4,6})$", low)
    if match:
        prefix, code = match.group(1), match.group(2)
        if prefix == "bj":
            raise Fail("北交所还没接（京市代码 %s）" % code)
        if prefix in ("hk", "hkex"):
            return _em("116." + code.zfill(5), code.zfill(5), "hk", None, "share")
        if prefix in ("sh", "sse"):
            return _em("1." + code.zfill(6), code.zfill(6), "cn")
        return _em("0." + code.zfill(6), code.zfill(6), "cn")
    if raw.isdigit():
        if len(raw) == 6:
            head = raw[0]
            if head in ("6", "5", "9"):
                return _em("1." + raw, raw, "cn")
            if head in ("0", "3", "1", "2"):
                return _em("0." + raw, raw, "cn")
            raise Fail("%s 看着像北交所的代码，还没接" % raw)
        if len(raw) in (3, 4, 5):
            code = raw.zfill(5)
            return _em("116." + code, code, "hk", None, "share")
        raise Fail("认不出 %s 是哪个市场的代码" % raw)
    if is_cjk(raw):
        return _search(raw)
    return None


def _usable(row):
    category = row.get("Classify")
    if category in EM_SEARCH_CLASSES:
        return True
    # exchange traded funds trade like shares; open-end funds do not
    if category == "Fund":
        return len(row.get("Code") or "") == 6 and str(row.get("MktNum")) in ("0", "1")
    return False


def _search(name):
    payload = http_json(EM_SEARCH, {"input": name, "type": 14})
    table = (payload.get("QuotationCodeTable") or {}).get("Data") or []
    hits = [row for row in table if _usable(row) and row.get("QuoteID")]
    if not hits:
        raise Fail("东方财富里找不到叫 %r 的股票或指数" % name)
    exact = [row for row in hits if row.get("Name") == name]
    row = (exact or hits)[0]
    secid = row["QuoteID"]
    market = "hk" if row.get("Classify") == "HK" or secid.startswith(("116.", "100.", "124.")) else "cn"
    unit = "share" if market == "hk" else "lot"
    return _em(secid, row.get("Code") or secid.split(".")[1], market, row.get("Name"), unit)


def _resolve_binance(raw, market):
    symbol = "".join(raw.split()).upper().replace("/", "").replace("-", "").replace("_", "")
    if symbol.endswith(".P"):
        symbol, market = symbol[:-2], "perp"
    if not any(symbol.endswith(q) and len(symbol) > len(q) for q in BINANCE_QUOTES):
        symbol += "USDT"
    market = (market or "spot").strip().lower()
    if market not in ("spot", "perp"):
        raise Fail("market must be spot or perp")
    return {"source": "binance", "symbol": symbol, "market": market, "name": None, "volume_unit": "base"}


# --- intervals ---

def interval_of(value, source="binance"):
    text = (value or "").strip()
    if not text:
        text = "1d" if source == "eastmoney" else "1h"
    if text == "1M":
        normalized = text
    else:
        normalized = text.lower()
    allowed = EM_INTERVALS if source == "eastmoney" else BINANCE_INTERVALS
    if normalized not in allowed:
        raise Fail("%s 上没有 %s 这个周期，能用的有 %s" % (
            "东方财富" if source == "eastmoney" else "Binance", text, ", ".join(allowed)))
    return normalized


# --- candles ---

def fetch(res, interval, limit):
    if res["source"] == "eastmoney":
        return _fetch_eastmoney(res, interval, limit)
    return _fetch_binance(res, interval, limit)


def _fetch_binance(res, interval, limit):
    if res["market"] == "perp":
        rows = http_json(BINANCE_FAPI + "/fapi/v1/klines", {"symbol": res["symbol"], "interval": interval, "limit": limit})
    else:
        rows = http_json(BINANCE_SPOT + "/api/v3/klines", {"symbol": res["symbol"], "interval": interval, "limit": limit})
    return [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), float(r[7])] for r in rows]


def _fetch_eastmoney(res, interval, limit):
    if interval in EM_COMPOSED:
        base, factor = EM_COMPOSED[interval]
        rows = _em_klines(res, base, min(10000, limit * factor + factor))
        return _group(rows, factor, intraday=base in ("1m", "5m", "15m", "30m", "1h"))[-limit:]
    return _em_klines(res, interval, limit)[-limit:]


def _em_klines(res, interval, limit):
    payload = http_json(EM_KLINE, {
        "secid": res["secid"],
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": EM_KLTS[interval],
        "fqt": 1,
        "end": "20500101",
        "lmt": limit,
    })
    data = payload.get("data") or {}
    lines = data.get("klines") or []
    if not lines:
        raise Fail("东方财富没有 %s 的 K 线（代码对吗，或者这只停牌了？）" % res["symbol"])
    if data.get("name"):
        res["name"] = data["name"]
    intraday = interval in ("1m", "5m", "15m", "30m", "1h")
    fmt = "%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"
    rows = []
    for line in lines:
        parts = line.split(",")
        if len(parts) < 5:
            continue
        stamp = int(datetime.datetime.strptime(parts[0], fmt).timestamp() * 1000)
        # Eastmoney orders the fields: date, open, close, high, low, volume, amount
        rows.append([stamp, float(parts[1]), float(parts[3]), float(parts[4]), float(parts[2]),
                     float(parts[5]) if len(parts) > 5 else 0.0,
                     float(parts[6]) if len(parts) > 6 else 0.0])
    return rows


def _group(rows, factor, intraday):
    merged = []

    def flush(bucket):
        if not bucket:
            return
        merged.append([bucket[0][0], bucket[0][1], max(r[2] for r in bucket), min(r[3] for r in bucket),
                       bucket[-1][4], sum(r[5] for r in bucket), sum(r[6] for r in bucket)])

    bucket = []
    session = None
    for row in rows:
        if intraday:
            day = datetime.datetime.fromtimestamp(row[0] / 1000.0).date()
            if day != session:
                flush(bucket)
                bucket = []
                session = day
        bucket.append(row)
        if len(bucket) >= factor:
            flush(bucket)
            bucket = []
    flush(bucket)
    return merged


def quote_eastmoney(res):
    payload = http_json(EM_QUOTE, {"secid": res["secid"],
                                  "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f59,f60,f169,f170"})
    data = payload.get("data")
    if not data:
        raise Fail("东方财富没有 %s 的报价" % res["symbol"])

    def scaled(key, scale):
        value = data.get(key)
        if isinstance(value, (int, float)):
            return round(value / scale, 6)
        return None

    scale = 10 ** int(data.get("f59") or 2)
    res["name"] = data.get("f58") or res.get("name")
    return {
        "symbol": res["symbol"],
        "name": res["name"],
        "market": res["market"],
        "window": "today",
        "price": scaled("f43", scale),
        "change_pct": scaled("f170", 100),
        "open": scaled("f46", scale),
        "prev_close": scaled("f60", scale),
        "high": scaled("f44", scale),
        "low": scaled("f45", scale),
        "volume": data.get("f47") if isinstance(data.get("f47"), (int, float)) else None,
        "quote_volume": data.get("f48") if isinstance(data.get("f48"), (int, float)) else None,
    }


# --- formatting ---

def stamp(ms):
    return datetime.datetime.fromtimestamp(ms / 1000.0).astimezone().isoformat(timespec="seconds")


# --- indicator math (TradingView definitions) ---

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


def vwap_daily(data, tz=datetime.timezone.utc):
    """VWAP per session: UTC days for crypto (TradingView's default), exchange days for stocks."""
    out = [None] * len(data)
    day = None
    pv = 0.0
    volume = 0.0
    for i, d in enumerate(data):
        stamp_day = datetime.datetime.fromtimestamp(d[0] / 1000.0, tz).date()
        if stamp_day != day:
            day, pv, volume = stamp_day, 0.0, 0.0
        typical = (d[2] + d[3] + d[4]) / 3.0
        pv += typical * d[5]
        volume += d[5]
        out[i] = pv / volume if volume else None
    return out
