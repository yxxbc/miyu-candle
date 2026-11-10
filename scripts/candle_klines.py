#!/usr/bin/env python3
# Description: Fetch OHLCV candles from public endpoints and return them with a window summary: Binance spot or USDT-M perpetual, or Eastmoney for 沪深 A 股, indices and HK stocks (no key, no login).
# Display name: Market candles
# 显示名称：K 线
# 描述：取 K 线：Binance 现货/永续，或东方财富的沪深 A 股、指数、港股（不用 key），带区间概况。
# Timeout: 40
# Parameters:
# {"type": "object", "properties": {
#   "symbol": {"type": "string", "description": "BTCUSDT, a bare base like btc, BTCUSDT.P for perpetual; or 600519, 茅台, 00700, 上证指数, HKEX:00700, SSE:600795"},
#   "interval": {"type": "string", "enum": ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"], "description": "Candle width, default 1h. Stocks support 1m/5m/15m/30m/1h/2h/4h/1d/3d/1w/1M"},
#   "limit": {"type": "integer", "description": "How many candles, 1-1000, default 200"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Binance only, default spot"}
# }, "required": ["symbol"]}
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from marketdata import Fail, args, fetch, interval_of, resolve, stamp  # noqa: E402


def main():
    a = args()
    res = resolve(a.get("symbol"), a.get("market"))
    interval = interval_of(a.get("interval"), res["source"])
    try:
        limit = int(a.get("limit") or 200)
    except (TypeError, ValueError):
        raise Fail("limit must be an integer")
    limit = max(1, min(1000, limit))

    rows = fetch(res, interval, limit)
    if not rows:
        raise Fail("no candles for %s" % res["symbol"])

    first_open = rows[0][1]
    last_close = rows[-1][4]
    out = {
        "symbol": res["symbol"],
        "market": res["market"],
        "source": res["source"],
        "interval": interval,
        "count": len(rows),
        "volume_unit": {"base": "base asset", "lot": "lot (100 shares)", "share": "share"}[res["volume_unit"]],
        "candles": [[r[0], round(r[1], 8), round(r[2], 8), round(r[3], 8), round(r[4], 8), round(r[5], 4)] for r in rows],
        "summary": {
            "from": stamp(rows[0][0]),
            "to": stamp(rows[-1][0]),
            "open": round(first_open, 8),
            "close": round(last_close, 8),
            "change_pct": round((last_close - first_open) / first_open * 100, 3) if first_open else None,
            "high": round(max(r[2] for r in rows), 8),
            "low": round(min(r[3] for r in rows), 8),
            "volume": round(sum(r[5] for r in rows), 4),
            "quote_volume": round(sum(r[6] for r in rows), 2),
        },
    }
    if res.get("name"):
        out["name"] = res["name"]
    if len(rows) < limit:
        note = "returned %d of the %d asked" % (len(rows), limit)
        if res["source"] == "eastmoney" and interval not in ("1d", "3d", "1w", "1M"):
            note += "; Eastmoney keeps roughly the last six weeks of minute and hour candles"
        out["note"] = note
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Fail as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
