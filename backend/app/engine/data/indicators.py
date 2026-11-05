import pandas as pd
import ta


def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # RSI
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd_obj = ta.trend.MACD(close)
    macd_line = macd_obj.macd()
    macd_signal = macd_obj.macd_signal()
    macd_hist = macd_obj.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_mid = bb.bollinger_mavg()

    # EMA
    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    ema200 = ta.trend.EMAIndicator(close, window=200).ema_indicator()

    # ATR (volatility)
    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    # Volume SMA
    vol_sma20 = volume.rolling(20).mean()

    latest = -1

    price = float(close.iloc[latest])
    rsi_val = float(rsi.iloc[latest])

    # Interpret RSI
    if rsi_val >= 70:
        rsi_signal = "OVERBOUGHT"
    elif rsi_val <= 30:
        rsi_signal = "OVERSOLD"
    else:
        rsi_signal = "NEUTRAL"

    # MACD crossover
    m = float(macd_line.iloc[latest])
    s = float(macd_signal.iloc[latest])
    h = float(macd_hist.iloc[latest])
    prev_h = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else 0

    if h > 0 and prev_h <= 0:
        macd_signal_str = "BULLISH_CROSSOVER"
    elif h < 0 and prev_h >= 0:
        macd_signal_str = "BEARISH_CROSSOVER"
    elif h > 0:
        macd_signal_str = "BULLISH"
    else:
        macd_signal_str = "BEARISH"

    # Bollinger position
    bbu = float(bb_upper.iloc[latest])
    bbl = float(bb_lower.iloc[latest])
    bbm = float(bb_mid.iloc[latest])
    if price >= bbu:
        bb_position = "UPPER_BAND (overbought zone)"
    elif price <= bbl:
        bb_position = "LOWER_BAND (oversold zone)"
    else:
        pct = (price - bbl) / (bbu - bbl) * 100
        bb_position = f"MID ({pct:.0f}% from lower band)"

    # EMA trend
    e20 = float(ema20.iloc[latest])
    e50 = float(ema50.iloc[latest])
    e200 = float(ema200.iloc[latest]) if not pd.isna(ema200.iloc[latest]) else None

    if e200:
        if price > e20 > e50 > e200:
            ema_trend = "STRONG_UPTREND"
        elif price < e20 < e50 < e200:
            ema_trend = "STRONG_DOWNTREND"
        elif price > e200:
            ema_trend = "ABOVE_200EMA (bullish bias)"
        else:
            ema_trend = "BELOW_200EMA (bearish bias)"
    else:
        ema_trend = "UPTREND" if price > e50 else "DOWNTREND"

    # Volume analysis
    vol_now = float(volume.iloc[latest])
    vol_avg = float(vol_sma20.iloc[latest])
    vol_ratio = vol_now / vol_avg if vol_avg > 0 else 1.0
    vol_signal = "HIGH_VOLUME" if vol_ratio > 1.5 else ("LOW_VOLUME" if vol_ratio < 0.7 else "NORMAL_VOLUME")

    # Recent price change
    price_1w = float(close.iloc[-6]) if len(close) >= 6 else price
    price_1m = float(close.iloc[-22]) if len(close) >= 22 else price
    change_1w = (price - price_1w) / price_1w * 100
    change_1m = (price - price_1m) / price_1m * 100

    return {
        "current_price": round(price, 2),
        "rsi": round(rsi_val, 2),
        "rsi_signal": rsi_signal,
        "macd_line": round(m, 4),
        "macd_signal_line": round(s, 4),
        "macd_histogram": round(h, 4),
        "macd_signal": macd_signal_str,
        "bb_upper": round(bbu, 2),
        "bb_lower": round(bbl, 2),
        "bb_mid": round(bbm, 2),
        "bb_position": bb_position,
        "ema20": round(e20, 2),
        "ema50": round(e50, 2),
        "ema200": round(e200, 2) if e200 else None,
        "ema_trend": ema_trend,
        "atr": round(float(atr.iloc[latest]), 2),
        "volume_ratio": round(vol_ratio, 2),
        "volume_signal": vol_signal,
        "change_1w_pct": round(change_1w, 2),
        "change_1m_pct": round(change_1m, 2),
    }
