#!/usr/bin/env python3
# Description: Draw a candlestick chart from Binance candles or Eastmoney A-share, index and HK candles into a PNG and return its path: price with MA/EMA/BOLL/VWAP overlays, panes for volume, RSI, MACD, KDJ, ATR, OBV. Needs matplotlib (ships with the macOS command line tools).
# Display name: Market chart
# 显示名称：K 线图
# 描述：把 K 线画成 PNG（K 线 + 均线/BOLL/VWAP，副图可放成交量、RSI、MACD、KDJ、ATR、OBV），币和 A 股、指数、港股都能画，返回图片路径。要 matplotlib。
# Timeout: 60
# Parameters:
# {"type": "object", "properties": {
#   "symbol": {"type": "string", "description": "BTCUSDT, btc, BTCUSDT.P; or 600519, 茅台, 00700, 上证指数"},
#   "interval": {"type": "string", "enum": ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1M"], "description": "Default 1h. Stocks support 1m/5m/15m/30m/1h/2h/4h/1d/3d/1w/1M"},
#   "market": {"type": "string", "enum": ["spot", "perp"], "description": "Binance only, default spot"},
#   "limit": {"type": "integer", "description": "Candles to draw, 30-500, default 150"},
#   "studies": {"type": "array", "items": {"type": "string"}, "description": "Mix of overlays (ma20, ema50, wma20, boll, vwap) and panes (vol, rsi, macd, kdj, atr, obv). Default [ma20, ma60, vol, macd]"},
#   "theme": {"type": "string", "enum": ["dark", "light"], "description": "Default dark"},
#   "path": {"type": "string", "description": "Where to save the PNG; default a charts folder inside the Miyu cache"}
# }, "required": ["symbol"]}
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
from marketdata import (Fail, args, atr, boll, ema, fetch, interval_of, kdj, macd,  # noqa: E402
                        obv, resolve, rsi, sma, vwap_daily, wma, work_dir)

OVERLAYS = ("ma", "ema", "wma", "boll", "vwap")
PANES = ("vol", "rsi", "macd", "kdj", "atr", "obv")
THEMES = {
    "dark": {"bg": "#131722", "grid": "#242832", "text": "#d1d4dc", "muted": "#787b86", "up": "#26a69a", "down": "#ef5350",
             "lines": ["#f0b90b", "#2962ff", "#ab47bc", "#ff7043", "#42a5f5"]},
    "light": {"bg": "#ffffff", "grid": "#e8eaed", "text": "#2a2e39", "muted": "#787b86", "up": "#089981", "down": "#f23645",
              "lines": ["#2962ff", "#f0b90b", "#ab47bc", "#ff7043", "#00897b"]},
}


def num(value):
    if value is None:
        return ""
    if abs(value) >= 1000:
        return "{:,.0f}".format(value)
    if abs(value) >= 10:
        return "{:,.2f}".format(value)
    if abs(value) >= 1:
        return "{:,.3f}".format(value)
    return "{:,.5f}".format(value)


def compact(value):
    if value is None:
        return ""
    if abs(value) < 1:
        return "0"
    for scale, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= scale:
            text = "%.2f" % (value / scale)
            return text.rstrip("0").rstrip(".") + suffix
    return "%.2f" % value


def parse_studies(raw):
    if isinstance(raw, str):
        raw = [part for part in raw.split(",") if part.strip()]
    studies = raw if isinstance(raw, list) and raw else ["ma20", "ma60", "vol", "macd"]
    overlays, panes = [], []
    for item in studies:
        text = str(item).strip().lower().replace(" ", "")
        match = re.match(r"^([a-z]+)(\d*)$", text)
        if not match:
            raise Fail("study %r is not like ma20, ema50, boll, vwap, vol, rsi, macd, kdj, atr, obv" % (item,))
        name, digits = match.group(1), match.group(2)
        period = int(digits) if digits else None
        if name in OVERLAYS:
            overlays.append((name, period))
        elif name in PANES:
            panes.append((name, period))
        else:
            raise Fail("study %r is not one of %s" % (item, ", ".join(OVERLAYS + PANES)))
    if len(panes) > 3:
        raise Fail("at most 3 panes at a time, got %d" % len(panes))
    return overlays, panes


