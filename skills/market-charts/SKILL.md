---
name: market-charts
description: "Read Binance candles, compute technical indicators and draw chart images. Use when asked about a coin's price, candles, an indicator or a chart (看下行情、K 线图、RSI、MACD、涨了多少、支撑位)."
metadata:
  display_name: Read markets
  display_name_zh: 看行情画图
  summary: Quotes, candles, indicators and chart images from Binance
  summary_zh: 从 Binance 取报价、K 线，算指标，出图
---

# 看行情画图

四个工具，都走 Binance 的公开接口，不用账号、不用 key。

| 工具 | 做什么 |
| --- | --- |
| `candle_quote` | 24 小时报价：最新价、涨跌幅、高低、成交量，一次可问几个 |
| `candle_klines` | K 线：开高低收量，带区间概况 |
| `candle_indicator` | 指标：ma ema wma rsi macd boll atr kdj obv vwap |
| `candle_chart` | 出图：K 线加均线、副图，存成 PNG |

## 怎么选

1. 问价、涨了多少 → `candle_quote`，多个币用逗号一次问完。
2. 问走势、区间、最近几根 → `candle_klines`，`limit` 30 到 200 就够读。
3. 问指标数值（RSI 多少、MACD 金叉没有）→ `candle_indicator`；金叉死叉看返回的 `tail` 里 dif 和 dea 前后两根谁在上。
4. 要看图 → `candle_chart`，拿到返回的 `path` 之后用 `show` 打开，不然对方看不到。只在对方要图、或者一张图比一屏数字更省事的时候画。

## 约定

- 符号写 `btc`、`eth` 就行，会补上 USDT；永续写 `BTCUSDT.P`，或者 `market` 传 `perp`。
- 默认周期：K 线 `1h`，指标 `1d`（看指标一般看日线），图 `1h`。月线是 `1M`，大写 M。
- 图默认 `studies` 是 `ma20`、`ma60`、`vol`、`macd`；看趋势加 `boll` 或 `vwap`，看强弱把 `vol` 换成 `rsi`，超买超卖换 `kdj`；副图最多 3 个。
- 数字照工具原样说，不要自己再估一遍；指标是按 TradingView 口径算的。
- 工具出错时退出码是 1，原因在 stderr：`Invalid symbol` 是交易对不存在；`network` 是要开代理（中国大陆连 Binance 需要）。
- 只读公开行情，不碰账户，不是投资建议。
