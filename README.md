# miyu-candle

给 [Miyu](https://github.com/miyu-agent/miyu) 的行情包：从 Binance 的公开接口取 K 线，按 TradingView 的口径算技术指标，再把图存成 PNG。写法和口径是照着 [Candle](https://github.com/margbug01/Candle) 来的，但**不需要装 Candle**，只用 python3。

Candles, indicators and chart images for Miyu, from Binance's public endpoints. The indicator math follows TradingView (and Candle), the charts follow its dark theme. No account, no API key, no Candle app.

## 装

```sh
git clone https://github.com/yxxbc/miyu-candle
miyu pkg install ./miyu-candle
```

要 python3；出图另要 matplotlib（macOS 装了命令行工具就自带）。装完下一回合多出四个工具和一份「看行情画图」的技能。

## 工具

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `candle_quote` | `symbols`（逗号分隔）、`market` | 最新价、24 小时涨跌幅、高、低、成交量 |
| `candle_klines` | `symbol`、`interval`、`limit`、`market` | 每根的开高低收量，加区间概况 |
| `candle_indicator` | `symbol`、`indicator`、`interval`、`length`、`limit`、`market` | 最新值、参数、最近 20 根的序列 |
| `candle_chart` | `symbol`、`interval`、`limit`、`studies`、`theme`、`market`、`path` | PNG 的路径 |

- 符号：`BTCUSDT`、`btc`（会补成 BTCUSDT）、`BTCUSDT.P`（U 本位永续）都行。
- 周期：`1m 5m 15m 30m 1h 2h 4h 6h 12h 1d 3d 1w 1M`。
- 指标：`ma ema wma rsi macd boll atr kdj obv vwap`，口径见下。
- 图的 `studies` 混着写叠在 K 线上的和单独一栏的：`ma20`、`ema50`、`wma20`、`boll`、`vwap` 画在 K 线上，`vol`、`rsi`、`macd`、`kdj`、`atr`、`obv` 各占一栏（最多 3 栏）。

## 指标口径

和 TradingView 一致，也和 Candle 一致：

- EMA 首值是前 n 根的 SMA，之后 α = 2/(n+1)；RSI、ATR 用 Wilder 平滑（α = 1/n，首值同样是 SMA）。
- BOLL 用总体标准差；MACD 的柱是 DIF − DEA。
- KDJ 的 K、D 从 0 起算（TradingView 社区脚本的写法），J = 3K − 2D。
- VWAP 按 UTC 0 点切日，和 TradingView 的默认一致。

数值对过一次独立的实现（Python 的 [ta](https://github.com/bukosabino/ta) 库）：SMA、EMA、RSI、BOLL、MACD 的 DIF/DEA/柱、ATR 在 500 根 BTC 小时线上逐项一致，差在 1e-9 以下。

## 例子

| 你说 | 走哪个工具、传什么 |
| --- | --- |
| 现在 BTC 多少 | `candle_quote` `{"symbols": "btc"}` |
| ETH 日线 RSI 多少 | `candle_indicator` `{"symbol": "eth", "indicator": "rsi", "interval": "1d"}` |
| 画一张 ETH 4 小时图，带 BOLL 和 RSI | `candle_chart` `{"symbol": "eth", "interval": "4h", "studies": ["ma20", "boll", "vol", "rsi"]}` |
| 永续最近一天的 K 线 | `candle_klines` `{"symbol": "BTCUSDT.P", "interval": "1h", "limit": 24}` |

`candle_indicator` 的返回：

```json
{"symbol": "BTCUSDT", "interval": "1d", "indicator": "rsi",
 "params": {"length": 14, "source": "close"},
 "latest": {"t": 1794268800000, "time": "2026-11-10T08:00:00+08:00", "value": 36.31, "close": 74800.01},
 "tail": [{"t": 1794265200000, "time": "2026-11-10T07:00:00+08:00", "value": 35.82}, ...]}
```

## 说明

- 行情来自 `data-api.binance.vision`（现货）和 `fapi.binance.com`（U 本位永续），都是公开接口。中国大陆连不上时开系统代理。
- 没有账号、没有交易、没有下单接口，只读公开行情。不构成投资建议。
- 只接了 Binance 的币和永续；美股、期货、A 股、港股没接。

## English

Four tools for Miyu: `candle_quote`, `candle_klines`, `candle_indicator`, `candle_chart`. Public Binance endpoints only, no key, no login. Indicators use TradingView's math (cross-checked against the `ta` library). Charts are PNG files drawn with matplotlib, themed like Candle. Install with `miyu pkg install ./miyu-candle`.

## 许可证

MIT，见 [LICENSE](LICENSE)。