def draw(data, res, interval, overlays, panes, theme_name, out_path):
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(work_dir(), "mpl"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    import numpy as np

    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Heiti SC", "DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False

    theme = THEMES[theme_name]
    bg, grid, text, muted = theme["bg"], theme["grid"], theme["text"], theme["muted"]
    session_tz = datetime.timezone.utc if res["source"] == "binance" else None

    n = len(data)
    x = np.arange(n)
    opens = np.array([d[1] for d in data])
    highs = np.array([d[2] for d in data])
    lows = np.array([d[3] for d in data])
    closes = np.array([d[4] for d in data])
    vols = np.array([d[5] for d in data])
    rising = closes >= opens
    candle_colors = np.where(rising, theme["up"], theme["down"])

    rows = 1 + len(panes)
    heights = [3.6] + [1.0 if p[0] == "vol" else 1.4 for p in panes]
    fig = plt.figure(figsize=(12.6, 7.4), dpi=130, facecolor=bg)
    gs = fig.add_gridspec(rows, 1, height_ratios=heights, hspace=0.06,
                          left=0.05, right=0.925, top=0.885, bottom=0.085)
    ax = fig.add_subplot(gs[0])
    axes = [ax] + [fig.add_subplot(gs[i + 1], sharex=ax) for i in range(len(panes))]

    body_width = 0.62
    min_body = (highs.max() - lows.min()) * 0.0006
    for i in range(n):
        bottom = min(opens[i], closes[i])
        height = max(abs(closes[i] - opens[i]), min_body)
        ax.add_patch(Rectangle((i - body_width / 2, bottom), body_width, height,
                               facecolor=candle_colors[i], edgecolor=candle_colors[i], linewidth=0.4))
        ax.vlines(i, lows[i], highs[i], color=candle_colors[i], lw=0.9)

    low_limit = float(lows.min())
    high_limit = float(highs.max())
    color_index = 0
    for name, period in overlays:
        color = theme["lines"][color_index % len(theme["lines"])]
        color_index += 1
        if name == "boll":
            upper, mid, lower = boll(closes.tolist(), 20, 2.0)
            ax.plot(x, upper, color=color, lw=0.9, label="BOLL 20,2")
            ax.plot(x, mid, color=color, lw=0.9, ls="--")
            ax.plot(x, lower, color=color, lw=0.9)
            for series in (upper, mid, lower):
                vals = [v for v in series if v is not None]
                if vals:
                    low_limit = min(low_limit, min(vals))
                    high_limit = max(high_limit, max(vals))
            continue
        if name == "vwap":
            series, label = vwap_daily(data, session_tz), "VWAP"
        else:
            length = period or 20
            series = {"ma": sma, "ema": ema, "wma": wma}[name](closes.tolist(), length)
            label = "%s %d" % (name.upper(), length)
        ax.plot(x, series, color=color, lw=1.1, label=label)
        vals = [v for v in series if v is not None]
        if vals:
            low_limit = min(low_limit, min(vals))
            high_limit = max(high_limit, max(vals))

    pad = (high_limit - low_limit) * 0.06 or high_limit * 0.01
    ax.set_ylim(low_limit - pad, high_limit + pad)
    ax.set_xlim(-1, n)
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: num(v)))
    ax.legend(loc="upper left", frameon=False, fontsize=7.5, labelcolor=text, ncols=6,
              handlelength=1.3, columnspacing=1.1, borderpad=0)
    watermark = (res.get("name") or res["symbol"]).replace("USDT", "")
    ax.text(0.5, 0.45, watermark, transform=ax.transAxes, fontsize=56 if not res.get("name") else 44,
            color=text, alpha=0.045, ha="center", va="center")

    for slot, (name, period) in enumerate(panes):
        pane = axes[1 + slot]
        pane.set_xlim(-1, n)
        pane.yaxis.tick_right()
        pane.set_facecolor(bg)
        if name == "vol":
            pane.bar(x, vols, width=0.62, color=candle_colors, alpha=0.55, linewidth=0)
            pane.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: compact(v)))
            title = {"base": "Volume", "lot": "Volume (lots)", "share": "Volume (shares)"}[res["volume_unit"]]
        elif name == "rsi":
            length = period or 14
            pane.plot(x, rsi(closes.tolist(), length), color=theme["lines"][1], lw=1.1)
            pane.axhline(70, color=muted, lw=0.8, ls="--")
            pane.axhline(30, color=muted, lw=0.8, ls="--")
            pane.set_ylim(0, 100)
            pane.set_yticks([30, 50, 70])
            title = "RSI %d" % length
        elif name == "macd":
            dif, dea, hist = macd(closes.tolist(), 12, 26, 9)
            hist_colors = [theme["up"] if (h or 0) >= 0 else theme["down"] for h in hist]
            pane.bar(x, [h or 0 for h in hist], width=0.62, color=hist_colors, alpha=0.75, linewidth=0)
            pane.plot(x, dif, color=theme["lines"][2], lw=1.0)
            pane.plot(x, dea, color=theme["lines"][0], lw=1.0)
            pane.axhline(0, color=muted, lw=0.7)
            title = "MACD 12,26,9"
        elif name == "kdj":
            length = period or 9
            k_line, d_line, j_line = kdj(data, length, 3, 3)
            pane.plot(x, k_line, color=theme["lines"][0], lw=1.0)
            pane.plot(x, d_line, color=theme["lines"][1], lw=1.0)
            pane.plot(x, j_line, color=theme["lines"][2], lw=0.9)
            pane.axhline(80, color=muted, lw=0.7, ls="--")
            pane.axhline(20, color=muted, lw=0.7, ls="--")
            title = "KDJ %d,3,3" % length
        elif name == "atr":
            length = period or 14
            pane.plot(x, atr(data, length), color=theme["lines"][3], lw=1.1)
            pane.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: compact(v)))
            title = "ATR %d" % length
        else:
            pane.plot(x, obv(data), color=theme["lines"][4], lw=1.1)
            pane.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: compact(v)))
            title = "OBV"
        pane.text(0.004, 0.985, title, transform=pane.transAxes, fontsize=7.5, color=muted, va="top",
                  bbox=dict(facecolor=bg, edgecolor="none", pad=1.5, alpha=0.85))

    for pane in axes:
        pane.set_facecolor(bg)
        pane.grid(True, color=grid, lw=0.6, alpha=0.6)
        pane.set_axisbelow(True)
        for side in ("top", "left", "right", "bottom"):
            pane.spines[side].set_visible(False)
        pane.tick_params(colors=muted, labelsize=7.5, length=0)

    for pane in axes[:-1]:
        plt.setp(pane.get_xticklabels(), visible=False)

    daily = interval in ("1d", "3d", "1w", "1M")
    fmt = "%Y-%m-%d" if daily else "%m-%d %H:%M"
    ticks = np.linspace(0, n - 1, min(7, n)).astype(int)
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels([time.strftime(fmt, time.localtime(data[i][0] / 1000)) for i in ticks])

    window_change = (closes[-1] - opens[0]) / opens[0] * 100 if opens[0] else 0.0
    heading = " · ".join(part for part in (res.get("name"), res["symbol"], interval, res["market"]) if part)
    fig.text(0.05, 0.955, heading, fontsize=13.5, color=text, weight="semibold")
    fig.text(0.05, 0.925,
             "close %s   window %+.2f%%   high %s   low %s   %d bars" % (
                 num(closes[-1]), window_change, num(highs.max()), num(lows.min()), n),
             fontsize=8.5, color=muted)
    fig.text(0.925, 0.955, time.strftime("%Y-%m-%d %H:%M"), fontsize=8, color=muted, ha="right")

    directory = os.path.dirname(os.path.abspath(out_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    fig.savefig(out_path, facecolor=bg, dpi=130)
    plt.close(fig)


def main():
    a = args()
    res = resolve(a.get("symbol"), a.get("market"))
    interval = interval_of(a.get("interval"), res["source"])
    limit = max(30, min(500, int(a.get("limit") or 150)))
    theme_name = (a.get("theme") or "dark").strip().lower()
    if theme_name not in THEMES:
        raise Fail("theme must be dark or light")
    overlays, panes = parse_studies(a.get("studies"))

    data = fetch(res, interval, limit)
    if len(data) < 30:
        raise Fail("only %d candles came back, not enough to draw" % len(data))

    out_path = a.get("path")
    if out_path:
        out_path = os.path.expanduser(out_path)
    else:
        out_path = os.path.join(work_dir(), "charts", "%s-%s-%s-%s.png" % (
            res["symbol"], interval, res["market"], time.strftime("%Y%m%d-%H%M%S")))

    draw(data, res, interval, overlays, panes, theme_name, out_path)

    out = {
        "path": os.path.abspath(out_path),
        "symbol": res["symbol"],
        "market": res["market"],
        "source": res["source"],
        "interval": interval,
        "bars": len(data),
        "studies": ["%s%s" % (name, period or "") for name, period in overlays + panes],
        "last_close": data[-1][4],
    }
    if res.get("name"):
        out["name"] = res["name"]
    if len(data) < limit:
        note = "drawn %d of the %d asked" % (len(data), limit)
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
