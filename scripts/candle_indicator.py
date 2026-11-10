#!/usr/bin/env python3
# Description: Compute a technical indicator with TradingView-compatible math (MA, EMA, WMA, RSI, MACD, BOLL, ATR, KDJ, OBV, VWAP) over Binance candles or Eastmoney A-share, index and HK candles, and return the latest value plus a tail of the series.
# Display name: Market indicator
# 显示名称：指标数值
# 描述：按 TradingView 口径算指标（MA、EMA、WMA、RSI、MACD、BOLL、ATR、KDJ、OBV、VWAP），币和 A 股、指数、港股都能算，返回最新值和最近几十根。
# Timeout: 45
# Parameters:
# {"type": "object", "properties": {
#   "symbol": {"type": "string", "description": "BTCUSDT, btc, BTCUSDT.P; or 600519, 茅台, 00700, 上证指数"},
#   "indicator": {"type": "string", "enum": ["ma", "ema", "wma", "rsi", "macd", "boll", "atr", "kdj", "obv", "vwap"], "description": "Which indicator"},
#   "interval": {"type": "string", "enum": ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"], "description": "Default 1d"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Binance only, default spot"},
#   "length": {"type": "integer", "description": "Main period, default 20 for ma/ema/wma, 14 for rsi/atr, 20 for boll, 9 for kdj"},
#   "fast": {"type": "integer", "description": "macd fast EMA, default 12"},
#   "slow": {"type": "integer", "description": "macd slow EMA, default 26"},
#   "signal": {"type": "integer", "description": "macd signal EMA, default 9"},
#   "mult": {"type": "number", "description": "boll band width in standard deviations, default 2"},
#   "source": {"type": "string", "enum": ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"], "description": "Price source for ma/ema/wma/rsi, default close"},
#   "limit": {"type": "integer", "description": "Candles to load, 50-1000, default 300"}
# }, "required": ["symbol", "indicator"]}
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from marketdata import (Fail, args, atr, boll, ema, fetch, interval_of, kdj, macd,  # noqa: E402
                        obv, pick, resolve, rma, rsi, sma, wma, vwap_daily)

INDICATORS = ("ma", "ema", "wma", "rsi", "macd", "boll", "atr", "kdj", "obv", "vwap")


def main():
    a = args()
    res = resolve(a.get("symbol"), a.get("market"))
    name = (a.get("indicator") or "").strip().lower()
    if name not in INDICATORS:
        raise Fail("indicator must be one of %s" % ", ".join(INDICATORS))
    interval = interval_of(a.get("interval"), res["source"])
    source = (a.get("source") or "close").strip().lower()

    length = int(a.get("length") or {"ma": 20, "ema": 20, "wma": 20, "rsi": 14, "atr": 14, "boll": 20, "kdj": 9}.get(name, 14))
    fast = int(a.get("fast") or 12)
    slow = int(a.get("slow") or 26)
    signal = int(a.get("signal") or 9)
    mult = float(a.get("mult") or 2.0)
    limit = max(50, min(1000, int(a.get("limit") or 300)))

    data = fetch(res, interval, limit)
    need = max(length, slow if name == "macd" else 1) + signal + 5
    if len(data) < need:
        raise Fail("only %d candles back; %s needs about %d" % (len(data), name, need))

    params = {}
    if name in ("ma", "ema", "wma"):
        series = {"ma": sma, "ema": ema, "wma": wma}[name](pick(data, source), length)
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
    else:
        session = datetime.timezone.utc if res["source"] == "binance" else None
        parts = [("value", vwap_daily(data, session))]
        params = {"session": "UTC day" if res["source"] == "binance" else "exchange day"}

    last = None
    for i in range(len(data) - 1, -1, -1):
        if all(series[i] is not None for _, series in parts):
            last = i
            break
    if last is None:
        raise Fail("%s has no defined value in these %d candles; try a longer limit" % (name, len(data)))

    def stamp(ms):
        return datetime.datetime.fromtimestamp(ms / 1000.0).astimezone().isoformat(timespec="seconds")

    tail = []
    for i in range(max(0, last - 19), last + 1):
        row = {"t": data[i][0], "time": stamp(data[i][0])}
        for key, series in parts:
            row[key] = round(series[i], 6)
        tail.append(row)

    latest = dict(tail[-1])
    latest["close"] = round(data[last][4], 8)
    out = {
        "symbol": res["symbol"],
        "market": res["market"],
        "source": res["source"],
        "interval": interval,
        "indicator": name,
        "params": params,
        "price": round(data[-1][4], 8),
        "latest": latest,
        "tail": tail,
    }
    if res.get("name"):
        out["name"] = res["name"]
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Fail as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
