# miyu-candle

给 [Miyu](https://github.com/miyu-agent/miyu) 的行情包：Binance 的币和 U 本位永续，加上东方财富的沪深 A 股、指数、港股。取 K 线、按 TradingView 的口径算技术指标、把图存成 PNG。写法和口径是照着 [Candle](https://github.com/margbug01/Candle) 来的，但**不需要装 Candle**，只用 python3。

Candles, indicators and chart images for Miyu: Binance spot and USDT-M perpetual, plus A-shares, indices and HK stocks through Eastmoney. TradingView-compatible math, Candle-style charts. No account, no API key, no Candle app.

## 装

```sh
git clone https://github.com/yxxbc/miyu-candle
miyu pkg install ./miyu-candle
```

要 python3；出图另要 matplotlib（macOS 装了命令行工具就自带）。装完下一回合多出四个工具和一份「看行情画图」的技能。

## 工具

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `candle_quote` | `symbols`（逗号分隔）、`market` | 最新价、涨跌幅、高、低、成交量 |
| `candle_klines` | `symbol`、`interval`、`limit`、`market` | 每根的开高低收量，加区间概况 |
| `candle_indicator` | `symbol`、`indicator`、`interval`、`length`、`limit`、`market` | 最新值、参数、最近 20 根的序列 |
| `candle_chart` | `symbol`、`interval`、`limit`、`studies`、`theme`、`market`、`path` | PNG 的路径 |

一份列表里可以币和股票混着问。

## 写什么符号

| 要查 | 写法 |
| --- | --- |
| 币 | `BTCUSDT`、`btc`（会补成 BTCUSDT）、`ETHUSDT.P` 或 `market=perp`（U 本位永续） |
| A 股 | `600519`、`茅台`、`gzmt`（拼音首字母）、`300750`、`宁德时代` |
| 指数 | `上证指数`、`深证成指`、`创业板指`、`沪深300`、`中证500`、`科创50`、`恒生指数`、`恒生科技`、`国企指数` |
| 港股 | `00700`、`700`、`腾讯`、`HKEX:00700` |
| 场内 ETF | `512880`、`证券ETF`（场外基金没接） |

- 加交易所前缀也行：`sh600519`、`sz000001`、`hk00700`、`SSE:600795`、`SZSE:000001`、`HKEX:00700`。
- 单独的 `000001` 是**平安银行**（深市）；上证指数要写名字，或者 `sh000001`。
- 6 位数字按首位分市场：6/5/9 开头是沪市，0/3/1/2 开头是深市，4/8 开头是北交所（没接）；3 到 5 位数字当港股。
- 中文名和拼音首字母走东方财富的搜索，找到的第一个股票或指数就用它。

## 周期

- 币：`1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M`。
- 股票：`1m 5m 15m 30m 1h 2h 4h 1d 3d 1w 1M`；`2h`、`4h` 是拿 1 小时线按交易日合并出来的，`3d` 由日线合并。
- 东方财富的分钟线和小时线只往回一个半月左右（1 分钟线只有当天），日线、周线从上市那天起；拿少了会在返回里写 `note`。
- 月线写 `1M`，大写 M；`1m` 是一分钟。

## 指标

`ma ema wma rsi macd boll atr kdj obv vwap`，叠在 K 线上的有 `ma20`、`ema50`、`wma20`、`boll`、`vwap`；单独一栏的有 `vol`、`rsi`、`macd`、`kdj`、`atr`、`obv`（最多 3 栏）。

口径和 TradingView 一致，也和 Candle 一致：

- EMA 首值是前 n 根的 SMA，之后 α = 2/(n+1)；RSI、ATR 用 Wilder 平滑（α = 1/n，首值同样是 SMA）。
- BOLL 用总体标准差；MACD 的柱是 DIF − DEA。
- KDJ 的 K、D 从 0 起算（TradingView 社区脚本的写法），J = 3K − 2D。
- VWAP：币按 UTC 0 点切日（TradingView 默认），股票按交易日。

## 例子

| 你说 | 走哪个工具、传什么 |
| --- | --- |
| 现在 BTC 多少 | `candle_quote` `{"symbols": "btc"}` |
| 茅台和腾讯现在多少 | `candle_quote` `{"symbols": "茅台, 腾讯"}` |
| 贵州茅台日线 RSI | `candle_indicator` `{"symbol": "600519", "indicator": "rsi", "interval": "1d"}` |
| 上证指数最近半年的日线 | `candle_klines` `{"symbol": "上证指数", "interval": "1d", "limit": 120}` |
| 画一张宁德时代日线，带均线、成交量和 MACD | `candle_chart` `{"symbol": "宁德时代", "interval": "1d", "studies": ["ma20", "ma60", "vol", "macd"]}` |
| ETH 4 小时图，带 BOLL 和 RSI | `candle_chart` `{"symbol": "eth", "interval": "4h", "studies": ["ma20", "boll", "vol", "rsi"]}` |

`candle_indicator` 的返回：

```json
{"symbol": "600519", "name": "贵州茅台", "market": "cn", "source": "eastmoney",
 "interval": "1d", "indicator": "rsi", "params": {"length": 14, "source": "close"},
 "price": 1438.92,
 "latest": {"t": 1794240000000, "time": "2026-11-10T00:00:00+08:00", "value": 66.42, "close": 1438.92},
 "tail": [{"t": 1794153600000, "time": "2026-11-09T00:00:00+08:00", "value": 65.87}, ...]}
```

## 数据从哪来

- 币：`data-api.binance.vision`（现货）、`fapi.binance.com`（U 本位永续），公开接口，不要 key。
- 股票：东方财富网页自己用的接口——K 线 `push2his.eastmoney.com`、报价 `push2.eastmoney.com`、搜名字 `searchapi.eastmoney.com`。不是公开 API，可能限流、改字段；A 股价格是前复权的，和国内炒股软件一致；A 股报价晚几秒，港股接近实时。
- 大陆连 Binance 要开代理（走系统代理）；东方财富国内直连。
- 没有账号、没有交易、没有下单接口，只读公开行情。不构成投资建议。

## 对过的数

- 指标对了一份独立实现（Python 的 [ta](https://github.com/bukosabino/ta) 库）：SMA、EMA、RSI、BOLL、MACD 的 DIF/DEA/柱、ATR，在 500 根 BTC 小时线上逐项一致，差在 1e-9 以下。VWAP、KDJ 另有独立重算。
- 股票的 4 小时线（由 1 小时线合并）和日线比：32 个交易日的开高低收全部相同，成交量只差几百手（东财自己的小时合计和日合计就对不上）。
- 报价和日线比：贵州茅台的现价、最高、最低分别等于它当天的收盘、最高、最低。

## English

Four tools for Miyu: `candle_quote`, `candle_klines`, `candle_indicator`, `candle_chart`. Public Binance endpoints for crypto, Eastmoney for 沪深 A-shares, indices and HK stocks (code, Chinese name or pinyin initials). Indicators use TradingView's math (cross-checked against the `ta` library). Charts are PNG files drawn with matplotlib, themed like Candle and labelled in Chinese. Install with `miyu pkg install ./miyu-candle`.

## 许可证

MIT，见 [LICENSE](LICENSE)。
