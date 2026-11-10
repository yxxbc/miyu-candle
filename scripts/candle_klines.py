#!/usr/bin/env python3
# Description: Fetch OHLCV candles from Binance's public endpoints (spot or USDT-M perpetual, no key, no login) and return them with a window summary.
# Display name: Market candles
# 显示名称：K 线
# 描述：从 Binance 公开接口取 K 线（现货或 U 本位永续，不用 key），带区间概况。
# Timeout: 30
# Parameters:
# {"type": "object", "properties": {
#   "symbol": {"type": "string", "description": "Ticker such as BTCUSDT; a bare base like btc becomes BTCUSDT; BTCUSDT.P means USDT-M perpetual"},
#   "interval": {"type": "string", "enum": ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"], "description": "Candle width, default 1h"},
#   "limit": {"type": "integer", "description": "How many candles, 1-1000, default 200"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Default spot"}
# }, "required": ["symbol"]}
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

SPOT = "https://data-api.binance.vision"
FAPI = "https://fapi.binance.com"
QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "BTC", "ETH", "BNB", "EUR", "USD", "TRY", "BRL", "JPY")
INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M")


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
        with urllib.request.urlopen(req, timeout=15) as r:
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
    v = (value or "1h").strip()
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
    return [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), float(r[7])] for r in rows]


def main():
    a = args()
    symbol, market = resolve(a.get("symbol"), a.get("market"))
    interval = interval_of(a.get("interval"))
    try:
        limit = int(a.get("limit") or 200)
    except (TypeError, ValueError):
        raise Fail("limit must be an integer")
    limit = max(1, min(1000, limit))
    if market not in ("spot", "perp"):
        raise Fail("market must be spot or perp")

    rows = candles(symbol, interval, limit, market)
    if not rows:
        raise Fail("Binance returned no candles for %s %s" % (symbol, interval))

    o = rows[0][1]
    c = rows[-1][4]
    stamp = lambda ms: datetime.datetime.fromtimestamp(ms / 1000.0).astimezone().isoformat(timespec="seconds")
    out = {
        "symbol": symbol,
        "market": market,
        "interval": interval,
        "count": len(rows),
        "candles": [[r[0], round(r[1], 8), round(r[2], 8), round(r[3], 8), round(r[4], 8), round(r[5], 4)] for r in rows],
        "summary": {
            "from": stamp(rows[0][0]),
            "to": stamp(rows[-1][0]),
            "open": round(o, 8),
            "close": round(c, 8),
            "change_pct": round((c - o) / o * 100, 3) if o else None,
            "high": round(max(r[2] for r in rows), 8),
            "low": round(min(r[3] for r in rows), 8),
            "volume": round(sum(r[5] for r in rows), 4),
            "quote_volume": round(sum(r[6] for r in rows), 2),
        },
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Fail as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
