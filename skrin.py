import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
import io
import base64
import json
import concurrent.futures
import requests
from datetime import datetime, timedelta
from functools import lru_cache

# Chart generation
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

# =============================================================================
# 1. KONFIGURASI HALAMAN & CSS
# =============================================================================
st.set_page_config(
    page_title="Quant Trader - IDX Screener Ultra v4.2",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card {
        background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 1.2rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        transition: transform 0.2s, border-color 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); border-color: #58a6ff; }
    .ticker { font-size: 1.6rem; font-weight: 800; color: #58a6ff; letter-spacing: 0.5px; }
    .score-badge {
        background-color: rgba(56, 139, 253, 0.15); color: #58a6ff; padding: 0.2rem 0.6rem;
        border-radius: 20px; font-size: 0.85rem; font-weight: 700; border: 1px solid rgba(56, 139, 253, 0.3);
    }
    .grade-A  { background: rgba(63,185,80,.15);  color:#3fb950; border:1px solid rgba(63,185,80,.3);  padding:0.15rem 0.5rem; border-radius:12px; font-weight:700; }
    .grade-B  { background: rgba(88,166,255,.15); color:#58a6ff; border:1px solid rgba(88,166,255,.3); padding:0.15rem 0.5rem; border-radius:12px; font-weight:700; }
    .grade-C  { background: rgba(219,109,40,.15); color:#db6d28; border:1px solid rgba(219,109,40,.3); padding:0.15rem 0.5rem; border-radius:12px; font-weight:700; }
    .price-range { font-size: 1.8rem; font-weight: 700; color: #ffffff; margin-top: 0.2rem; }
    .label { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }
    .tp  { font-size: 1.1rem; font-weight: 700; color: #3fb950; }
    .sl  { font-size: 1.1rem; font-weight: 700; color: #f85149; }
    .ts-rule { font-size: 0.85rem; font-weight: 600; color: #db6d28; }
    .ind-pill {
        display:inline-block; font-size:0.7rem; font-weight:600; padding:0.1rem 0.45rem;
        border-radius:10px; margin:0.1rem;
    }
    .ind-bull { background:rgba(63,185,80,.15);  color:#3fb950; border:1px solid rgba(63,185,80,.3); }
    .ind-bear { background:rgba(248,81,73,.15);  color:#f85149; border:1px solid rgba(248,81,73,.3); }
    .ind-neut { background:rgba(139,148,158,.12);color:#8b949e; border:1px solid rgba(139,148,158,.3);}
    .rr-badge  { font-size:0.75rem; font-weight:700; color:#d2a8ff; }
    .audit-box { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:0.8rem; margin-top:0.5rem; font-size:0.75rem; color:#8b949e; }

    /* Volume Context Bar */
    .vol-ctx { background:rgba(255,255,255,0.03); border-radius:6px; padding:0.4rem 0.6rem; margin-bottom:0.5rem; border:1px solid #21262d; }
    .vol-bar-track { background:#21262d; border-radius:4px; height:5px; width:100%; margin-top:0.25rem; }
    .vol-bar-fill  { height:5px; border-radius:4px; transition:width 0.3s; }

    /* Tape Reading & Bandarmology */
    .section-divider { border-top:1px solid #21262d; margin:0.5rem 0 0.4rem; }
    .tape-pill {
        display:inline-block; font-size:0.65rem; font-weight:700; padding:0.12rem 0.4rem;
        border-radius:8px; margin:0.08rem 0.06rem;
    }
    .tape-accum   { background:rgba(63,185,80,.18);  color:#3fb950; border:1px solid rgba(63,185,80,.35); }
    .tape-distrib { background:rgba(248,81,73,.18);  color:#f85149; border:1px solid rgba(248,81,73,.35); }
    .tape-neutral { background:rgba(139,148,158,.12);color:#8b949e; border:1px solid rgba(139,148,158,.3);}
    .tape-warn    { background:rgba(219,109,40,.18); color:#db6d28; border:1px solid rgba(219,109,40,.35);}
    .tape-purple  { background:rgba(188,140,255,.15);color:#bc8cff; border:1px solid rgba(188,140,255,.3);}

    /* Confidence badge */
    .conf-hi  { color:#3fb950; font-weight:800; font-size:0.65rem; }
    .conf-med { color:#e3b341; font-weight:800; font-size:0.65rem; }
    .conf-lo  { color:#8b949e; font-weight:700; font-size:0.65rem; }

    /* Narasi box */
    .narasi-tech  { font-size:0.72rem; color:#c9d1d9; font-style:italic; line-height:1.35; }
    .narasi-plain { font-size:0.7rem;  color:#8b949e; line-height:1.3; margin-top:0.15rem; }
    /* Signal validity states */
    .signal-expired {
        border-color: #f85149 !important;
        background: rgba(248,81,73,0.04) !important;
    }
    .signal-waiting {
        border-color: #e3b341 !important;
        background: rgba(227,179,65,0.04) !important;
    }
    .expired-banner {
        background: rgba(248,81,73,0.12); border:1px solid rgba(248,81,73,0.4);
        border-radius:6px; padding:0.5rem 0.7rem; margin-bottom:0.5rem;
        text-align:center;
    }
    .waiting-banner {
        background: rgba(227,179,65,0.1); border:1px solid rgba(227,179,65,0.35);
        border-radius:6px; padding:0.5rem 0.7rem; margin-bottom:0.5rem;
        text-align:center;
    }
    .dimmed { opacity: 0.35; pointer-events:none; user-select:none; filter:grayscale(60%); }
    /* Best Buy highlight */
    .best-buy-card {
        border-color: #ffd700 !important;
        background: linear-gradient(135deg, rgba(255,215,0,0.06) 0%, #161b22 60%) !important;
        box-shadow: 0 0 0 2px rgba(255,215,0,0.25), 0 6px 20px rgba(255,215,0,0.1) !important;
    }
    .best-buy-crown {
        display:inline-flex; align-items:center; gap:0.3rem;
        background:linear-gradient(90deg,#ffd700,#ffb300);
        color:#0d1117; font-size:0.72rem; font-weight:900;
        padding:0.2rem 0.65rem; border-radius:20px;
        letter-spacing:0.3px; margin-bottom:0.5rem;
    }
    .best-buy-banner {
        background:linear-gradient(135deg,rgba(255,215,0,0.12),rgba(255,179,0,0.06));
        border:1px solid rgba(255,215,0,0.4); border-radius:8px;
        padding:0.8rem 1rem; margin-bottom:1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. SESSION STATE
# =============================================================================
for key, default in [
    ('raw_market_data', {}), ('last_loaded_mode', None), ('scan_meta', {}),
    ('vision_cache', {}),    # cache hasil Vision per ticker per hari
    ('sheets_log', []),      # log sementara sebelum push ke GSheets
]:
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================================
# 3. HELPER & PARSER
# =============================================================================
def fmt_idr(val):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return "Rp 0"
        return f"Rp {int(val):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"

def parse_tickers_from_df(df: pd.DataFrame) -> list:
    ticker_col = None
    for col in df.columns:
        if col.strip().lower() in ("ticker", "kode", "symbol", "emiten", "code"):
            ticker_col = col
            break
    if ticker_col is None:
        ticker_col = df.columns[0]
    tickers = df[ticker_col].dropna().astype(str).str.strip().tolist()
    return [
        t.upper() if t.upper().endswith(".JK") else f"{t.upper()}.JK"
        for t in tickers
        if t.strip() and t.strip().lower() not in ("nan", "none", "")
    ]

@st.cache_data(show_spinner=False)
def load_local_emiten_csv():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = os.getcwd()
    local_csv = os.path.join(base_dir, "emiten.csv")
    if os.path.exists(local_csv):
        try:
            return parse_tickers_from_df(pd.read_csv(local_csv))
        except Exception:
            return []
    return []

def tickers_from_text(text: str) -> list:
    parts = re.split(r"[,\s\n]+", text.strip())
    return [
        t.upper() if t.upper().endswith(".JK") else f"{t.upper()}.JK"
        for t in parts if t.strip()
    ]

# =============================================================================
# 4. INDIKATOR TEKNIKAL
# =============================================================================

def calculate_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Average True Range — mengukur volatilitas aktual per candle."""
    prev_close = df['Close'].shift(1)
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - prev_close).abs(),
        (df['Low']  - prev_close).abs(),
    ], axis=1).max(axis=1)
    # FIX #1: Gunakan Wilder smoothing (RMA) yang benar, bukan EWM
    # EWM span=14 ≠ Wilder alpha=1/14; Wilder menggunakan alpha=1/window
    return tr.ewm(alpha=1/window, adjust=False).mean()

def calculate_cmf(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Chaikin Money Flow — tekanan beli/jual berbasis volume."""
    if len(df) < window:
        return pd.Series(0.0, index=df.index)
    hl_safe = (df['High'] - df['Low']).replace(0, np.nan)
    mfm = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / hl_safe
    mfm = mfm.fillna(0.0)
    mfv = mfm * df['Volume']
    vol_sum = df['Volume'].rolling(window).sum().replace(0, np.nan)
    return (mfv.rolling(window).sum() / vol_sum).fillna(0.0)

def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """RSI klasik Wilder — momentum overbought/oversold."""
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    # FIX #2: RSI Wilder gunakan alpha=1/window, bukan alpha=1/window yang sama
    # dengan EWM span. Keduanya menggunakan ewm(alpha=1/window) — ini BENAR.
    # Namun avg_loss=0 harus menghasilkan RSI=100, bukan NaN → fillna diperbaiki
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    # FIX #3: rs infinite (avg_loss=0) → RSI=100, bukan dibuang sebagai NaN lalu fillna(50)
    rsi = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, 1e-10)))
    return rsi.fillna(50.0)

def calculate_bb_squeeze(df: pd.DataFrame,
                          bb_window: int = 20, bb_std: float = 2.0,
                          kc_mult: float = 1.5, atr_window: int = 14) -> pd.Series:
    """
    Lazybear-style BB Squeeze:
    True  = BB berada DI DALAM Keltner Channel → kompresi (energi menumpuk).
    False = BB sudah keluar KC → squeeze release / breakout sedang terjadi.
    """
    basis   = df['Close'].rolling(bb_window).mean()
    bb_std_ = df['Close'].rolling(bb_window).std(ddof=1)  # FIX #4: explicit ddof=1 (sample std)
    bb_upper = basis + bb_std * bb_std_
    bb_lower = basis - bb_std * bb_std_

    atr = calculate_atr(df, window=atr_window)
    kc_upper = basis + kc_mult * atr
    kc_lower = basis - kc_mult * atr

    return (bb_upper < kc_upper) & (bb_lower > kc_lower)

def calculate_indicators(df: pd.DataFrame) -> dict:
    """
    Hitung semua indikator sekaligus dan kembalikan sebagai dict scalar.
    FIX #5: Semua series dihitung sekali, bukan berulang di setiap fungsi scoring.
    """
    close  = df['Close']
    volume = df['Volume']

    # EMA trend
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema20  = close.ewm(span=20,  adjust=False).mean()
    last_close = float(close.iloc[-1])
    above_ema50 = last_close > float(ema50.iloc[-1])
    above_ema20 = last_close > float(ema20.iloc[-1])

    # ATR
    atr_series  = calculate_atr(df)
    atr_val     = float(atr_series.iloc[-1])
    atr_pct     = atr_val / last_close if last_close > 0 else 0.0

    # CMF
    cmf_series  = calculate_cmf(df)
    cmf_val     = float(cmf_series.iloc[-1])
    cmf_prev    = float(cmf_series.iloc[-2]) if len(cmf_series) > 1 else 0.0
    cmf_rising  = cmf_val > cmf_prev

    # RSI
    rsi_series  = calculate_rsi(df)
    rsi_val     = float(rsi_series.iloc[-1])
    rsi_prev    = float(rsi_series.iloc[-2]) if len(rsi_series) > 1 else 50.0
    rsi_rising  = rsi_val > rsi_prev

    # BB Squeeze
    sq_series   = calculate_bb_squeeze(df)
    in_squeeze  = bool(sq_series.iloc[-1])
    squeeze_release = (not in_squeeze) and bool(sq_series.iloc[-2]) if len(sq_series) > 1 else False

    # Volume spike vs MA-15
    vol_ma15    = float(volume.rolling(15).mean().iloc[-1])
    vol_last    = float(volume.iloc[-1])
    # FIX #6: Gunakan max(vol_ma15, 1) untuk menghindari division by tiny epsilon
    vol_spike   = vol_last / max(vol_ma15, 1.0)

    # ADTV (MA-20 volume × harga)
    vol_ma20    = float(volume.rolling(20).mean().iloc[-1])
    adtv        = vol_ma20 * last_close

    # FIX #7: Tambah guard — atr_val harus positif dan finite
    if not np.isfinite(atr_val) or atr_val <= 0:
        raise ValueError(f"ATR tidak valid: {atr_val}")

    return {
        'last_close':      last_close,
        'above_ema50':     above_ema50,
        'above_ema20':     above_ema20,
        'atr_val':         atr_val,
        'atr_pct':         atr_pct,
        'cmf_val':         cmf_val,
        'cmf_rising':      cmf_rising,
        'rsi_val':         rsi_val,
        'rsi_rising':      rsi_rising,
        'in_squeeze':      in_squeeze,
        'squeeze_release': squeeze_release,
        'vol_spike':       vol_spike,
        'adtv':            adtv,
    }

# =============================================================================
# 4b. VOLUME CONTEXT — analisis candle terakhir
# =============================================================================
def analyse_volume_context(df: pd.DataFrame) -> dict:
    """
    Analisis candle hari ini vs rata-rata:
    - Arah candle (bullish/bearish/doji)
    - Volume spike ratio vs MA-20
    - Body size (%) vs full range
    - Upper/lower shadow dominance
    Adaptif: bekerja sama di 1d (swing) maupun 60m (intraday).
    """
    if len(df) < 5:
        return {'valid': False}

    row   = df.iloc[-1]
    o, h, l, c = float(row['Open']), float(row['High']), float(row['Low']), float(row['Close'])
    vol   = float(row['Volume'])
    rng   = h - l if h > l else 1e-9

    body      = abs(c - o)
    body_pct  = body / rng            # 0–1, besar = candle tegas
    upper_sh  = h - max(c, o)
    lower_sh  = min(c, o) - l
    close_pos = (c - l) / rng        # 0 = tutup di bawah, 1 = tutup di atas

    vol_ma20  = float(df['Volume'].rolling(20).mean().iloc[-1])
    vol_ratio = vol / max(vol_ma20, 1.0)

    if body_pct < 0.15:
        candle_dir = "doji"
    elif c >= o:
        candle_dir = "bullish"
    else:
        candle_dir = "bearish"

    return {
        'valid':       True,
        'candle_dir':  candle_dir,
        'body_pct':    round(body_pct, 3),
        'upper_sh':    round(upper_sh / rng, 3),
        'lower_sh':    round(lower_sh / rng, 3),
        'close_pos':   round(close_pos, 3),
        'vol_ratio':   round(vol_ratio, 2),
        'vol_ma20':    vol_ma20,
    }


# =============================================================================
# 4c. TAPE READING — pola 5 candle terakhir
# =============================================================================
def analyse_tape(df: pd.DataFrame) -> dict:
    """
    Deteksi pola price-volume 5 candle terakhir:
    - Buying/Selling Climax
    - Absorption
    - Exhaustion
    - Accumulation Quiet
    Kembalikan list sinyal aktif + sinyal terkuat.
    """
    if len(df) < 10:
        return {'signals': [], 'dominant': None}

    tail   = df.tail(5).copy()
    vol5   = tail['Volume'].values.astype(float)
    hi5    = tail['High'].values.astype(float)
    lo5    = tail['Low'].values.astype(float)
    op5    = tail['Open'].values.astype(float)
    cl5    = tail['Close'].values.astype(float)

    vol_ma = float(df['Volume'].rolling(20).mean().iloc[-1])
    atr5   = float(calculate_atr(df.tail(20)).iloc[-1])

    ranges5     = hi5 - lo5
    avg_range5  = float(np.mean(ranges5)) if np.mean(ranges5) > 0 else 1e-9
    avg_vol5    = float(np.mean(vol5))
    avg_vol5_s  = max(avg_vol5, 1.0)

    signals = []

    # ── Buying Climax: volume sangat tinggi + candle bullish besar di puncak ──
    last_vol_ratio = vol5[-1] / max(vol_ma, 1.0)
    last_range     = ranges5[-1]
    last_body      = abs(cl5[-1] - op5[-1])
    last_close_pos = (cl5[-1] - lo5[-1]) / max(last_range, 1e-9)

    if (last_vol_ratio > 2.5 and last_body / max(last_range, 1e-9) > 0.6
            and cl5[-1] > op5[-1] and last_close_pos > 0.7):
        signals.append(('buying_climax', 'distrib',
                        'Buying Climax', 'BC',
                        min(int(last_vol_ratio / 3.0 * 100), 90)))

    # ── Selling Climax: volume sangat tinggi + bearish besar ──
    if (last_vol_ratio > 2.5 and last_body / max(last_range, 1e-9) > 0.6
            and cl5[-1] < op5[-1] and last_close_pos < 0.3):
        signals.append(('selling_climax', 'accum',
                        'Selling Climax', 'SC',
                        min(int(last_vol_ratio / 3.0 * 100), 90)))

    # ── Absorption: volume besar tapi harga tidak turun jauh (close_pos tinggi) ──
    if (last_vol_ratio > 1.8 and last_close_pos > 0.55
            and abs(cl5[-1] - cl5[-2]) / max(atr5, 1e-9) < 0.5):
        signals.append(('absorption', 'accum',
                        'Absorption', 'ABS',
                        min(int(last_close_pos * last_vol_ratio / 2.5 * 100), 85)))

    # ── Exhaustion: volume tinggi tapi range candle kecil ──
    if (last_vol_ratio > 1.8 and last_range < avg_range5 * 0.6):
        signals.append(('exhaustion', 'warn',
                        'Exhaustion', 'EXH',
                        min(int((avg_range5 / max(last_range, 1e-9)) * 20), 80)))

    # ── Accumulation Quiet: 5 candle volume rendah konsisten, harga tidak turun ──
    vol_consistent_low = all(v < vol_ma * 0.8 for v in vol5)
    price_stable       = (max(cl5) - min(cl5)) / max(atr5, 1e-9) < 1.5
    if vol_consistent_low and price_stable:
        signals.append(('accum_quiet', 'accum',
                        'Akumulasi Senyap', 'AQ',
                        72))

    dominant = signals[0] if signals else None
    return {'signals': signals, 'dominant': dominant}


# =============================================================================
# 4d. BANDARMOLOGY — deteksi aksi smart money
# =============================================================================
def analyse_bandarmology(df: pd.DataFrame) -> dict:
    """
    Deteksi pola OHLCV khas smart money:
    1. Accumulation Signal    — turun tapi close upper-half + vol di atas rata
    2. Distribution Signal    — naik tapi close lower-half + vol spike
    3. Stealth Accumulation   — sideways ketat + vol sedikit di atas normal
    4. Markup Phase           — gap up + volume besar setelah akumulasi
    5. Shakeout               — spike turun tajam 1 candle lalu langsung recovery

    Kembalikan list sinyal dengan confidence level (high/med/low).
    Dua level: high ≥ 75, med ≥ 50.
    """
    if len(df) < 20:
        return {'signals': [], 'dominant': None, 'narasi': ('', '')}

    vol_ma    = float(df['Volume'].rolling(20).mean().iloc[-1])
    atr_val   = float(calculate_atr(df.tail(30)).iloc[-1])
    close     = df['Close'].values.astype(float)
    high_arr  = df['High'].values.astype(float)
    low_arr   = df['Low'].values.astype(float)
    open_arr  = df['Open'].values.astype(float)
    vol_arr   = df['Volume'].values.astype(float)

    def _close_pos(i):
        rng = high_arr[i] - low_arr[i]
        return (close[i] - low_arr[i]) / max(rng, 1e-9)

    def _vol_ratio(i):
        return vol_arr[i] / max(vol_ma, 1.0)

    def _conf_label(pct: int) -> str:
        if pct >= 75: return 'high'
        if pct >= 50: return 'med'
        return 'low'

    signals = []
    n = len(df)
    last = n - 1

    # 1. Accumulation Signal (lihat 3 candle terakhir)
    for i in range(max(0, n-3), n):
        if (close[i] < close[i-1]                # harga turun
                and _close_pos(i) > 0.55         # tutup di atas setengah
                and _vol_ratio(i) > 1.4):        # volume di atas rata
            cp  = _close_pos(i)
            vr  = _vol_ratio(i)
            conf = int(min((cp - 0.55)/0.45 * 50 + (vr - 1.4)/1.6 * 50, 95))
            signals.append({
                'key': 'accum_signal', 'style': 'accum',
                'label': 'Akumulasi', 'short': 'ACCU',
                'conf_pct': conf, 'conf': _conf_label(conf),
                'candle_idx': i,
            })
            break

    # 2. Distribution Signal
    for i in range(max(0, n-3), n):
        if (close[i] > close[i-1]
                and _close_pos(i) < 0.45
                and _vol_ratio(i) > 1.8):
            cp  = 1 - _close_pos(i)
            vr  = _vol_ratio(i)
            conf = int(min((cp - 0.55)/0.45 * 50 + (vr - 1.8)/2.2 * 50, 95))
            signals.append({
                'key': 'distrib_signal', 'style': 'distrib',
                'label': 'Distribusi', 'short': 'DIST',
                'conf_pct': conf, 'conf': _conf_label(conf),
                'candle_idx': i,
            })
            break

    # 3. Stealth Accumulation — 5 candle terakhir
    tail5_vol   = vol_arr[-5:]
    tail5_close = close[-5:]
    vol_slightly_above = np.mean(tail5_vol) > vol_ma * 1.05 and np.mean(tail5_vol) < vol_ma * 1.5
    price_range_tight  = (max(tail5_close) - min(tail5_close)) / max(atr_val, 1e-9) < 1.2
    if vol_slightly_above and price_range_tight:
        conf = 68
        signals.append({
            'key': 'stealth_accum', 'style': 'accum',
            'label': 'Akum. Senyap', 'short': 'STL',
            'conf_pct': conf, 'conf': _conf_label(conf),
            'candle_idx': last,
        })

    # 4. Markup Phase — gap up + volume besar setelah 5 hari sideways
    if n >= 7:
        gap_up    = open_arr[last] > close[-2] * 1.005
        big_vol   = _vol_ratio(last) > 2.0
        was_sideways = (max(close[-7:-2]) - min(close[-7:-2])) / max(atr_val, 1e-9) < 2.0
        if gap_up and big_vol and was_sideways:
            vr   = _vol_ratio(last)
            conf = int(min(60 + (vr - 2.0)/3.0 * 35, 95))
            signals.append({
                'key': 'markup', 'style': 'purple',
                'label': 'Markup Phase', 'short': 'MRK',
                'conf_pct': conf, 'conf': _conf_label(conf),
                'candle_idx': last,
            })

    # 5. Shakeout — spike turun tajam lalu langsung recovery hari ini
    if n >= 3:
        prev_drop   = close[-2] - close[-3]   # drop candle kemarin
        today_recov = close[-1] - close[-2]   # recovery hari ini
        drop_size   = abs(prev_drop) / max(atr_val, 1e-9)
        if (prev_drop < 0
                and drop_size > 1.5
                and today_recov > abs(prev_drop) * 0.6
                and _vol_ratio(last-1) > 1.5):
            conf = int(min(55 + drop_size * 8, 88))
            signals.append({
                'key': 'shakeout', 'style': 'warn',
                'label': 'Shakeout', 'short': 'SKO',
                'conf_pct': conf, 'conf': _conf_label(conf),
                'candle_idx': last,
            })

    # Urutkan confidence tertinggi di depan
    signals.sort(key=lambda x: x['conf_pct'], reverse=True)
    dominant = signals[0] if signals else None

    # Narasi dua baris
    narasi_tech, narasi_plain = _build_narasi(signals, dominant)

    return {
        'signals':     signals,
        'dominant':    dominant,
        'narasi_tech': narasi_tech,
        'narasi_plain': narasi_plain,
    }


def _build_narasi(signals: list, dominant: dict | None) -> tuple[str, str]:
    """Bangun narasi teknikal + plain dari sinyal dominant."""
    if dominant is None:
        return "Tidak ada sinyal price-action signifikan.", \
               "Belum ada pola yang cukup kuat untuk dibaca."

    key = dominant['key']
    conf = dominant['conf_pct']

    narasi_map = {
        'accum_signal': (
            f"Candle turun namun close di upper-half dengan volume {conf}% di atas rata — indikasi penyerapan.",
            "Harga turun tapi ada yang beli kuat di bawah. Kemungkinan bandar sedang akumulasi."
        ),
        'distrib_signal': (
            f"Candle naik namun close di lower-half + volume spike — pola distribusi institusional.",
            "Harga naik tapi bandar tampak buang saham ke ritel. Hati-hati jebakan kenaikan."
        ),
        'stealth_accum': (
            "Volume 5 candle sedikit di atas normal, harga bergerak sideways ketat — akumulasi bertahap.",
            "Saham diam-diam dibeli dalam jumlah kecil. Biasanya tanda akan ada pergerakan besar."
        ),
        'markup': (
            f"Gap-up + volume >{conf//10*10}% di atas rata setelah fase sideways — markup phase terdeteksi.",
            "Bandar mulai dorong harga setelah akumulasi selesai. Ini sinyal awal kenaikan besar."
        ),
        'shakeout': (
            "Drop tajam 1 candle diikuti recovery kuat hari ini — pola shakeout sebelum naik.",
            "Kemarin turun tajam tapi hari ini langsung balik. Ini cara bandar buang holder lemah."
        ),
        'buying_climax': (
            "Volume ekstrem + candle bullish besar di level atas — potensi buying climax.",
            "Semua orang beli sekarang, tapi ini justru saat bandar mulai jual. Waspada balik arah."
        ),
        'selling_climax': (
            "Volume ekstrem + candle bearish besar — selling climax, potensi reversal naik.",
            "Semua orang panik jual. Ini biasanya momen bandar masuk beli murah."
        ),
        'absorption': (
            "Volume besar namun harga tidak turun signifikan — demand menyerap supply.",
            "Ada yang beli besar dan menahan harga agar tidak jatuh. Tanda akumulasi aktif."
        ),
        'exhaustion': (
            "Volume tinggi tapi range candle kecil — tenaga gerak mulai habis.",
            "Banyak yang trading tapi harga nggak kemana-mana. Pergerakan besar mungkin sudah hampir habis."
        ),
        'accum_quiet': (
            "5 candle volume rendah konsisten, harga tidak turun — akumulasi senyap (quiet period).",
            "Tidak ada yang buang saham ini. Bandar sedang diam-diam mengumpulkan."
        ),
    }

    tech, plain = narasi_map.get(key, ("Sinyal tidak dikenali.", "Pola belum terdefinisi."))
    return tech, plain


# =============================================================================
# 4e. CHART GENERATOR — 60m + 1D dengan semua indikator & Auto-Fibonacci
# =============================================================================

def _calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast   = close.ewm(span=fast, adjust=False).mean()
    ema_slow   = close.ewm(span=slow, adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line= macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram

def _calc_adx(df: pd.DataFrame, window=14) -> pd.Series:
    high, low, close = df['High'], df['Low'], df['Close']
    plus_dm  = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    mask     = plus_dm < minus_dm
    plus_dm[mask]  = 0
    minus_dm[~mask]= 0
    atr      = calculate_atr(df, window)
    plus_di  = 100 * plus_dm.ewm(alpha=1/window, adjust=False).mean()  / atr.replace(0, 1e-9)
    minus_di = 100 * minus_dm.ewm(alpha=1/window, adjust=False).mean() / atr.replace(0, 1e-9)
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9))
    adx      = dx.ewm(alpha=1/window, adjust=False).mean()
    return adx

def _calc_vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP harian — reset setiap hari baru. Untuk intraday pakai semua data yang ada."""
    typical = (df['High'] + df['Low'] + df['Close']) / 3
    cum_vol  = df['Volume'].cumsum()
    cum_tp_vol = (typical * df['Volume']).cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)

def _calc_fibonacci(df: pd.DataFrame, lookback: int = 50) -> dict:
    """
    Auto-Fibonacci: ambil swing high & low dari `lookback` candle terakhir.
    Level: 0, 23.6, 38.2, 50, 61.8, 78.6, 100
    """
    tail  = df.tail(lookback)
    swing_high = float(tail['High'].max())
    swing_low  = float(tail['Low'].min())
    diff = swing_high - swing_low
    levels = {
        '0%':    swing_high,
        '23.6%': swing_high - 0.236 * diff,
        '38.2%': swing_high - 0.382 * diff,
        '50%':   swing_high - 0.500 * diff,
        '61.8%': swing_high - 0.618 * diff,
        '78.6%': swing_high - 0.786 * diff,
        '100%':  swing_low,
    }
    return levels

def _calc_bb(close: pd.Series, window=20, std_mult=2.0):
    basis  = close.rolling(window).mean()
    std    = close.rolling(window).std(ddof=1)
    upper  = basis + std_mult * std
    lower  = basis - std_mult * std
    return upper, basis, lower

def generate_chart(df: pd.DataFrame, ticker: str, timeframe_label: str,
                   trade_plan: dict | None = None) -> bytes:
    """
    Buat chart lengkap 4 panel:
    Panel 1 (besar): Candlestick + EMA20 + EMA50 + BB + VWAP + Auto-Fibonacci + TP/SL
    Panel 2: Volume bar + Vol MA
    Panel 3: RSI(14) + garis 30/70
    Panel 4: MACD histogram + signal

    Kembalikan PNG sebagai bytes (untuk Vision API dan display Streamlit).
    """
    if len(df) < 30:
        return b''

    # ── Hitung semua indikator ─────────────────────────────────────────────
    close  = df['Close']
    n      = min(100, len(df))   # maks 100 candle terakhir
    df_plot= df.tail(n).copy().reset_index()
    idx    = np.arange(len(df_plot))

    c      = df_plot['Close'].values
    o      = df_plot['Open'].values
    h      = df_plot['High'].values
    l      = df_plot['Low'].values
    v      = df_plot['Volume'].values

    ema20  = df_plot['Close'].ewm(span=20, adjust=False).mean().values
    ema50  = df_plot['Close'].ewm(span=50, adjust=False).mean().values
    bb_u, bb_m, bb_l = _calc_bb(df_plot['Close'])
    vwap   = _calc_vwap(df_plot).values
    macd_l, macd_s, macd_h = _calc_macd(df_plot['Close'])
    rsi    = calculate_rsi(df_plot)
    adx    = _calc_adx(df_plot)
    fib    = _calc_fibonacci(df_plot)
    vol_ma = df_plot['Volume'].rolling(20).mean().values

    # ── Setup figure ───────────────────────────────────────────────────────
    BG    = '#0d1117'; PANEL = '#161b22'; GRID = '#21262d'
    GREEN = '#3fb950'; RED   = '#f85149'; BLUE = '#58a6ff'
    GOLD  = '#ffd700'; PURP  = '#bc8cff'; ORNG = '#db6d28'

    fig = plt.figure(figsize=(16, 11), facecolor=BG)
    gs  = GridSpec(4, 1, figure=fig,
                   height_ratios=[5, 1.2, 1.2, 1.2],
                   hspace=0.06, top=0.94, bottom=0.05, left=0.06, right=0.97)

    ax1 = fig.add_subplot(gs[0])   # candlestick
    ax2 = fig.add_subplot(gs[1], sharex=ax1)   # volume
    ax3 = fig.add_subplot(gs[2], sharex=ax1)   # RSI
    ax4 = fig.add_subplot(gs[3], sharex=ax1)   # MACD

    for ax in [ax1, ax2, ax3, ax4]:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors='#8b949e', labelsize=7)
        ax.spines[:].set_color(GRID)
        ax.yaxis.set_label_position('right')
        ax.yaxis.tick_right()

    # ── Panel 1: Candlestick ───────────────────────────────────────────────
    W  = 0.6
    for i in idx:
        bull = c[i] >= o[i]
        col  = GREEN if bull else RED
        # Wick
        ax1.plot([i, i], [l[i], h[i]], color=col, linewidth=0.8, zorder=2)
        # Body
        y0 = min(o[i], c[i]); y1 = max(o[i], c[i])
        ax1.add_patch(mpatches.FancyBboxPatch(
            (i - W/2, y0), W, max(y1 - y0, (h[i]-l[i])*0.01),
            boxstyle="square,pad=0", facecolor=col,
            edgecolor=col, linewidth=0, zorder=3
        ))

    # EMA & BB
    ax1.plot(idx, ema20, color=BLUE,  linewidth=1.0, label='EMA20', zorder=4)
    ax1.plot(idx, ema50, color=GOLD,  linewidth=1.0, label='EMA50', zorder=4)
    ax1.plot(idx, bb_u.values, color='#8b949e', linewidth=0.6, linestyle='--', label='BB', zorder=4)
    ax1.plot(idx, bb_m.values, color='#8b949e', linewidth=0.5, linestyle=':', zorder=4)
    ax1.plot(idx, bb_l.values, color='#8b949e', linewidth=0.6, linestyle='--', zorder=4)
    ax1.fill_between(idx, bb_u.values, bb_l.values, alpha=0.04, color='#8b949e')

    # VWAP
    ax1.plot(idx, vwap, color=PURP, linewidth=1.0, linestyle='-.', label='VWAP', zorder=4)

    # Auto-Fibonacci
    fib_colors = {'0%':'#3fb950','23.6%':'#58a6ff','38.2%':'#e3b341',
                  '50%':'#ffd700','61.8%':'#e3b341','78.6%':'#f85149','100%':'#f85149'}
    for level_name, level_price in fib.items():
        ax1.axhline(level_price, color=fib_colors[level_name],
                    linewidth=0.5, linestyle=':', alpha=0.7, zorder=1)
        ax1.text(idx[-1] + 0.3, level_price, f' Fib {level_name}',
                 color=fib_colors[level_name], fontsize=5.5, va='center', alpha=0.85)

    # TP / SL overlay
    if trade_plan:
        sl = trade_plan.get('stop_loss'); tp1 = trade_plan.get('tp1'); tp2 = trade_plan.get('tp2')
        if sl:  ax1.axhline(sl,  color=RED,   linewidth=1.2, linestyle='--', alpha=0.9, zorder=5)
        if tp1: ax1.axhline(tp1, color=GREEN, linewidth=1.2, linestyle='--', alpha=0.9, zorder=5)
        if tp2: ax1.axhline(tp2, color=GREEN, linewidth=0.8, linestyle=':', alpha=0.7, zorder=5)
        if sl:  ax1.text(0.5, sl,  f' SL {int(sl):,}'.replace(',','.'),  color=RED,   fontsize=6.5, va='bottom')
        if tp1: ax1.text(0.5, tp1, f' TP1 {int(tp1):,}'.replace(',','.'), color=GREEN, fontsize=6.5, va='bottom')
        if tp2: ax1.text(0.5, tp2, f' TP2 {int(tp2):,}'.replace(',','.'), color=GREEN, fontsize=6.5, va='bottom')

    # ADX annotation
    adx_val = float(adx.iloc[-1]) if len(adx) > 0 else 0
    adx_col = GREEN if adx_val >= 25 else '#8b949e'
    ax1.text(0.01, 0.98, f'ADX {adx_val:.1f}', transform=ax1.transAxes,
             color=adx_col, fontsize=7, va='top', fontweight='bold')

    # Legend
    legend_elements = [
        Line2D([0],[0], color=BLUE,  lw=1.2, label='EMA20'),
        Line2D([0],[0], color=GOLD,  lw=1.2, label='EMA50'),
        Line2D([0],[0], color=PURP,  lw=1.2, linestyle='-.', label='VWAP'),
        Line2D([0],[0], color='#8b949e', lw=0.8, linestyle='--', label='BB'),
    ]
    ax1.legend(handles=legend_elements, loc='upper left', fontsize=6.5,
               facecolor=PANEL, edgecolor=GRID, labelcolor='#c9d1d9', framealpha=0.9)

    ax1.set_title(f'{ticker}  ·  {timeframe_label}  ·  {datetime.now().strftime("%d %b %Y %H:%M")} WIB',
                  color='#c9d1d9', fontsize=9.5, fontweight='bold', loc='left', pad=6)
    ax1.set_ylabel('Harga (Rp)', color='#8b949e', fontsize=7)
    ax1.grid(True, color=GRID, linewidth=0.4, alpha=0.6)

    # ── Panel 2: Volume ────────────────────────────────────────────────────
    vol_colors = [GREEN if c[i] >= o[i] else RED for i in idx]
    ax2.bar(idx, v, color=vol_colors, alpha=0.75, width=0.7, zorder=3)
    ax2.plot(idx, vol_ma, color=GOLD, linewidth=0.9, label='Vol MA20', zorder=4)
    ax2.set_ylabel('Vol', color='#8b949e', fontsize=7)
    ax2.grid(True, color=GRID, linewidth=0.3, alpha=0.5)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x/1e6:.0f}M'))

    # ── Panel 3: RSI ───────────────────────────────────────────────────────
    rsi_vals = rsi.values
    ax3.plot(idx, rsi_vals, color=PURP, linewidth=1.0, zorder=3)
    ax3.fill_between(idx, rsi_vals, 70, where=(rsi_vals > 70), alpha=0.25, color=RED)
    ax3.fill_between(idx, rsi_vals, 30, where=(rsi_vals < 30), alpha=0.25, color=GREEN)
    ax3.axhline(70, color=RED,      linewidth=0.6, linestyle='--', alpha=0.7)
    ax3.axhline(50, color='#8b949e',linewidth=0.4, linestyle=':', alpha=0.5)
    ax3.axhline(30, color=GREEN,    linewidth=0.6, linestyle='--', alpha=0.7)
    ax3.set_ylim(0, 100); ax3.set_ylabel('RSI', color='#8b949e', fontsize=7)
    ax3.text(idx[-1], float(rsi_vals[-1]), f' {rsi_vals[-1]:.1f}',
             color=PURP, fontsize=6.5, va='center')
    ax3.grid(True, color=GRID, linewidth=0.3, alpha=0.5)

    # ── Panel 4: MACD ──────────────────────────────────────────────────────
    hist_colors = [GREEN if v >= 0 else RED for v in macd_h.values]
    ax4.bar(idx, macd_h.values, color=hist_colors, alpha=0.7, width=0.7, zorder=3)
    ax4.plot(idx, macd_l.values, color=BLUE,  linewidth=0.9, label='MACD', zorder=4)
    ax4.plot(idx, macd_s.values, color=ORNG,  linewidth=0.9, label='Signal', zorder=4)
    ax4.axhline(0, color='#8b949e', linewidth=0.4, alpha=0.6)
    ax4.set_ylabel('MACD', color='#8b949e', fontsize=7)
    ax4.legend(loc='upper left', fontsize=5.5, facecolor=PANEL,
               edgecolor=GRID, labelcolor='#c9d1d9', framealpha=0.9)
    ax4.grid(True, color=GRID, linewidth=0.3, alpha=0.5)

    # ── X-axis labels (tanggal/jam) ────────────────────────────────────────
    plt.setp(ax1.get_xticklabels(), visible=False)
    plt.setp(ax2.get_xticklabels(), visible=False)
    plt.setp(ax3.get_xticklabels(), visible=False)
    date_col = df_plot.columns[0]  # index setelah reset_index
    tick_step = max(1, n // 10)
    tick_idx  = idx[::tick_step]
    tick_lbl  = []
    for ti in tick_idx:
        try:
            dt = pd.to_datetime(df_plot[date_col].iloc[ti])
            fmt = '%H:%M' if 'h' in timeframe_label.lower() else '%d/%m'
            tick_lbl.append(dt.strftime(fmt))
        except Exception:
            tick_lbl.append('')
    ax4.set_xticks(tick_idx)
    ax4.set_xticklabels(tick_lbl, fontsize=6.5, color='#8b949e')

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_charts_for_ticker(ticker_jk: str, df_daily: pd.DataFrame,
                                trade_plan: dict | None = None) -> dict[str, bytes]:
    """
    Generate dua chart:
    - '1D'  : data harian  (df_daily, sudah ada)
    - '60m' : download intraday 60m terpisah
    Kembalikan dict {'1D': bytes, '60m': bytes}
    """
    charts = {}
    ticker_clean = ticker_jk.split('.')[0]

    # Chart 1D
    if len(df_daily) >= 30:
        charts['1D'] = generate_chart(df_daily, ticker_clean, '1 Hari', trade_plan)

    # Chart 60m — download on-demand
    try:
        start = (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d')
        df_60m = yf.download(ticker_jk, start=start, interval='60m',
                             auto_adjust=True, progress=False, timeout=20)
        if not df_60m.empty and len(df_60m) >= 20:
            charts['60m'] = generate_chart(df_60m, ticker_clean, '60 Menit', trade_plan)
    except Exception:
        pass

    return charts


# =============================================================================
# 4f. CLAUDE VISION AGENT — baca chart, output BUY / WATCHLIST / IGNORE
# =============================================================================

VISION_SYSTEM_PROMPT = """Kamu adalah Strategy Agent untuk saham IDX (Bursa Efek Indonesia).
Kamu menerima dua chart teknikal (timeframe 60 menit dan 1 Hari) beserta data indikator.
Tugasmu: analisis secara visual dan tentukan keputusan trading.

Output HARUS dalam JSON valid (tidak ada teks lain, tidak ada markdown fence):
{
  "keputusan": "BUY" | "WATCHLIST" | "IGNORE",
  "confidence": 0-100,
  "alasan_singkat": "1 kalimat max 20 kata",
  "analisis": {
    "trend": "bullish|sideways|bearish",
    "momentum": "kuat|lemah|divergen",
    "volume_konfirmasi": true|false,
    "level_kunci": "deskripsi support/resistance penting",
    "risiko_utama": "deskripsi risiko terbesar"
  },
  "timeframe_alignment": "ya|tidak|parsial"
}

Kriteria keputusan:
- BUY: trend naik di kedua TF, volume konfirmasi, RSI tidak overbought (≤70), MACD positif atau cross up, harga di atas EMA20/50
- WATCHLIST: setup hampir siap tapi belum semua konfirmasi terpenuhi, atau sideways dengan potensi breakout
- IGNORE: trend turun jelas, atau sinyal mixed/kontradiktif antar TF, atau overbought ekstrem
"""

def call_vision_agent(charts: dict[str, bytes], indicator_summary: str,
                      anthropic_api_key: str) -> dict:
    """
    Kirim chart ke Claude Vision melalui Anthropic Messages API.
    Kembalikan dict hasil parsing JSON dari model.
    """
    if not charts or not anthropic_api_key:
        return {'keputusan': 'IGNORE', 'confidence': 0,
                'alasan_singkat': 'Tidak ada chart atau API key.',
                'analisis': {}, 'timeframe_alignment': 'tidak'}

    # Bangun content blocks — kirim semua chart yang tersedia
    content = []
    for tf_label, chart_bytes in charts.items():
        if chart_bytes:
            b64 = base64.standard_b64encode(chart_bytes).decode('utf-8')
            content.append({
                "type": "text",
                "text": f"Chart timeframe {tf_label}:"
            })
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64}
            })

    content.append({
        "type": "text",
        "text": f"Data indikator tambahan:\n{indicator_summary}\n\nBerikan keputusan dalam format JSON."
    })

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "system":     VISION_SYSTEM_PROMPT,
                "messages":   [{"role": "user", "content": content}],
            },
            timeout=45
        )
        resp.raise_for_status()
        raw_text = resp.json()['content'][0]['text'].strip()
        # Strip markdown fence jika ada
        raw_text = re.sub(r'^```[a-z]*\n?', '', raw_text)
        raw_text = re.sub(r'\n?```$', '', raw_text)
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {'keputusan': 'IGNORE', 'confidence': 0,
                'alasan_singkat': 'Gagal parse JSON dari Vision.', 'analisis': {}, 'timeframe_alignment': 'tidak'}
    except Exception as e:
        return {'keputusan': 'IGNORE', 'confidence': 0,
                'alasan_singkat': f'Error API: {str(e)[:60]}', 'analisis': {}, 'timeframe_alignment': 'tidak'}


def build_indicator_summary(ind: dict, row: pd.Series) -> str:
    """Ringkasan indikator dalam teks untuk dikirim ke Vision Agent."""
    return (
        f"Ticker: {row.get('Ticker','?')} | Score: {row.get('Score','?')} | Grade: {row.get('Grade','?')}\n"
        f"Harga: {row.get('Live Price','?')} | Zona Beli: {row.get('Buy Min','?')}–{row.get('Buy Max','?')}\n"
        f"RSI: {ind.get('rsi_val','?'):.1f} | CMF: {ind.get('cmf_val','?'):.3f} | "
        f"ATR: {ind.get('atr_val','?'):.1f} | Vol Spike: {ind.get('vol_spike','?'):.2f}×\n"
        f"EMA50: {'Di atas' if ind.get('above_ema50') else 'Di bawah'} | "
        f"EMA20: {'Di atas' if ind.get('above_ema20') else 'Di bawah'} | "
        f"Squeeze: {'Ya' if ind.get('in_squeeze') else 'Tidak'}\n"
        f"TP1: {row.get('TP1','?')} ({row.get('Upside TP1','?')}) | "
        f"TP2: {row.get('TP2','?')} ({row.get('Upside TP2','?')}) | "
        f"SL: {row.get('Stop Loss','?')} ({row.get('Risk%','?')})"
    )


# =============================================================================
# 4g. TELEGRAM NOTIFIER
# =============================================================================

def send_telegram(bot_token: str, chat_id: str, message: str,
                  photo_bytes: bytes | None = None) -> bool:
    """
    Kirim pesan teks + opsional foto ke Telegram.
    Kembalikan True jika sukses.
    """
    if not bot_token or not chat_id:
        return False
    base_url = f"https://api.telegram.org/bot{bot_token}"
    try:
        if photo_bytes:
            resp = requests.post(
                f"{base_url}/sendPhoto",
                data={"chat_id": chat_id, "caption": message,
                      "parse_mode": "HTML"},
                files={"photo": ("chart.png", photo_bytes, "image/png")},
                timeout=20
            )
        else:
            resp = requests.post(
                f"{base_url}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=15
            )
        return resp.status_code == 200
    except Exception:
        return False


def build_telegram_message(row: pd.Series, vision_result: dict) -> str:
    """Format pesan sinyal untuk Telegram VIP grup."""
    keputusan = vision_result.get('keputusan', 'IGNORE')
    conf      = vision_result.get('confidence', 0)
    alasan    = vision_result.get('alasan_singkat', '—')
    analisis  = vision_result.get('analisis', {})

    emoji_map = {'BUY': '🟢', 'WATCHLIST': '🟡', 'IGNORE': '🔴'}
    emoji = emoji_map.get(keputusan, '⚪')

    validity = _check_signal_validity(
        row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"]
    )
    status_label = {"valid": "✅ Siap Entry", "waiting": "⏳ Tunggu", "expired": "🚫 Expired"}[validity['status']]

    msg = (
        f"{emoji} <b>SINYAL {keputusan}</b> — <b>{row['Ticker']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Score: <b>{row['Score']}</b> (Grade {row['Grade']}) | Confidence AI: <b>{conf}%</b>\n"
        f"📍 Status: {status_label}\n\n"
        f"💰 <b>Level Trading:</b>\n"
        f"  Harga Skrg : Rp {int(row['Live Price']):,}\n"
        f"  Zona Beli  : Rp {int(row['Buy Min']):,} – Rp {int(row['Buy Max']):,}\n"
        f"  TP1        : Rp {int(row['TP1']):,} ({row['Upside TP1']})\n"
        f"  TP2        : Rp {int(row['TP2']):,} ({row['Upside TP2']})\n"
        f"  Stop Loss  : Rp {int(row['Stop Loss']):,} ({row['Risk%']})\n"
        f"  R/R        : {row['R/R TP1']} → {row['R/R TP2']}\n\n"
        f"🤖 <b>Analisis AI:</b>\n"
        f"  {alasan}\n"
        f"  Trend: {analisis.get('trend','—')} | Momentum: {analisis.get('momentum','—')}\n"
        f"  Vol Konfirmasi: {'✅' if analisis.get('volume_konfirmasi') else '❌'} | "
        f"TF Alignment: {vision_result.get('timeframe_alignment','—')}\n"
        f"  Risiko: {analisis.get('risiko_utama','—')}\n\n"
        f"⏰ {datetime.now().strftime('%d %b %Y %H:%M')} WIB\n"
        f"<i>Generated by IDX Screener Ultra</i>"
    ).replace(",", ".")
    return msg


# =============================================================================
# 4h. GOOGLE SHEETS LOGGER
# =============================================================================

def append_to_gsheets(sheet_url: str, row: pd.Series,
                       vision_result: dict, gsheets_api_key: str) -> bool:
    """
    Append satu baris sinyal ke Google Sheets via Google Sheets API v4.
    sheet_url: URL spreadsheet (harus dibagikan ke service account atau publik edit).

    Untuk setup mudah tanpa service account, gunakan Make.com / Zapier webhook
    atau Apps Script Web App — kirim POST JSON ke webhook URL.

    Di sini implementasi via Apps Script webhook (lebih mudah untuk pengguna awam).
    """
    if not sheet_url or not sheet_url.startswith('https://'):
        return False

    payload = {
        "timestamp":   datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "ticker":      row.get('Ticker', ''),
        "score":       row.get('Score', ''),
        "grade":       row.get('Grade', ''),
        "live_price":  row.get('Live Price', ''),
        "buy_min":     row.get('Buy Min', ''),
        "buy_max":     row.get('Buy Max', ''),
        "tp1":         row.get('TP1', ''),
        "tp2":         row.get('TP2', ''),
        "stop_loss":   row.get('Stop Loss', ''),
        "rr_tp1":      row.get('R/R TP1', ''),
        "lots":        row.get('Lots', ''),
        "alokasi":     row.get('Alokasi (Rp)', ''),
        "keputusan":   vision_result.get('keputusan', ''),
        "confidence":  vision_result.get('confidence', ''),
        "alasan":      vision_result.get('alasan_singkat', ''),
        "trend":       vision_result.get('analisis', {}).get('trend', ''),
        "momentum":    vision_result.get('analisis', {}).get('momentum', ''),
    }

    try:
        resp = requests.post(sheet_url, json=payload, timeout=15)
        return resp.status_code in (200, 201)
    except Exception:
        return False


# =============================================================================
# 4i. RENDER VISION RESULT CARD (dalam expander di dalam kartu)
# =============================================================================

def render_vision_section(ticker: str, vision_result: dict,
                           charts: dict[str, bytes],
                           bot_token: str, chat_id: str,
                           sheet_url: str, row: pd.Series):
    """
    Render hasil Vision Agent dalam expander di bawah kartu ticker.
    Tampilkan: keputusan, confidence bar, analisis, chart preview, tombol kirim.
    """
    keputusan = vision_result.get('keputusan', 'IGNORE')
    conf      = vision_result.get('confidence', 0)
    alasan    = vision_result.get('alasan_singkat', '—')
    analisis  = vision_result.get('analisis', {})

    color_map = {'BUY': '#3fb950', 'WATCHLIST': '#e3b341', 'IGNORE': '#f85149'}
    emoji_map = {'BUY': '🟢', 'WATCHLIST': '🟡', 'IGNORE': '🔴'}
    col = color_map.get(keputusan, '#8b949e')

    with st.expander(f"{emoji_map.get(keputusan,'')} AI Vision — {keputusan} ({conf}%)", expanded=False):
        # Keputusan badge besar
        st.markdown(
            f'<div style="text-align:center;padding:0.6rem;background:rgba(0,0,0,0.2);'
            f'border-radius:8px;border:1px solid {col};margin-bottom:0.6rem;">'
            f'<span style="font-size:1.4rem;font-weight:900;color:{col};">{keputusan}</span>'
            f'<span style="color:#8b949e;font-size:0.75rem;margin-left:0.5rem;">confidence {conf}%</span>'
            f'</div>', unsafe_allow_html=True
        )

        # Confidence bar
        st.progress(conf / 100)

        # Alasan singkat
        st.markdown(f'*"{alasan}"*')

        # Detail analisis
        if analisis:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Trend:** {analisis.get('trend','—')}")
                st.markdown(f"**Momentum:** {analisis.get('momentum','—')}")
                st.markdown(f"**Vol Konfirmasi:** {'✅' if analisis.get('volume_konfirmasi') else '❌'}")
            with c2:
                st.markdown(f"**TF Alignment:** {vision_result.get('timeframe_alignment','—')}")
                st.markdown(f"**Level Kunci:** {analisis.get('level_kunci','—')}")
                st.markdown(f"**Risiko:** {analisis.get('risiko_utama','—')}")

        # Chart preview tabs
        if charts:
            tf_keys = list(charts.keys())
            if len(tf_keys) > 1:
                tabs = st.tabs([f"📈 Chart {k}" for k in tf_keys])
                for tab, key in zip(tabs, tf_keys):
                    with tab:
                        if charts[key]:
                            st.image(charts[key], use_container_width=True)
            else:
                key = tf_keys[0]
                if charts[key]:
                    st.image(charts[key], use_container_width=True)

        st.markdown("---")

        # Aksi
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"📨 Kirim ke Telegram", key=f"tg_{ticker}",
                         disabled=not (bot_token and chat_id)):
                msg        = build_telegram_message(row, vision_result)
                photo_bytes= charts.get('1D') or charts.get('60m')
                ok         = send_telegram(bot_token, chat_id, msg, photo_bytes)
                if ok:
                    st.success("✅ Terkirim ke Telegram!")
                else:
                    st.error("❌ Gagal kirim — cek bot token & chat ID di sidebar.")

        with col2:
            if st.button(f"📊 Log ke Sheets", key=f"gs_{ticker}",
                         disabled=not sheet_url):
                ok = append_to_gsheets(sheet_url, row, vision_result, '')
                if ok:
                    st.success("✅ Tercatat di Google Sheets!")
                else:
                    st.error("❌ Gagal — cek Sheets webhook URL di sidebar.")


# =============================================================================
# 5. SCORING ENGINE (5 KOMPONEN BERBOBOT)
# =============================================================================
# Bobot total = 100 poin
# Komponen         Maks     Filosofi
# ─────────────────────────────────────────────────────
# A. Trend (EMA)    25 pt   Konfirmasi arah pasar utama
# B. Momentum (RSI) 20 pt   Kekuatan momentum, hindari OB
# C. Money Flow     25 pt   Tekanan beli institusional
# D. Vol Spike      15 pt   Partisipasi pasar
# E. BB Squeeze     15 pt   Potensi breakout terkompresi
# ─────────────────────────────────────────────────────

def score_trend(ind: dict) -> tuple[float, str]:
    """A. Trend filter berbasis EMA50 dan EMA20."""
    if ind['above_ema50'] and ind['above_ema20']:
        return 25.0, "bull"
    elif ind['above_ema50']:
        return 12.0, "bull"
    elif ind['above_ema20']:
        return 5.0,  "neut"
    else:
        return 0.0,  "bear"

def score_rsi(ind: dict) -> tuple[float, str]:
    """
    B. RSI 14.
    - Zona ideal setup: 40–65
    - RSI > 75 = overbought → penalty
    - FIX #8: Base 20 + bonus 5 bisa melebihi cap 20 — dibatasi min() sudah benar
              tapi logika bonus harusnya hanya aktif di zona sweet spot.
    """
    rsi = ind['rsi_val']
    if rsi > 75:
        return 2.0, "bear"
    elif 40 <= rsi <= 65:
        bonus = 5.0 if ind['rsi_rising'] else 0.0
        return min(20.0 + bonus, 20.0), "bull"   # bonus tidak pernah membuat > 20
    elif 65 < rsi <= 75:
        return 10.0, "neut"
    elif 30 <= rsi < 40:
        return 8.0, "neut"
    else:
        return 4.0, "bear"

def score_cmf(ind: dict) -> tuple[float, str]:
    """
    C. CMF 20.
    Skala linier 0–25 untuk CMF positif.
    """
    cmf = ind['cmf_val']
    if cmf > 0:
        base  = 25.0 * min(cmf / 0.25, 1.0)
        bonus = 2.0 if ind['cmf_rising'] else 0.0
        return min(base + bonus, 25.0), "bull"
    elif cmf > -0.05:
        return 5.0, "neut"
    else:
        return 0.0, "bear"

def score_volume(ind: dict) -> tuple[float, str]:
    """
    D. Volume spike vs MA-15.
    FIX #9: Formula lama spike ∈ [1.5, 2.5] → 15*(((s-1.5)/1+0.5)) bisa overflow >15
    misal spike=2.4 → 15*(0.9+0.5)=21. Dibatasi min() sekarang.
    """
    spike = ind['vol_spike']
    if spike >= 2.5:
        return 15.0, "bull"
    elif spike >= 1.5:
        score = min(15.0 * ((spike - 1.5) / 1.0 + 0.5), 15.0)
        return score, "bull"
    elif spike >= 1.2:
        return 7.0, "neut"
    else:
        return 0.0, "neut"

def score_squeeze(ind: dict) -> tuple[float, str]:
    """E. Bollinger Band Squeeze."""
    if ind['squeeze_release']:
        return 15.0, "bull"
    elif ind['in_squeeze']:
        return 8.0, "neut"
    else:
        return 3.0, "neut"

def compute_total_score(ind: dict) -> tuple[float, dict]:
    """
    Gabungkan semua komponen.
    Hard filter: trend bearish total → cap score maksimal 40.
    """
    st_score, st_sig = score_trend(ind)
    rs_score, rs_sig = score_rsi(ind)
    cm_score, cm_sig = score_cmf(ind)
    vo_score, vo_sig = score_volume(ind)
    sq_score, sq_sig = score_squeeze(ind)

    total = st_score + rs_score + cm_score + vo_score + sq_score

    if not ind['above_ema50'] and not ind['above_ema20']:
        total = min(total, 40.0)

    breakdown = {
        'trend':   (round(st_score, 1), st_sig),
        'rsi':     (round(rs_score, 1), rs_sig),
        'cmf':     (round(cm_score, 1), cm_sig),
        'volume':  (round(vo_score, 1), vo_sig),
        'squeeze': (round(sq_score, 1), sq_sig),
    }
    return round(total, 1), breakdown

# =============================================================================
# 6. TRADING PLAN: ATR-BASED + MINIMUM R/R GUARANTEE
# =============================================================================
INTRADAY_PARAMS = {
    'atr_window':  14,
    'atr_sl_mult': 1.5,
    'min_rr1':     1.5,
    'min_rr2':     2.5,
    'ts_rule':     "Trailing 1× ATR; geser ke BEP saat TP1 hit",
    'fixed_risk_pct': 3.0,
}

SWING_PARAMS = {
    'atr_window':  14,
    'atr_sl_mult': 2.0,
    'min_rr1':     2.0,
    'min_rr2':     3.5,
    'ts_rule':     "Set BEP saat TP1 hit; trailing 2× ATR",
    'fixed_risk_pct': 5.0,
}

def build_trade_plan(last_close: float, atr_val: float, mode_params: dict) -> dict:
    """
    Hitung level TP/SL dengan:
    1. SL berbasis ATR (volatilitas aktual)
    2. TP dijamin memenuhi minimum R/R ratio
    3. Fallback ke persen flat jika ATR tidak valid

    FIX #10: stop_loss bisa bernilai negatif jika ATR > last_close → guard ditambah.
    """
    sl_dist = atr_val * mode_params['atr_sl_mult']
    min_sl_dist = last_close * (mode_params['fixed_risk_pct'] / 100.0) * 0.5
    sl_dist = max(sl_dist, min_sl_dist)

    # FIX #10: pastikan SL tidak negatif (misal saham murah + ATR besar)
    stop_loss_raw = last_close - sl_dist
    if stop_loss_raw <= 0:
        sl_dist   = last_close * 0.95    # fallback: SL 5% di bawah harga
        stop_loss_raw = last_close - sl_dist

    tp1_dist = sl_dist * mode_params['min_rr1']
    tp2_dist = sl_dist * mode_params['min_rr2']

    tp1 = last_close + tp1_dist
    tp2 = last_close + tp2_dist

    rr1_actual = tp1_dist / sl_dist
    rr2_actual = tp2_dist / sl_dist

    return {
        'stop_loss': float(np.floor(stop_loss_raw)),
        'tp1':       float(np.ceil(tp1)),
        'tp2':       float(np.ceil(tp2)),
        'sl_dist':   sl_dist,
        'rr1':       round(rr1_actual, 2),
        'rr2':       round(rr2_actual, 2),
        'ts_rule':   mode_params['ts_rule'],
    }

# =============================================================================
# 7. DOWNLOAD ENGINE
# =============================================================================
def download_ticker_chunk(tickers: list, period_days: int, interval: str) -> dict:
    """
    FIX #11: Tambah timeout eksplisit pada yf.download agar tidak hang selamanya.
    FIX #12: Single-ticker path dibedakan dengan benar menggunakan isinstance check
             pada MultiIndex vs flat columns.
    """
    start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    end_date   = datetime.now().strftime('%Y-%m-%d')
    chunk_results = {}

    def _safe_extract(data, ticker):
        try:
            df_t = data[ticker].dropna(subset=['Close'])
            return df_t if not df_t.empty else None
        except KeyError:
            return None

    try:
        data = yf.download(
            " ".join(tickers),
            start=start_date, end=end_date,
            interval=interval, group_by='ticker',
            auto_adjust=True, progress=False, threads=True,
            timeout=30,   # FIX #11: timeout eksplisit
        )
        if data.empty:
            raise ValueError("Empty response")

        # FIX #12: deteksi MultiIndex dengan tepat
        is_multi = isinstance(data.columns, pd.MultiIndex)

        if len(tickers) == 1:
            if not is_multi and 'Close' in data.columns:
                df_t = data.dropna(subset=['Close'])
                if not df_t.empty:
                    chunk_results[tickers[0]] = df_t
            elif is_multi:
                result = _safe_extract(data, tickers[0])
                if result is not None:
                    chunk_results[tickers[0]] = result
        else:
            if is_multi:
                available = data.columns.get_level_values(0).unique().tolist()
                for t in tickers:
                    if t in available:
                        result = _safe_extract(data, t)
                        if result is not None:
                            chunk_results[t] = result

    except Exception:
        # Fallback: download satu per satu
        for t in tickers:
            try:
                df_s = yf.download(t, start=start_date, end=end_date,
                                   interval=interval, auto_adjust=True,
                                   progress=False, timeout=15)
                if not df_s.empty and 'Close' in df_s.columns:
                    df_c = df_s.dropna(subset=['Close'])
                    if not df_c.empty:
                        chunk_results[t] = df_c
            except Exception:
                continue

    return chunk_results

# =============================================================================
# 7b. LIVE PRICE FETCHER (paralel — FIX #13)
# =============================================================================
def _fetch_one_live(ticker: str) -> tuple[str, float | None]:
    """Fetch satu ticker live price, kembalikan (ticker, price)."""
    try:
        info  = yf.Ticker(ticker).fast_info
        price = info.get('last_price') or info.get('lastPrice')
        if price and float(price) > 0:
            return ticker, float(price)
    except Exception:
        pass
    return ticker, None

def fetch_live_prices(tickers_jk: list, max_workers: int = 8) -> dict:
    """
    FIX #13: Versi asli fetch satu per satu secara serial → lambat untuk 20+ ticker.
    Versi baru menggunakan ThreadPoolExecutor untuk paralel I/O.
    """
    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one_live, t): t for t in tickers_jk}
        for future in concurrent.futures.as_completed(futures, timeout=30):
            try:
                ticker, price = future.result()
                if price is not None:
                    result[ticker] = price
            except Exception:
                pass
    return result

# =============================================================================
# 8. MAIN STRATEGY ENGINE
# =============================================================================
def quant_strategy_engine(all_data: dict, config: dict, trading_mode: str) -> pd.DataFrame:
    """
    Pipeline utama:
    1. Filter likuiditas & panjang data
    2. Hitung semua indikator
    3. Scoring multi-komponen
    4. Bangun trading plan ATR-based dengan R/R guarantee
    5. Position sizing dengan batas alokasi
    """
    mode_params = INTRADAY_PARAMS if trading_mode == "Intraday (Fast Trade)" else SWING_PARAMS
    MIN_CANDLES = 60

    results = []
    skipped_reason = {}   # FIX #14: tracking alasan skip untuk debug

    for ticker, df in all_data.items():
        if len(df) < MIN_CANDLES:
            skipped_reason[ticker] = f"candle kurang ({len(df)} < {MIN_CANDLES})"
            continue

        df = df.copy()

        try:
            ind = calculate_indicators(df)
        except Exception as e:
            skipped_reason[ticker] = f"error indikator: {e}"
            continue

        last_close = ind['last_close']
        if not np.isfinite(last_close) or last_close <= 0:
            skipped_reason[ticker] = "harga tidak valid"
            continue

        if last_close < config['min_price'] or last_close > config['max_price']:
            skipped_reason[ticker] = f"harga {last_close:.0f} di luar filter"
            continue
        if ind['adtv'] < config['min_adtv']:
            skipped_reason[ticker] = f"ADTV {ind['adtv']/1e6:.1f}M < minimum"
            continue

        total_score, breakdown = compute_total_score(ind)
        if total_score < config['min_score_threshold']:
            skipped_reason[ticker] = f"score {total_score} < threshold"
            continue

        if total_score >= 80:
            grade = "A"
        elif total_score >= 65:
            grade = "B"
        else:
            grade = "C"

        # ── Analisis tambahan (tidak mempengaruhi score) ───────────────────
        vol_ctx  = analyse_volume_context(df)
        tape     = analyse_tape(df)
        bandar   = analyse_bandarmology(df)

        plan = build_trade_plan(last_close, ind['atr_val'], mode_params)
        stop_loss = plan['stop_loss']
        tp1       = plan['tp1']
        tp2       = plan['tp2']

        buy_min = int(np.floor(last_close - 0.5 * ind['atr_val']))
        buy_max = int(np.ceil(last_close + 0.3 * ind['atr_val']))

        # FIX #15: buy_min tidak boleh < stop_loss (entry di bawah SL tidak logis)
        buy_min = max(buy_min, int(stop_loss) + 1)

        loss_per_share = last_close - stop_loss
        if loss_per_share <= 0:
            skipped_reason[ticker] = "loss_per_share ≤ 0"
            continue

        rupiah_risk    = config['total_capital'] * (config['capital_risk_limit_pct'] / 100.0)
        calc_lots      = int(rupiah_risk / loss_per_share / 100)

        max_alloc      = config['total_capital'] * (config['max_capital_allocation_pct'] / 100.0)
        required_cap   = calc_lots * 100 * last_close
        if required_cap > max_alloc:
            calc_lots    = int(max_alloc / (100 * last_close))
            required_cap = calc_lots * 100 * last_close

        if calc_lots < 1:
            skipped_reason[ticker] = "modal tidak cukup untuk 1 lot"
            continue

        clean_ticker = ticker.split('.')[0]
        results.append({
            "Ticker":       clean_ticker,
            "_ticker_jk":  ticker,
            "Score":        total_score,
            "Grade":        grade,
            "Last Price":   int(round(last_close)),
            "Buy Min":      buy_min,
            "Buy Max":      buy_max,
            "TP1":          int(tp1),
            "Upside TP1":   f"+{round((tp1 - last_close) / last_close * 100, 1)}%",
            "TP2":          int(tp2),
            "Upside TP2":   f"+{round((tp2 - last_close) / last_close * 100, 1)}%",
            "Stop Loss":    int(stop_loss),
            "Risk%":        f"-{round((last_close - stop_loss) / last_close * 100, 1)}%",
            "R/R TP1":      f"1:{plan['rr1']}",
            "R/R TP2":      f"1:{plan['rr2']}",
            "ATR":          round(ind['atr_val'], 1),
            "RSI":          round(ind['rsi_val'], 1),
            "CMF":          round(ind['cmf_val'], 3),
            "TS Kriteria":  plan['ts_rule'],
            "Lots":         int(calc_lots),
            "Alokasi (Rp)": required_cap,
            "_breakdown":   breakdown,
            "_vol_ctx":     vol_ctx,
            "_tape":        tape,
            "_bandar":      bandar,
        })

    # Simpan summary ke session state untuk debug view
    st.session_state['scan_meta'] = {
        'total_input': len(all_data),
        'lolos':       len(results),
        'difilter':    len(skipped_reason),
        'skipped':     skipped_reason,
    }

    if not results:
        return pd.DataFrame()

    passed_tickers_jk = [r["_ticker_jk"] for r in results]
    live_prices = fetch_live_prices(passed_tickers_jk)

    for r in results:
        lp = live_prices.get(r["_ticker_jk"])
        r["Live Price"] = int(round(lp)) if lp else r["Last Price"]
        r["Live Src"]   = "live" if lp else "delayed"
        del r["_ticker_jk"]

    return (
        pd.DataFrame(results)
        .sort_values(by="Score", ascending=False)
        .reset_index(drop=True)
    )

# =============================================================================
# 9. RENDER TRADE CARDS
# =============================================================================
def _pill(label: str, signal: str) -> str:
    return f'<span class="ind-pill ind-{signal}">{label}</span>'

def _tape_pill(short: str, style: str, conf_pct: int) -> str:
    return f'<span class="tape-pill tape-{style}">{short} {conf_pct}%</span>'

def _conf_badge(conf: str) -> str:
    cls = {'high': 'conf-hi', 'med': 'conf-med', 'low': 'conf-lo'}.get(conf, 'conf-lo')
    label = {'high': '▲ Tinggi', 'med': '◆ Sedang', 'low': '● Rendah'}.get(conf, '—')
    return f'<span class="{cls}">{label}</span>'

def _render_volume_ctx_html(vc: dict) -> str:
    """Volume Context Bar — arah candle, vol ratio, body size."""
    if not vc.get('valid'):
        return ''

    dir_color = {'bullish': '#3fb950', 'bearish': '#f85149', 'doji': '#8b949e'}.get(vc['candle_dir'], '#8b949e')
    dir_icon  = {'bullish': '▲', 'bearish': '▼', 'doji': '—'}.get(vc['candle_dir'], '—')
    dir_label = {'bullish': 'Bullish', 'bearish': 'Bearish', 'doji': 'Doji'}.get(vc['candle_dir'], '—')

    vr = vc['vol_ratio']
    if vr >= 2.0:
        bar_color, vol_label = '#3fb950', f'{vr:.1f}× vol (spike)'
    elif vr >= 1.3:
        bar_color, vol_label = '#e3b341', f'{vr:.1f}× vol (atas rata)'
    elif vr >= 0.7:
        bar_color, vol_label = '#8b949e', f'{vr:.1f}× vol (normal)'
    else:
        bar_color, vol_label = '#f85149', f'{vr:.1f}× vol (sepi)'

    bar_width = min(int(vr / 3.0 * 100), 100)
    body_pct  = int(vc['body_pct'] * 100)
    close_pct = int(vc['close_pos'] * 100)

    return (
        f'<div class="vol-ctx">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'  <span style="font-size:0.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;">Volume Konteks</span>'
        f'  <span style="font-size:0.72rem;font-weight:700;color:{dir_color};">{dir_icon} {dir_label}</span>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.3rem;margin-top:0.25rem;">'
        f'  <div><div style="font-size:0.6rem;color:#8b949e;">Vol vs MA</div>'
        f'  <div style="font-size:0.7rem;font-weight:700;color:{bar_color};">{vol_label}</div></div>'
        f'  <div><div style="font-size:0.6rem;color:#8b949e;">Body Size</div>'
        f'  <div style="font-size:0.7rem;font-weight:700;color:#c9d1d9;">{body_pct}% range</div></div>'
        f'  <div><div style="font-size:0.6rem;color:#8b949e;">Close Pos</div>'
        f'  <div style="font-size:0.7rem;font-weight:700;color:#c9d1d9;">{close_pct}% hi-lo</div></div>'
        f'</div>'
        f'<div class="vol-bar-track"><div class="vol-bar-fill" style="width:{bar_width}%;background:{bar_color};"></div></div>'
        f'</div>'
    )

def _render_tape_bandar_html(tape: dict, bandar: dict) -> str:
    """Tape pills + Bandar pills + Confidence + Narasi dua baris."""
    parts = []

    # ── Tape Reading pills ─────────────────────────────────────────────────
    tape_sigs = tape.get('signals', [])
    if tape_sigs:
        pills_html = ''.join(
            _tape_pill(s[3], s[1], s[4]) for s in tape_sigs[:4]
        )
        parts.append(
            f'<div style="margin-bottom:0.25rem;">'
            f'<span style="font-size:0.6rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;margin-right:0.3rem;">Tape</span>'
            f'{pills_html}</div>'
        )

    # ── Bandarmology pills ────────────────────────────────────────────────
    bandar_sigs = bandar.get('signals', [])
    if bandar_sigs:
        pills_html = ''.join(
            _tape_pill(s['short'], s['style'], s['conf_pct']) for s in bandar_sigs[:3]
        )
        dominant = bandar.get('dominant')
        conf_badge = _conf_badge(dominant['conf']) if dominant else ''
        parts.append(
            f'<div style="display:flex;align-items:center;gap:0.3rem;flex-wrap:wrap;margin-bottom:0.25rem;">'
            f'<span style="font-size:0.6rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;">Bandar</span>'
            f'{pills_html}{conf_badge}</div>'
        )

    # ── Narasi ────────────────────────────────────────────────────────────
    narasi_tech  = bandar.get('narasi_tech', '')
    narasi_plain = bandar.get('narasi_plain', '')
    if narasi_tech:
        parts.append(
            f'<div style="background:rgba(255,255,255,0.02);border-left:2px solid #30363d;'
            f'padding:0.3rem 0.5rem;border-radius:0 4px 4px 0;">'
            f'<div class="narasi-tech">"{narasi_tech}"</div>'
            f'<div class="narasi-plain">→ {narasi_plain}</div>'
            f'</div>'
        )

    if not parts:
        return ''

    return (
        f'<div class="section-divider"></div>'
        f'<div style="margin-bottom:0.4rem;">'
        + ''.join(parts) +
        f'</div>'
    )

def _grade_badge(grade: str) -> str:
    cls = {"A": "grade-A", "B": "grade-B", "C": "grade-C"}.get(grade, "grade-C")
    return f'<span class="{cls}">Grade {grade}</span>'

def _price_status_html(live_price: int, ref_close: int, buy_min: int, buy_max: int, live_src: str) -> str:
    """Tampilkan harga live + ref close + status zona beli."""
    if buy_min <= live_price <= buy_max:
        color, icon, label = "#3fb950", "●", "Dalam Zona Beli"
    elif live_price < buy_min:
        color, icon, label = "#58a6ff", "↓", "Di Bawah Zona"
    else:
        color, icon, label = "#e3b341", "↑", "Di Atas Zona"

    src_label = "Live" if live_src == "live" else "Delayed"
    src_color = "#3fb950" if live_src == "live" else "#8b949e"

    ref_note = ""
    if ref_close != live_price:
        diff     = live_price - ref_close
        diff_pct = diff / ref_close * 100
        sign     = "+" if diff >= 0 else ""
        ref_col  = "#3fb950" if diff >= 0 else "#f85149"
        # FIX #16: f-string terputus di tengah (concatenation aneh) — disatukan
        ref_note = (
            f'<span style="font-size:0.68rem;color:{ref_col};margin-left:0.3rem;">'
            f'{sign}{diff_pct:.1f}% vs ref {ref_close:,}'.replace(",", ".") +
            '</span>'
        )

    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:0.4rem;padding:0.35rem 0.6rem;'
        f'background:rgba(255,255,255,0.04);border-radius:6px;'
        f'border-left:3px solid {color};">'
        f'  <div style="display:flex;align-items:baseline;gap:0.4rem;flex-wrap:wrap;">'
        f'    <span style="font-size:1.3rem;font-weight:800;color:{color};">'
        f'      {live_price:,}'.replace(",", ".") +
        f'    </span>'
        f'    {ref_note}'
        f'  </div>'
        f'  <div style="text-align:right;">'
        f'    <div style="font-size:0.65rem;color:{src_color};font-weight:700;">{src_label}</div>'
        f'    <div style="font-size:0.65rem;color:{color};font-weight:600;">{icon} {label}</div>'
        f'  </div>'
        f'</div>'
    )


def compute_best_buy_score(row: pd.Series) -> tuple[float, list[str]]:
    """
    Hitung composite score "layak entry sekarang" untuk setiap baris hasil scan.
    Berbeda dari Score utama (kualitas teknikal) — ini mengukur kesiapan entry:

    Komponen                          Maks    Logika
    ─────────────────────────────────────────────────────────────────────
    1. Signal validity                 30     valid=30, waiting=10, expired=0
    2. Score utama (dinormalisasi)     25     score/100 × 25
    3. Grade bonus                     10     A=10, B=6, C=2
    4. Bandar confidence               15     high=15, med=8, low=3, none=0
    5. Bullish tape confirmation       10     ada sinyal accum tape = +10
    6. Volume konteks                  10     vol spike + bullish candle = +10
    ─────────────────────────────────────────────────────────────────────
    Total maks                        100
    """
    reasons = []
    total   = 0.0

    # 1. Signal validity
    validity = _check_signal_validity(
        row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"]
    )
    if validity['status'] == 'valid':
        total += 30; reasons.append("✅ Harga dalam zona beli")
    elif validity['status'] == 'waiting':
        total += 10; reasons.append("⏳ Di bawah zona, SL masih aman")
    else:
        return 0.0, []   # expired → tidak pernah jadi best buy

    # 2. Score teknikal
    tech_pts = (row["Score"] / 100.0) * 25
    total += tech_pts
    reasons.append(f"📊 Score teknikal {row['Score']}")

    # 3. Grade
    grade_map = {"A": 10, "B": 6, "C": 2}
    total += grade_map.get(row.get("Grade", "C"), 2)
    reasons.append(f"🏅 Grade {row.get('Grade','C')}")

    # 4. Bandar confidence
    bandar = row.get("_bandar", {})
    dom    = bandar.get("dominant")
    if dom:
        conf_pts = {"high": 15, "med": 8, "low": 3}.get(dom.get("conf", "low"), 3)
        # Hanya akumulasi / markup yang bernilai positif; distribusi dikurangi
        if dom.get("style") in ("distrib",):
            conf_pts = -5
            reasons.append(f"⚠️ Sinyal distribusi bandar terdeteksi")
        else:
            total += conf_pts
            reasons.append(f"🔍 Bandar: {dom.get('label','')} ({dom.get('conf','')})")
        total += conf_pts if dom.get("style") not in ("distrib",) else 0
    else:
        reasons.append("— Tidak ada sinyal bandar")

    # 5. Tape bullish confirmation
    tape      = row.get("_tape", {})
    tape_sigs = tape.get("signals", [])
    accum_tape = [s for s in tape_sigs if s[1] in ("accum",)]
    if accum_tape:
        total += 10
        reasons.append(f"📼 Tape: {accum_tape[0][2]}")
    elif any(s[1] == "distrib" for s in tape_sigs):
        total -= 5
        reasons.append("📼 Tape: sinyal distribusi")

    # 6. Volume konteks
    vc = row.get("_vol_ctx", {})
    if vc.get("valid"):
        vol_ok  = vc.get("vol_ratio", 0) >= 1.3
        bull_ok = vc.get("candle_dir") == "bullish"
        if vol_ok and bull_ok:
            total += 10; reasons.append("📊 Vol spike + candle bullish")
        elif vol_ok:
            total += 5;  reasons.append("📊 Vol spike (candle netral/bear)")
        elif bull_ok:
            total += 3;  reasons.append("📊 Candle bullish (vol normal)")

    return round(max(total, 0.0), 1), reasons


def pick_best_buy(df: pd.DataFrame) -> tuple[str | None, float, list[str]]:
    """Pilih satu ticker dengan composite best-buy score tertinggi."""
    if df.empty:
        return None, 0.0, []

    best_ticker, best_score, best_reasons = None, -1.0, []
    for _, row in df.iterrows():
        s, r = compute_best_buy_score(row)
        if s > best_score:
            best_score, best_reasons, best_ticker = s, r, row["Ticker"]

    return best_ticker, best_score, best_reasons


def render_best_buy_banner(ticker: str, score: float, reasons: list[str], row: pd.Series):
    """Tampilkan banner Best Buy di atas hasil scan."""
    validity = _check_signal_validity(
        row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"]
    )
    status_label = "🟢 Harga dalam zona — siap entry" if validity['status'] == 'valid' \
                   else "🟡 Di bawah zona — pantau & tunggu"
    status_color = "#3fb950" if validity['status'] == 'valid' else "#e3b341"

    # Confidence bar visual
    bar_w = min(int(score), 100)
    bar_c = "#ffd700" if score >= 70 else "#e3b341" if score >= 50 else "#8b949e"

    reasons_html = "".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,0.06);'
        f'border-radius:6px;padding:0.1rem 0.4rem;margin:0.1rem;font-size:0.68rem;color:#c9d1d9;">'
        f'{r}</span>'
        for r in reasons
    )

    html = (
        f'<div class="best-buy-banner">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">'
        f'  <div>'
        f'    <span class="best-buy-crown">👑 BEST BUY</span>'
        f'    <span style="font-size:1.5rem;font-weight:900;color:#ffd700;margin-left:0.5rem;">{ticker}</span>'
        f'    <span style="font-size:0.8rem;color:{status_color};margin-left:0.6rem;font-weight:700;">{status_label}</span>'
        f'  </div>'
        f'  <div style="text-align:right;">'
        f'    <div style="font-size:0.65rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;">Entry Score</div>'
        f'    <div style="font-size:1.4rem;font-weight:900;color:#ffd700;">{score}<span style="font-size:0.7rem;color:#8b949e;">/100</span></div>'
        f'  </div>'
        f'</div>'
        f'<div style="margin-top:0.5rem;">'
        f'  <div class="vol-bar-track" style="margin-bottom:0.4rem;">'
        f'    <div class="vol-bar-fill" style="width:{bar_w}%;background:{bar_c};height:6px;border-radius:4px;"></div>'
        f'  </div>'
        f'  <div style="font-size:0.65rem;color:#8b949e;margin-bottom:0.25rem;text-transform:uppercase;letter-spacing:0.4px;">Alasan Pemilihan</div>'
        f'  <div style="line-height:1.8;">{reasons_html}</div>'
        f'</div>'
        f'<div style="margin-top:0.5rem;padding-top:0.4rem;border-top:1px solid rgba(255,215,0,0.2);'
        f'display:grid;grid-template-columns:repeat(4,1fr);gap:0.4rem;font-size:0.72rem;">'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">HARGA LIVE</div>'
        f'  <div style="color:#fff;font-weight:700;">{int(row["Live Price"]):,}'.replace(",",".") + f'</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">ZONA BELI</div>'
        f'  <div style="color:#fff;font-weight:700;">{int(row["Buy Min"]):,}–{int(row["Buy Max"]):,}'.replace(",",".") + f'</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">STOP LOSS</div>'
        f'  <div style="color:#f85149;font-weight:700;">{int(row["Stop Loss"]):,}'.replace(",",".") + f'</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">TARGET TP1</div>'
        f'  <div style="color:#3fb950;font-weight:700;">{int(row["TP1"]):,} <span style="font-size:0.65rem;">{row["Upside TP1"]}</span></div></div>'.replace(",",".") +
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _check_signal_validity(live_price: int, stop_loss: int, buy_min: int, buy_max: int) -> dict:
    """
    Tentukan status validitas sinyal berdasarkan harga live vs level kunci.

    Status:
    - 'valid'    : harga di dalam atau di atas zona beli, di atas SL → normal
    - 'waiting'  : harga di bawah zona beli tapi MASIH di atas SL → belum saatnya entry
    - 'expired'  : harga sudah di bawah SL → sinyal tidak valid, breakdown
    """
    if live_price <= stop_loss:
        gap_pct = round((stop_loss - live_price) / stop_loss * 100, 1)
        return {
            'status':   'expired',
            'title':    '⚠️ Sinyal Tidak Valid — Harga Breakdown',
            'detail':   f'Harga ({live_price:,}) sudah {gap_pct}% di bawah SL ({stop_loss:,}). Jangan entry — sinyal dihitung saat kondisi berbeda.'.replace(',', '.'),
            'action':   'Tunggu konfirmasi reversal atau skip saham ini.',
            'card_cls': 'signal-expired',
            'banner_cls': 'expired-banner',
            'title_color': '#f85149',
        }
    elif live_price < buy_min:
        gap_pct = round((buy_min - live_price) / buy_min * 100, 1)
        return {
            'status':   'waiting',
            'title':    '⏳ Harga di Bawah Zona Beli',
            'detail':   f'Harga ({live_price:,}) masih {gap_pct}% di bawah zona ({buy_min:,}–{buy_max:,}). SL masih aman — pantau, jangan entry dulu.'.replace(',', '.'),
            'action':   'Entry hanya jika harga masuk zona beli.',
            'card_cls': 'signal-waiting',
            'banner_cls': 'waiting-banner',
            'title_color': '#e3b341',
        }
    else:
        return {
            'status':   'valid',
            'title':    '',
            'detail':   '',
            'action':   '',
            'card_cls': '',
            'banner_cls': '',
            'title_color': '',
        }


def render_trade_cards(df: pd.DataFrame, max_cards: int = 6, best_ticker: str | None = None):
    if df.empty:
        st.info("ℹ️ Tidak ada saham yang memenuhi kriteria atau alokasi modal tidak cukup.")
        return

    cards_to_show = df.head(max_cards)
    n = len(cards_to_show)
    COLS = 3

    for i in range(0, n, COLS):
        batch = cards_to_show.iloc[i:i + COLS]
        cols  = st.columns(len(batch))
        for j, (_, row) in enumerate(batch.iterrows()):
            with cols[j]:
                bd      = row.get("_breakdown", {})
                vol_ctx = row.get("_vol_ctx", {})
                tape    = row.get("_tape", {})
                bandar  = row.get("_bandar", {})

                # FIX #17: pill_from_bd didefinisikan di dalam loop → closure bug di Python.
                # Pindahkan ke luar sebagai lambda dengan default arg.
                def pill_from_bd(key, label, _bd=bd):
                    if key not in _bd:
                        return ""
                    score_val, sig = _bd[key]
                    return _pill(f"{label} {score_val:.0f}", sig)

                pills_html = (
                    pill_from_bd("trend",   "EMA")
                    + pill_from_bd("rsi",   "RSI")
                    + pill_from_bd("cmf",   "CMF")
                    + pill_from_bd("volume","VOL")
                    + pill_from_bd("squeeze","SQZ")
                )

                vol_ctx_html     = _render_volume_ctx_html(vol_ctx)
                tape_bandar_html = _render_tape_bandar_html(tape, bandar)

                # ── Signal validity check ──────────────────────────────────
                validity = _check_signal_validity(
                    row["Live Price"], row["Stop Loss"],
                    row["Buy Min"],   row["Buy Max"]
                )
                is_best  = (row["Ticker"] == best_ticker)
                card_cls = validity['card_cls']
                if is_best:
                    card_cls = "best-buy-card"   # override warna border

                # Crown badge — hanya di kartu best buy
                crown_html = (
                    '<div><span class="best-buy-crown">👑 Best Buy</span></div>'
                    if is_best else ''
                )

                # Banner HTML
                is_expired = validity['status'] == 'expired'
                is_waiting = validity['status'] == 'waiting'
                if is_expired or is_waiting:
                    banner_html = (
                        f'<div class="{validity["banner_cls"]}">'
                        f'  <div style="font-size:0.78rem;font-weight:800;color:{validity["title_color"]};margin-bottom:0.2rem;">'
                        f'    {validity["title"]}'
                        f'  </div>'
                        f'  <div style="font-size:0.68rem;color:#c9d1d9;line-height:1.35;">{validity["detail"]}</div>'
                        f'  <div style="font-size:0.65rem;color:#8b949e;margin-top:0.2rem;font-style:italic;">{validity["action"]}</div>'
                        f'</div>'
                    )
                else:
                    banner_html = ''

                # Dimmed wrapper untuk level TP/SL/Lots saat expired
                dim_open  = '<div class="dimmed">' if is_expired else '<div>'
                dim_close = '</div>'

                html = (
                    f'<div class="metric-card {card_cls}">'

                    # Crown badge best buy
                    f'{crown_html}'

                    # Header: ticker + score + grade
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">'
                    f'  <span class="ticker">{row["Ticker"]}</span>'
                    f'  <div style="display:flex;gap:0.4rem;align-items:center;">'
                    f'    {_grade_badge(row["Grade"])}'
                    f'    <span class="score-badge">Score {row["Score"]}</span>'
                    f'  </div>'
                    f'</div>'

                    # Indicator pills (selalu tampil)
                    f'<div style="margin-bottom:0.5rem;">{pills_html}</div>'

                    # Volume context (selalu tampil — tetap informatif)
                    f'{vol_ctx_html}'

                    # Validity banner (tampil jika tidak valid)
                    f'{banner_html}'

                    # Harga live + zona — selalu tampil tapi pesan sudah ada di banner
                    f'{_price_status_html(row["Live Price"], row["Last Price"], row["Buy Min"], row["Buy Max"], row["Live Src"])}'

                    # Level trading — di-dim jika expired (tidak relevan)
                    f'{dim_open}'
                    f'<div class="price-range">{int(row["Buy Min"])} – {int(row["Buy Max"])}</div>'
                    f'<div class="label" style="margin-bottom:0.6rem;">Area Rentang Buy · ATR {row["ATR"]}</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;'
                    f'margin-bottom:0.6rem;border-top:1px solid #30363d;padding-top:0.4rem;">'
                    f'  <div><div class="label">TP 1 <span class="rr-badge">({row["R/R TP1"]})</span></div>'
                    f'  <div class="tp">{int(row["TP1"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP1"]}</span></div></div>'
                    f'  <div><div class="label">TP 2 <span class="rr-badge">({row["R/R TP2"]})</span></div>'
                    f'  <div class="tp">{int(row["TP2"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP2"]}</span></div></div>'
                    f'</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.6rem;">'
                    f'  <div><div class="label">Stop Loss</div>'
                    f'  <div class="sl">{int(row["Stop Loss"])} <span style="font-size:0.68rem;opacity:0.8">{row["Risk%"]}</span></div></div>'
                    f'  <div><div class="label">Trailing Strategy</div>'
                    f'  <div class="ts-rule" style="font-size:0.78rem;">{row["TS Kriteria"]}</div></div>'
                    f'</div>'
                    f'<div style="border-top:1px solid #30363d;padding-top:0.4rem;'
                    f'display:grid;grid-template-columns:1fr 1fr;gap:0.3rem;font-size:0.75rem;">'
                    f'  <div><div class="label">Lots Berbasis Risiko</div>'
                    f'  <div style="color:#fff;font-weight:600">{int(row["Lots"])} Lot</div></div>'
                    f'  <div><div class="label">Maks Alokasi</div>'
                    f'  <div style="color:#58a6ff;font-weight:600">{fmt_idr(row["Alokasi (Rp)"])}</div></div>'
                    f'</div>'
                    f'{dim_close}'

                    # Tape & bandar — selalu tampil (tetap berguna untuk context)
                    f'{tape_bandar_html}'
                    f'</div>'
                )
                st.markdown(html, unsafe_allow_html=True)

                # ── Vision Agent trigger ───────────────────────────────────
                ticker_key = row["Ticker"]
                cache_key  = f"{ticker_key}_{datetime.now().strftime('%Y%m%d')}"
                has_key    = bool(st.session_state.get('anthropic_key', ''))

                if st.button(
                    "🤖 Analisis AI" if has_key else "🔒 Analisis AI (butuh API key)",
                    key=f"vision_btn_{ticker_key}",
                    disabled=not has_key,
                    use_container_width=True,
                ):
                    ticker_jk = ticker_key + ".JK"
                    df_raw    = st.session_state['raw_market_data'].get(ticker_jk, pd.DataFrame())
                    row_dict  = row.to_dict()

                    with st.spinner(f"Generating chart & analisis AI untuk {ticker_key}..."):
                        # Ambil trade plan dari data yang ada
                        trade_plan_preview = {
                            'stop_loss': row.get('Stop Loss'),
                            'tp1': row.get('TP1'),
                            'tp2': row.get('TP2'),
                        }
                        charts = generate_charts_for_ticker(ticker_jk, df_raw, trade_plan_preview)

                        # Bangun indikator summary
                        ind_data = {}
                        try:
                            ind_data = calculate_indicators(df_raw)
                        except Exception:
                            pass
                        ind_summary = build_indicator_summary(ind_data, row)

                        # Panggil Vision Agent
                        vision_result = call_vision_agent(
                            charts, ind_summary,
                            st.session_state.get('anthropic_key', '')
                        )

                        # Cache hasil
                        st.session_state['vision_cache'][cache_key] = {
                            'result': vision_result,
                            'charts': charts,
                        }

                # Tampilkan hasil Vision jika sudah ada di cache
                if cache_key in st.session_state.get('vision_cache', {}):
                    cached = st.session_state['vision_cache'][cache_key]
                    render_vision_section(
                        ticker_key,
                        cached['result'],
                        cached['charts'],
                        st.session_state.get('tg_token', ''),
                        st.session_state.get('tg_chatid', ''),
                        st.session_state.get('sheets_url', ''),
                        row,
                    )

# =============================================================================
# 10. SIDEBAR
# =============================================================================

# ── Integrasi AI Vision + Notifikasi ──────────────────────────────────────
st.sidebar.header("🤖 AI Vision & Notifikasi")
with st.sidebar.expander("⚙️ Konfigurasi Integrasi", expanded=False):
    st.caption("Credentials hanya tersimpan di sesi ini.")

    anthropic_key = st.text_input("Anthropic API Key", type="password",
                                   placeholder="sk-ant-...",
                                   help="Dapatkan di console.anthropic.com")
    st.markdown("**Telegram**")
    tg_token  = st.text_input("Bot Token", type="password", placeholder="123456:ABC-...",
                               help="Dari @BotFather di Telegram")
    tg_chatid = st.text_input("Chat ID / Group ID", placeholder="-100xxxxxxxxx",
                               help="Gunakan @userinfobot untuk cek ID grup")
    st.markdown("**Google Sheets** (via Apps Script Webhook)")
    sheets_url = st.text_input("Webhook URL", placeholder="https://script.google.com/macros/s/...",
                                help="Buat Apps Script Web App, deploy as anyone. Panduan di sidebar bawah.")

    if anthropic_key:
        st.success("✅ Anthropic key aktif")
    if tg_token and tg_chatid:
        if st.button("🔔 Test Telegram"):
            ok = send_telegram(tg_token, tg_chatid,
                               "✅ <b>IDX Screener Ultra</b> — koneksi Telegram berhasil!")
            st.success("Terkirim!") if ok else st.error("Gagal — cek token & chat ID.")

    # Panduan singkat GSheets
    with st.expander("📖 Cara Setup Google Sheets"):
        st.markdown("""
1. Buka [script.google.com](https://script.google.com)
2. Buat project baru → paste kode di bawah
3. Deploy → **Web App** → Execute as: **Me** → Who has access: **Anyone**
4. Copy URL deployment → paste di atas

```
function doPost(e) {
  var sheet = SpreadsheetApp.openByUrl('URL_SPREADSHEET_KAMU').getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  sheet.appendRow([
    data.timestamp, data.ticker, data.score, data.grade,
    data.live_price, data.buy_min, data.buy_max,
    data.tp1, data.tp2, data.stop_loss, data.rr_tp1,
    data.lots, data.alokasi, data.keputusan,
    data.confidence, data.alasan, data.trend, data.momentum
  ]);
  return ContentService.createTextOutput('OK');
}
```
        """)

# Persist credentials ke session state
st.session_state['anthropic_key'] = anthropic_key
st.session_state['tg_token']      = tg_token
st.session_state['tg_chatid']     = tg_chatid
st.session_state['sheets_url']    = sheets_url

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Parameter Algoritma")
capital         = st.sidebar.number_input("Total Modal Akun (Rp)", value=50_000_000, step=5_000_000, min_value=1_000_000)
risk_limit      = st.sidebar.slider("Maks Risiko per Trade (%)", 0.5, 5.0, 2.0, 0.5)
allocation_limit= st.sidebar.slider("Maks Alokasi Dana per Saham (%)", 10, 50, 25, 5)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filter Likuiditas & Harga")
min_adtv_value  = st.sidebar.number_input("Minimal ADTV (Rp)", value=500_000_000, step=100_000_000, min_value=0)
min_px          = st.sidebar.number_input("Harga Minimal Saham (Rp)", value=100, step=50, min_value=1)
max_px          = st.sidebar.number_input("Harga Maksimal Saham (Rp)", value=25_000, step=500, min_value=1)
min_score       = st.sidebar.slider("Min Score Threshold", 50, 85, 60, 5,
                                     help="Semakin tinggi = sinyal lebih selektif")

if min_px >= max_px:
    st.sidebar.error("⚠️ Harga Minimal harus lebih kecil dari Harga Maksimal.")

# FIX: Debug panel pakai placeholder — diisi SETELAH engine jalan
st.sidebar.markdown("---")
debug_placeholder = st.sidebar.empty()

config_engine = {
    'total_capital':           capital,
    'capital_risk_limit_pct':  risk_limit,
    'max_capital_allocation_pct': allocation_limit,
    'min_adtv':                min_adtv_value,
    'min_price':               min_px,
    'max_price':               max_px,
    'min_score_threshold':     float(min_score),
}

# =============================================================================
# 11. MAIN UI
# =============================================================================
trading_mode = st.radio(
    "📊 **Pilih Gaya Trading:**",
    ["Swing Trading (Harian)", "Intraday (Fast Trade)"],
    horizontal=True,
)

st.markdown("### 📋 Daftar Saham")
input_tab, upload_tab = st.tabs(["✏️ Input Manual", "📂 Upload CSV"])
tickers_ready = ["BBRI.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

with input_tab:
    ticker_text = st.text_area("Kode Saham (pisah koma/spasi):", value="BBRI, BBCA, BMRI, TLKM, ASII", height=100)
    if ticker_text.strip():
        tickers_ready = tickers_from_text(ticker_text)

uploaded_csv = None
with upload_tab:
    uploaded_csv = st.file_uploader("Upload CSV emiten:", type=["csv"])
    if uploaded_csv is not None:
        try:
            t_csv = parse_tickers_from_df(pd.read_csv(uploaded_csv))
            if t_csv:
                tickers_ready = t_csv
                st.success(f"✅ {len(tickers_ready)} saham dimuat.")
            else:
                st.warning("⚠️ Tidak ada ticker valid dalam CSV.")
        except Exception as e:
            st.error(f"Error CSV: {e}")

if uploaded_csv is None:
    local_tickers = load_local_emiten_csv()
    if local_tickers:
        tickers_ready = local_tickers

st.markdown("---")
btn_col1, btn_col2 = st.columns([1, 4])
with btn_col1:
    execute_scan = st.button("🚀 Jalankan Skrining", type="primary", use_container_width=True)
with btn_col2:
    if st.button("🗑️ Reset Cache & State"):
        st.cache_data.clear()
        st.session_state['raw_market_data']  = {}
        st.session_state['last_loaded_mode'] = None
        st.session_state['scan_meta']        = {}
        st.success("Reset berhasil.")

# =============================================================================
# 12. EXECUTION CORE
# =============================================================================
if execute_scan:
    if not tickers_ready:
        st.error("❌ Daftar emiten kosong.")
        st.stop()
    if min_px >= max_px:
        st.error("❌ Filter harga tidak valid.")
        st.stop()

    p_days, p_interval = (30, "60m") if trading_mode == "Intraday (Fast Trade)" else (120, "1d")
    CHUNK_SIZE = 15 if trading_mode == "Intraday (Fast Trade)" else 40

    sorted_tickers = sorted(set(tickers_ready))
    chunks         = [sorted_tickers[i:i + CHUNK_SIZE] for i in range(0, len(sorted_tickers), CHUNK_SIZE)]
    total_chunks   = len(chunks)
    buffer         = {}

    status_ph  = st.empty()
    progress_b = st.progress(0)

    for idx, chunk in enumerate(chunks):
        n_done = min((idx + 1) * CHUNK_SIZE, len(sorted_tickers))
        status_ph.markdown(
            f"⏳ Mengunduh {n_done}/{len(sorted_tickers)} emiten (Batch {idx+1}/{total_chunks})…"
        )
        progress_b.progress(int((idx + 1) / total_chunks * 100))
        buffer.update(download_ticker_chunk(chunk, p_days, p_interval))

    status_ph.empty()
    progress_b.empty()

    if not buffer:
        st.error("❌ Tidak ada data berhasil diunduh. Cek koneksi atau daftar ticker.")
        st.stop()

    st.session_state['raw_market_data']  = buffer
    st.session_state['last_loaded_mode'] = trading_mode
    st.success(f"✅ Data berhasil untuk {len(buffer)}/{len(sorted_tickers)} saham.")

# ── Auto-render jika data tersedia & mode cocok ────────────────────────────
if st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] == trading_mode:
    final_df = quant_strategy_engine(st.session_state['raw_market_data'], config_engine, trading_mode)

    st.markdown(f"### 📈 Hasil Scan [{trading_mode}]")

    # ── Best Buy Recommendation ───────────────────────────────────────────
    best_ticker, best_score, best_reasons = pick_best_buy(final_df)
    if best_ticker:
        best_row = final_df[final_df["Ticker"] == best_ticker].iloc[0]
        render_best_buy_banner(best_ticker, best_score, best_reasons, best_row)
    else:
        st.info("ℹ️ Tidak ada saham dengan sinyal valid yang cukup kuat untuk direkomendasikan entry sekarang.")

    render_trade_cards(final_df, max_cards=6, best_ticker=best_ticker)

    # ── Tabel Ringkas untuk Orang Awam ────────────────────────────────────
    if not final_df.empty:
        st.markdown("---")
        st.markdown("### 📋 Ringkasan Semua Hasil Skrining")
        st.caption("Semua saham yang lolos filter, diurutkan dari yang paling direkomendasikan.")

        # Bangun tabel yang bersih dan mudah dibaca
        def _validity_label(row):
            v = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
            return {"valid": "✅ Siap Entry", "waiting": "⏳ Tunggu Dulu", "expired": "🚫 Hindari"}[v["status"]]

        def _bandar_label(row):
            dom = row.get("_bandar", {}).get("dominant")
            if not dom:
                return "—"
            conf_map = {"high": "🔴", "med": "🟡", "low": "⚪"}
            return f"{conf_map.get(dom['conf'], '')} {dom['label']}"

        def _tape_label(row):
            sigs = row.get("_tape", {}).get("signals", [])
            if not sigs:
                return "—"
            return sigs[0][2]  # nama sinyal terkuat

        tabel_rows = []
        for _, row in final_df.iterrows():
            is_best = row["Ticker"] == best_ticker
            tabel_rows.append({
                "🏆":          "👑" if is_best else "",
                "Saham":       row["Ticker"],
                "Harga Skrg":  f"Rp {int(row['Live Price']):,}".replace(",", "."),
                "Zona Beli":   f"Rp {int(row['Buy Min']):,} – {int(row['Buy Max']):,}".replace(",", "."),
                "Target 1":    f"Rp {int(row['TP1']):,} ({row['Upside TP1']})".replace(",", "."),
                "Target 2":    f"Rp {int(row['TP2']):,} ({row['Upside TP2']})".replace(",", "."),
                "Stop Loss":   f"Rp {int(row['Stop Loss']):,} ({row['Risk%']})".replace(",", "."),
                "R/R":         row["R/R TP1"],
                "Score":       row["Score"],
                "Grade":       row["Grade"],
                "Status":      _validity_label(row),
                "Sinyal Bandar": _bandar_label(row),
                "Tape":        _tape_label(row),
                "Lot Saran":   f"{int(row['Lots'])} lot",
                "Alokasi":     fmt_idr(row["Alokasi (Rp)"]),
            })

        tabel_df = pd.DataFrame(tabel_rows)

        # Style — warna baris berdasarkan status
        def _style_row(row):
            status = row["Status"]
            if "Siap" in status:
                bg = "background-color: rgba(63,185,80,0.07)"
            elif "Tunggu" in status:
                bg = "background-color: rgba(227,179,65,0.07)"
            elif "Hindari" in status:
                bg = "background-color: rgba(248,81,73,0.07)"
            else:
                bg = ""
            return [bg] * len(row)

        styled = (
            tabel_df.style
            .apply(_style_row, axis=1)
            .set_properties(**{
                "font-size": "0.82rem",
                "text-align": "left",
            })
            .set_table_styles([{
                "selector": "th",
                "props": [("font-size", "0.75rem"), ("text-transform", "uppercase"),
                          ("letter-spacing", "0.4px"), ("color", "#8b949e")]
            }])
        )

        st.dataframe(styled, use_container_width=True, hide_index=True,
                     height=min(80 + len(tabel_rows) * 38, 600))
    meta = st.session_state.get('scan_meta', {})
    with debug_placeholder.expander("🔬 Debug / Audit Scan", expanded=False):
        st.write(f"**Input:** {meta.get('total_input', 0)} saham")
        st.write(f"**Lolos:** {meta.get('lolos', 0)} saham")
        st.write(f"**Difilter:** {meta.get('difilter', 0)} saham")
        skipped = meta.get('skipped', {})
        if skipped:
            st.dataframe(
                pd.DataFrame(list(skipped.items()), columns=["Ticker", "Alasan"]),
                use_container_width=True, height=200
            )
        else:
            st.caption("Semua saham lolos filter atau tidak ada yang difilter.")

elif st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] != trading_mode:
    st.warning("⚠️ Mode trading diubah. Klik **🚀 Jalankan Skrining** untuk memperbarui data.")

# ── Fallback: debug panel tetap terisi dari session state sebelumnya ──────
if not st.session_state.get('raw_market_data'):
    with debug_placeholder.expander("🔬 Debug / Audit Scan", expanded=False):
        st.caption("Jalankan skrining dulu.")
elif 'scan_meta' in st.session_state and st.session_state['scan_meta']:
    meta = st.session_state['scan_meta']
    # Hanya render kalau placeholder belum diisi (tidak ada cara cek langsung,
    # tapi safe karena Streamlit idempotent — render ulang tidak masalah)
    with debug_placeholder.expander("🔬 Debug / Audit Scan", expanded=False):
        st.write(f"**Input:** {meta.get('total_input', 0)} saham")
        st.write(f"**Lolos:** {meta.get('lolos', 0)} saham")
        st.write(f"**Difilter:** {meta.get('difilter', 0)} saham")
        skipped = meta.get('skipped', {})
        if skipped:
            st.dataframe(
                pd.DataFrame(list(skipped.items()), columns=["Ticker", "Alasan"]),
                use_container_width=True, height=200
            )
        else:
            st.caption("Semua saham lolos filter.")
