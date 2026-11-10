#!/usr/bin/env python3
# Description: Read 24 hour tickers (last price, change, high, low, volume) from Binance's public endpoints for one or more symbols, spot or USDT-M perpetual.
# Display name: Market quote
# 显示名称：行情报价
# 描述：从 Binance 公开接口读一个或多个交易对的 24 小时报价（最新价、涨跌幅、高低、成交量）。
# Timeout: 30
# Parameters:
# {"type": "object", "properties": {
#   "symbols": {"type": "string", "description": "One ticker or several separated by commas, e.g. BTCUSDT,eth,sol"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Default spot"}
# }, "required": ["symbols"]}
import json, os, sys, urllib.error, urllib.parse, urllib.request

SPOT = "https://data-api.binance.vision"
FAPI = "https://fapi.binance.com"
QUOTES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "BTC", "ETH", "BNB", "EUR", "USD", "TRY", "BRL", "JPY")


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
        raise Fail("%s (HTTP %d)" % (msg, e.code))
    except urllib.error.URLError as e:
        raise Fail("network: %s (Binance needs the system proxy in mainland China)" % (e.reason,))


def resolve(symbol, market):
    s = "".join((symbol or "").split()).upper().replace("/", "").replace("-", "").replace("_", "")
    if s.endswith(".P"):
        s, market = s[:-2], "perp"
    if not any(s.endswith(q) and len(s) > len(q) for q in QUOTES):
        s += "USDT"
    return s, (market or "spot")


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    a = args()
    market = (a.get("market") or "spot").strip().lower()
    if market not in ("spot", "perp"):
        raise Fail("market must be spot or perp")
    wanted = [s for s in (a.get("symbols") or "").replace("；", ",").split(",") if s.strip()]
    if not wanted:
        raise Fail("symbols is empty")

    base, path = (FAPI, "/fapi/v1/ticker/24hr") if market == "perp" else (SPOT, "/api/v3/ticker/24hr")
    rows, problems = [], []
    for raw in wanted[:20]:
        symbol, mkt = resolve(raw, market)
        if mkt != market:
            problems.append("%s: skipped, .P means perpetual but market is %s" % (symbol, market))
            continue
        try:
            t = http(base + path, {"symbol": symbol})
        except Fail as e:
            problems.append("%s: %s" % (symbol, e))
            continue
        rows.append({
            "symbol": symbol,
            "price": num(t.get("lastPrice")),
            "change_24h_pct": num(t.get("priceChangePercent")),
            "high_24h": num(t.get("highPrice")),
            "low_24h": num(t.get("lowPrice")),
            "volume_24h": num(t.get("volume")),
            "quote_volume_24h": num(t.get("quoteVolume")),
        })

    if not rows:
        raise Fail("; ".join(problems) or "no quotes")
    out = {"market": market, "quotes": rows}
    if problems:
        out["problems"] = problems
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Fail as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
