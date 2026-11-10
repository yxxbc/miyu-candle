#!/usr/bin/env python3
# Description: Read latest quotes from public endpoints: Binance spot or USDT-M perpetual (24h ticker) and Eastmoney for 沪深 A 股, indices and HK stocks (today's price, change, high, low, volume).
# Display name: Market quote
# 显示名称：行情报价
# 描述：读最新报价：Binance 现货/永续的 24 小时报价，或东方财富的 A 股、指数、港股当日报价。
# Timeout: 40
# Parameters:
# {"type": "object", "properties": {
#   "symbols": {"type": "string", "description": "One or several separated by commas: BTCUSDT, eth, sol; or 600519, 茅台, 00700, 上证指数"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Binance only, default spot"}
# }, "required": ["symbols"]}
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from marketdata import (BINANCE_FAPI, BINANCE_SPOT, Fail, args, http_json,  # noqa: E402
                        quote_eastmoney, resolve)


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def binance_quote(res):
    if res["market"] == "perp":
        ticker = http_json(BINANCE_FAPI + "/fapi/v1/ticker/24hr", {"symbol": res["symbol"]})
    else:
        ticker = http_json(BINANCE_SPOT + "/api/v3/ticker/24hr", {"symbol": res["symbol"]})
    return {
        "symbol": res["symbol"],
        "market": res["market"],
        "source": "binance",
        "window": "24h",
        "price": number(ticker.get("lastPrice")),
        "change_pct": number(ticker.get("priceChangePercent")),
        "high": number(ticker.get("highPrice")),
        "low": number(ticker.get("lowPrice")),
        "volume": number(ticker.get("volume")),
        "quote_volume": number(ticker.get("quoteVolume")),
    }


def main():
    a = args()
    market = (a.get("market") or "spot").strip().lower()
    if market not in ("spot", "perp"):
        raise Fail("market must be spot or perp")
    wanted = [s for s in (a.get("symbols") or "").replace("；", ",").replace("，", ",").split(",") if s.strip()]
    if not wanted:
        raise Fail("symbols is empty")

    quotes, problems = [], []
    for raw in wanted[:20]:
        try:
            res = resolve(raw, market)
            if res["source"] == "eastmoney":
                row = quote_eastmoney(res)
                row["source"] = "eastmoney"
                row["volume_unit"] = {"lot": "lot (100 shares)", "share": "share"}[res["volume_unit"]]
            else:
                row = binance_quote(res)
        except Fail as e:
            problems.append("%s: %s" % (raw.strip(), e))
            continue
        quotes.append(row)

    if not quotes:
        raise Fail("; ".join(problems) or "no quotes")
    out = {"quotes": quotes}
    if problems:
        out["problems"] = problems
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Fail as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
