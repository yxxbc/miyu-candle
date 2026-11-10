---
name: market-charts
description: "Read candles and quotes, compute technical indicators and draw chart images for crypto, A-shares, Chinese indices and HK stocks. Use when asked about a price, a chart, an indicator or a 行情 (看下行情、K 线图、RSI、MACD、涨了多少、A 股、恒生、茅台、支撑位)."
metadata:
  display_name: Read markets
  display_name_zh: 看行情画图
  summary: Quotes, candles, indicators and chart images
  summary_zh: 币、A 股、指数的报价、K 线、指标、出图
---

# 看行情画图

四个工具，公开接口，不用账号、不用 key：

| 工具 | 做什么 | 覆盖 |
| --- | --- | --- |
| `candle_quote` | 最新价、涨跌幅、高低、成交量，一次可问几个 | 币、A 股、指数、港股 |
| `candle_klines` | K 线，带区间概况 | 同上 |
| `candle_indicator` | ma ema wma rsi macd boll atr kdj obv vwap | 同上 |
| `candle_chart` | 出图：K 线加均线、副图，存成 PNG | 同上 |

## 怎么选

1. 问价、涨了多少 → `candle_quote`，多个用逗号一次问完。
2. 问走势、区间、最近几根 → `candle_klines`，`limit` 30 到 200 就够读。
3. 问指标数值（RSI 多少、MACD 金叉没有）→ `candle_indicator`；金叉死叉看返回的 `tail` 里 dif 和 dea 前后两根谁在上。
4. 要看图 → `candle_chart`，拿到返回的 `path` 之后用 `show` 打开，不然对方看不到。只在对方要图、或者一张图比一屏数字更省事的时候画。

## 符号

- 币写 `btc`、`eth`（会补 USDT），永续写 `BTCUSDT.P` 或 `market=perp`。
- A 股写代码 `600519`、`300750`，或者名字 `茅台`、`宁德时代`，或者拼音首字母 `gzmt`。
- 指数写名字：`上证指数`、`深证成指`、`创业板指`、`沪深300`、`科创50`、`恒生指数`、`恒生科技`、`国企指数`。
- 港股写 `00700`、`700`、`腾讯`。
- 单独的 `000001` 是平安银行，上证指数要写名字或 `sh000001`。

## 约定

- 默认周期：K 线 `1h`，指标 `1d`（看指标一般看日线），图 `1h`。
- 股票没有 3m、6h、8h、12h；`2h`、`4h`、`3d` 是合并出来的。分钟线和小时线只往回一个半月，返回里的 `note` 会说明拿少了。
- 图默认 `studies` 是 `ma20`、`ma60`、`vol`、`macd`；看趋势加 `boll` 或 `vwap`，看强弱把 `vol` 换成 `rsi`，超买超卖换 `kdj`；副图最多 3 个。
- 数字照工具原样说，不要自己再估一遍；指标是按 TradingView 口径算的。
- 工具出错时退出码是 1，原因在 stderr：`Invalid symbol` 是交易对不存在，`找不到叫…的股票` 是名字没搜到，`network` 是要开代理（大陆连 Binance 需要）。
- 只读公开行情，不碰账户，不是投资建议。
