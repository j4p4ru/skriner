import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
import concurrent.futures
from datetime import datetime, timedelta
from functools import lru_cache

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

    Fallback: jika data < bb_window, kembalikan Series False (tidak dalam squeeze).
    """
    if len(df) < bb_window:
        return pd.Series(False, index=df.index)

    basis   = df['Close'].rolling(bb_window).mean()
    bb_std_ = df['Close'].rolling(bb_window).std(ddof=1)
    bb_upper = basis + bb_std * bb_std_
    bb_lower = basis - bb_std * bb_std_

    atr = calculate_atr(df, window=atr_window)
    kc_upper = basis + kc_mult * atr
    kc_lower = basis - kc_mult * atr

    squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    return squeeze.fillna(False)

def calculate_adx(df: pd.DataFrame, window: int = 14) -> dict:
    """
    Average Directional Index (ADX) — kekuatan tren, bukan arahnya.
    Kembalikan dict: {'adx': float, 'di_plus': float, 'di_minus': float}

    ADX > 25 = tren kuat (bull atau bear)
    ADX > 20 = tren mulai terbentuk
    ADX < 20 = sideways / konsolidasi

    Digunakan sebagai filter: squeeze release lebih valid jika ADX mulai naik.
    """
    if len(df) < window + 2:
        return {'adx': 0.0, 'di_plus': 0.0, 'di_minus': 0.0}

    high  = df['High'].values.astype(float)
    low   = df['Low'].values.astype(float)
    close = df['Close'].values.astype(float)

    # True Range
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low,
         np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))

    # Directional Movement
    up_move   = high - np.roll(high, 1)
    down_move = np.roll(low, 1) - low
    up_move[0]   = 0.0
    down_move[0] = 0.0

    dm_plus  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    dm_minus = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # Wilder smoothing (sama dengan ATR)
    alpha = 1.0 / window
    atr_w    = pd.Series(tr).ewm(alpha=alpha, adjust=False).mean().values
    dmp_w    = pd.Series(dm_plus).ewm(alpha=alpha, adjust=False).mean().values
    dmm_w    = pd.Series(dm_minus).ewm(alpha=alpha, adjust=False).mean().values

    safe_atr = np.where(atr_w > 0, atr_w, 1e-9)
    di_plus  = 100.0 * dmp_w / safe_atr
    di_minus = 100.0 * dmm_w / safe_atr

    di_sum  = di_plus + di_minus
    dx      = np.where(di_sum > 0, 100.0 * np.abs(di_plus - di_minus) / di_sum, 0.0)
    adx_s   = pd.Series(dx).ewm(alpha=alpha, adjust=False).mean().values

    return {
        'adx':      round(float(adx_s[-1]), 1),
        'di_plus':  round(float(di_plus[-1]), 1),
        'di_minus': round(float(di_minus[-1]), 1),
    }




def calculate_indicators(df: pd.DataFrame) -> dict:
    """
    Hitung semua indikator sekaligus dan kembalikan sebagai dict scalar.
    Kalkulasi dilakukan sekali, bukan berulang di setiap fungsi scoring.
    """
    close  = df['Close']
    volume = df['Volume']

    # EMA trend — tiga level
    ema200 = close.ewm(span=200, adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema20  = close.ewm(span=20,  adjust=False).mean()
    last_close = float(close.iloc[-1])
    ema200_available = len(close) >= 200
    above_ema200 = last_close > float(ema200.iloc[-1]) if ema200_available else False
    above_ema50  = last_close > float(ema50.iloc[-1])
    above_ema20  = last_close > float(ema20.iloc[-1])

    # EMA20 slope — cek apakah tren pendek sedang naik (bandingkan 3 candle terakhir)
    ema20_vals   = ema20.iloc[-4:].values
    ema20_rising = float(ema20_vals[-1]) > float(ema20_vals[-3]) if len(ema20_vals) >= 3 else False

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

    # ADX — kekuatan tren (tidak mempengaruhi arah, hanya intensitas)
    adx_data    = calculate_adx(df)
    adx_val     = adx_data['adx']
    adx_rising  = adx_val > 20  # tren sedang terbentuk

    # Volume spike vs MA-15
    vol_ma15    = float(volume.rolling(15).mean().iloc[-1])
    vol_last    = float(volume.iloc[-1])
    vol_spike   = vol_last / max(vol_ma15, 1.0)

    # ADTV (MA-20 volume × harga)
    vol_ma20    = float(volume.rolling(20).mean().iloc[-1])
    adtv        = vol_ma20 * last_close

    # Guard: atr_val harus positif dan finite
    if not np.isfinite(atr_val) or atr_val <= 0:
        raise ValueError(f"ATR tidak valid: {atr_val}")

    return {
        'last_close':      last_close,
        'ema200_available': ema200_available,
        'above_ema200':    above_ema200,
        'above_ema50':     above_ema50,
        'above_ema20':     above_ema20,
        'ema20_rising':    ema20_rising,
        'atr_val':         atr_val,
        'atr_pct':         atr_pct,
        'cmf_val':         cmf_val,
        'cmf_rising':      cmf_rising,
        'rsi_val':         rsi_val,
        'rsi_rising':      rsi_rising,
        'in_squeeze':      in_squeeze,
        'squeeze_release': squeeze_release,
        'adx_val':         adx_val,
        'adx_rising':      adx_rising,
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
    """
    A. Trend filter berbasis EMA200 + EMA50 + EMA20 slope.
    Bobot max = 25 poin.

    Hierarki:
    - Di atas EMA50 + EMA20 (bull alignment)          → 20 base
    - Di atas EMA200 juga (long-term uptrend)         → +3 bonus
    - EMA20 slope naik (momentum jangka pendek bagus) → +2 bonus
    - Hanya di atas EMA50                             → 12
    - Hanya di atas EMA20                             → 5
    - Di bawah semua                                  → 0, capped di 40 total
    """
    ema200_available = ind.get('ema200_available', False)
    above_200 = ind.get('above_ema200', False)
    above_50  = ind['above_ema50']
    above_20  = ind['above_ema20']
    slope_ok  = ind.get('ema20_rising', False)

    if above_50 and above_20:
        base  = 20.0
        bonus = (3.0 if ema200_available and above_200 else 0.0) + (2.0 if slope_ok else 0.0)
        return min(base + bonus, 25.0), "bull"
    elif above_50:
        return 12.0, "bull"
    elif above_20:
        return 5.0, "neut"
    else:
        return 0.0, "bear"

def score_rsi(ind: dict) -> tuple[float, str]:
    """
    B. RSI 14.
    - Zona ideal setup: 40–65  → skor 15 base + bonus 5 jika rising  = maks 20
    - RSI 65–75 (hangat)       → 10 flat, tidak ada bonus
    - RSI 30–40 (oversold warning) → 8 flat
    - RSI > 75 (overbought)    → penalti berat 2
    - RSI < 30 (ekstrem oversold)  → 4
    Bonus rising HANYA aktif di zona 40–65 agar tidak mendorong skor
    di zona yang seharusnya netral.
    """
    rsi = ind['rsi_val']
    if rsi > 75:
        return 2.0, "bear"
    elif 40 <= rsi <= 65:
        base  = 10.0 + (rsi - 40) / 25.0 * 5.0   # linear 10→15 di zona sweet spot
        bonus = 5.0 if ind['rsi_rising'] else 0.0
        return min(base + bonus, 20.0), "bull"
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
    """
    E. Bollinger Band Squeeze + ADX confirmation.

    Squeeze release LEBIH VALID jika ADX > 20 (tren sedang terbentuk).
    Squeeze tanpa ADX = kompresi saja, belum tentu akan breakout.

    Skor:
    - Squeeze release + ADX rising (tren valid)  → 15
    - Squeeze release saja (ADX lemah)            → 10
    - Dalam squeeze (energi menumpuk)             → 8
    - Tidak squeeze, tidak release               → 3
    """
    adx_ok = ind.get('adx_rising', False)
    if ind['squeeze_release']:
        return (15.0, "bull") if adx_ok else (10.0, "bull")
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
    # Penalti tambahan jika di bawah EMA200 (downtrend jangka panjang)
    if ind.get('ema200_available', False) and not ind.get('above_ema200', False) and not ind['above_ema50']:
        total = min(total, 35.0)

    breakdown = {
        'trend':   (round(st_score, 1), st_sig),
        'rsi':     (round(rs_score, 1), rs_sig),
        'cmf':     (round(cm_score, 1), cm_sig),
        'volume':  (round(vo_score, 1), vo_sig),
        'squeeze': (round(sq_score, 1), sq_sig),
        # ADX disimpan di breakdown untuk info display (bukan scoring terpisah)
        'adx':     (round(ind.get('adx_val', 0.0), 1), 'bull' if ind.get('adx_rising') else 'neut'),
    }
    return round(total, 1), breakdown

# =============================================================================
# 6. TRADING PLAN: ATR-BASED + MINIMUM R/R GUARANTEE
# =============================================================================
INTRADAY_PARAMS = {
    'atr_window':     14,
    'atr_sl_mult':    1.5,
    'min_rr1':        1.5,
    'min_rr2':        2.5,
    'min_rr3':        4.0,
    'ts_rule':        "Trailing 1× ATR; geser ke BEP saat TP1 hit",
    'fixed_risk_pct': 3.0,
}

SWING_PARAMS = {
    'atr_window':     14,
    'atr_sl_mult':    2.0,
    'min_rr1':        2.0,
    'min_rr2':        3.5,
    'min_rr3':        5.5,
    'ts_rule':        "Set BEP saat TP1 hit; trailing 2× ATR menuju TP2",
    'fixed_risk_pct': 5.0,
}

def snap_to_tick(price: float, direction: str = "floor") -> int:
    """
    Snap harga ke fraksi harga IDX yang valid.

    Fraksi harga IDX (BEI):
    < 200        → Rp 1
    200 – 500    → Rp 2   (kelipatan genap)
    500 – 2000   → Rp 5
    2000 – 5000  → Rp 10
    5000 – 10000 → Rp 25
    ≥ 10000      → Rp 50

    direction: "floor" untuk SL/buy_min, "ceil" untuk TP/buy_max.
    """
    p = float(price)
    if p < 200:
        tick = 1
    elif p < 500:
        tick = 2
    elif p < 2000:
        tick = 5
    elif p < 5000:
        tick = 10
    elif p < 10000:
        tick = 25
    else:
        tick = 50

    if direction == "ceil":
        return int(np.ceil(p / tick) * tick)
    else:
        return int(np.floor(p / tick) * tick)


def build_trade_plan(last_close: float, atr_val: float, mode_params: dict) -> dict:
    """
    Hitung level TP/SL dengan:
    1. SL berbasis ATR (volatilitas aktual)
    2. TP dijamin memenuhi minimum R/R ratio
    3. TP3 sebagai extended target (runner position)
    4. Semua level di-snap ke fraksi harga IDX yang valid
    5. Guard: SL tidak negatif, R/R minimum 1.5

    Partial Exit Plan (standar):
    - TP1 → exit 40% posisi, geser SL ke BEP
    - TP2 → exit 40% posisi, biarkan sisa runner
    - TP3 → exit sisa (20%) atau trailing stop
    """
    sl_dist = atr_val * mode_params['atr_sl_mult']
    min_sl_dist = last_close * (mode_params['fixed_risk_pct'] / 100.0) * 0.5
    sl_dist = max(sl_dist, min_sl_dist)

    stop_loss_raw = last_close - sl_dist
    if stop_loss_raw <= 0:
        sl_dist       = last_close * 0.95
        stop_loss_raw = last_close - sl_dist

    tp1_dist = max(sl_dist * mode_params['min_rr1'], sl_dist * 1.5)
    tp2_dist = sl_dist * mode_params['min_rr2']
    tp3_dist = sl_dist * mode_params['min_rr3']

    # Snap ke fraksi IDX yang valid
    stop_loss = snap_to_tick(stop_loss_raw, "floor")
    tp1       = snap_to_tick(last_close + tp1_dist, "ceil")
    tp2       = snap_to_tick(last_close + tp2_dist, "ceil")
    tp3       = snap_to_tick(last_close + tp3_dist, "ceil")

    # Hitung ulang sl_dist berdasarkan harga yang sudah di-snap
    sl_dist_actual = last_close - stop_loss
    if sl_dist_actual <= 0:
        sl_dist_actual = sl_dist

    rr1_actual = round((tp1 - last_close) / sl_dist_actual, 2)
    rr2_actual = round((tp2 - last_close) / sl_dist_actual, 2)
    rr3_actual = round((tp3 - last_close) / sl_dist_actual, 2)

    partial_plan = "TP1: exit 40% → geser SL ke BEP | TP2: exit 40% | TP3/Trail: sisa 20%"

    return {
        'stop_loss':    float(stop_loss),
        'tp1':          float(tp1),
        'tp2':          float(tp2),
        'tp3':          float(tp3),
        'sl_dist':      sl_dist_actual,
        'rr1':          rr1_actual,
        'rr2':          rr2_actual,
        'rr3':          rr3_actual,
        'ts_rule':      mode_params['ts_rule'],
        'partial_plan': partial_plan,
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
    # yfinance treats end as exclusive; add one day so the latest candle is included.
    end_date   = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
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
        done, pending = concurrent.futures.wait(
            futures, timeout=30, return_when=concurrent.futures.ALL_COMPLETED
        )
        for future in pending:
            future.cancel()
        for future in done:
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
        tp3       = plan['tp3']

        # Zona beli: entry hanya valid di rentang pullback/near-close yang masih memberi R/R sehat.
        # Risiko dan alokasi dihitung dari buy_max, bukan last_close, agar rencana tidak terlalu optimistis.
        buy_min = snap_to_tick(last_close - 0.5 * ind['atr_val'], "ceil")
        buy_max = snap_to_tick(last_close, "floor")

        # Guard bertingkat
        buy_min = max(buy_min, snap_to_tick(stop_loss + 1, "ceil"))  # tidak boleh <= SL
        buy_max = max(buy_max, buy_min)                               # tidak boleh terbalik
        if buy_max >= tp1:                                            # tidak boleh >= TP1
            buy_max = snap_to_tick(tp1 - 1, "floor")
            buy_min = min(buy_min, buy_max)

        entry_ref = float(buy_max)
        loss_per_share = entry_ref - stop_loss
        if loss_per_share <= 0:
            skipped_reason[ticker] = "loss_per_share ≤ 0"
            continue

        rupiah_risk    = config['total_capital'] * (config['capital_risk_limit_pct'] / 100.0)
        calc_lots      = int(rupiah_risk / loss_per_share / 100)

        max_alloc      = config['total_capital'] * (config['max_capital_allocation_pct'] / 100.0)
        required_cap   = calc_lots * 100 * entry_ref
        if required_cap > max_alloc:
            calc_lots    = int(max_alloc / (100 * entry_ref))
            required_cap = calc_lots * 100 * entry_ref

        if calc_lots < 1:
            skipped_reason[ticker] = "modal tidak cukup untuk 1 lot"
            continue

        probs = estimate_trade_probabilities(
            score=total_score,
            grade=grade,
            live_price=entry_ref,
            buy_min=buy_min,
            buy_max=buy_max,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            atr_val=ind['atr_val'],
            ind=ind,
            vol_ctx=vol_ctx,
            tape=tape,
            bandar=bandar,
        )

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
            "Upside TP1":   f"+{round((tp1 - entry_ref) / entry_ref * 100, 1)}%",
            "TP2":          int(tp2),
            "Upside TP2":   f"+{round((tp2 - entry_ref) / entry_ref * 100, 1)}%",
            "TP3":          int(tp3),
            "Upside TP3":   f"+{round((tp3 - entry_ref) / entry_ref * 100, 1)}%",
            "Stop Loss":    int(stop_loss),
            "Risk%":        f"-{round((entry_ref - stop_loss) / entry_ref * 100, 1)}%",
            "R/R TP1":      f"1:{plan['rr1']}",
            "R/R TP2":      f"1:{plan['rr2']}",
            "R/R TP3":      f"1:{plan['rr3']}",
            "Prob Entry":   probs["Prob Entry"],
            "Prob TP1":     probs["Prob TP1"],
            "Prob TP2":     probs["Prob TP2"],
            "Prob TP3":     probs["Prob TP3"],
            "Prob SL":      probs["Prob SL"],
            "Confidence":   probs["Confidence"],
            "ATR":          round(ind['atr_val'], 1),
            "RSI":          round(ind['rsi_val'], 1),
            "CMF":          round(ind['cmf_val'], 3),
            "TS Kriteria":  plan['ts_rule'],
            "Partial Plan": plan['partial_plan'],
            "Lots":         int(calc_lots),
            "Alokasi (Rp)": required_cap,
            "_breakdown":   breakdown,
            "_vol_ctx":     vol_ctx,
            "_tape":        tape,
            "_bandar":      bandar,
            "_ind":         ind,
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
        # Guard: pastikan live price valid (tidak None, tidak NaN, tidak negatif)
        if lp and np.isfinite(float(lp)) and float(lp) > 0:
            r["Live Price"] = int(round(float(lp)))
            r["Live Src"]   = "live"
        else:
            r["Live Price"] = int(r["Last Price"])  # fallback ke harga terakhir data
            r["Live Src"]   = "delayed"

        # Recalculate probability with the actual live/delayed price.
        # Initial probabilities were based on planned entry; this keeps status,
        # Best Buy, and tables honest when price moves outside the buy zone.
        live_probs = estimate_trade_probabilities(
            score=r["Score"],
            grade=r["Grade"],
            live_price=float(r["Live Price"]),
            buy_min=float(r["Buy Min"]),
            buy_max=float(r["Buy Max"]),
            stop_loss=float(r["Stop Loss"]),
            tp1=float(r["TP1"]),
            tp2=float(r["TP2"]),
            tp3=float(r["TP3"]),
            atr_val=float(r["ATR"]),
            ind=r.get("_ind", {}),
            vol_ctx=r.get("_vol_ctx", {}),
            tape=r.get("_tape", {}),
            bandar=r.get("_bandar", {}),
        )
        r.update(live_probs)
        del r["_ticker_jk"]

    df_out = pd.DataFrame(results)

    # FIX: Sort utama berdasarkan validity status, baru score
    # expired card tidak boleh tampil di atas valid card meski score-nya tinggi
    def _validity_rank(row) -> int:
        lp = row.get("Live Price", row.get("Last Price", 0))
        sl = row.get("Stop Loss", 0)
        bmin = row.get("Buy Min", 0)
        if lp <= sl:          return 2   # expired → paling bawah
        elif lp < bmin:       return 1   # waiting below zone → tengah
        elif lp > row.get("Buy Max", 0): return 1   # chasing above zone → tengah
        else:                 return 0   # valid inside zone → paling atas

    df_out["_validity_rank"] = df_out.apply(_validity_rank, axis=1)
    return (
        df_out
        .sort_values(by=["_validity_rank", "Prob Entry", "Score"], ascending=[True, False, False])
        .drop(columns=["_validity_rank"])
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
        ref_close_fmt = f"{ref_close:,}".replace(",", ".")
        ref_note = (
            f'<span style="font-size:0.68rem;color:{ref_col};margin-left:0.3rem;">'
            f'{sign}{diff_pct:.1f}% vs ref {ref_close_fmt}'
            f'</span>'
        )

    live_price_fmt = f"{live_price:,}".replace(",", ".")

    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:0.4rem;padding:0.35rem 0.6rem;'
        f'background:rgba(255,255,255,0.04);border-radius:6px;'
        f'border-left:3px solid {color};">'
        f'  <div style="display:flex;align-items:baseline;gap:0.4rem;flex-wrap:wrap;">'
        f'    <span style="font-size:1.3rem;font-weight:800;color:{color};">'
        f'      {live_price_fmt}'
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
        if row["Live Price"] > row["Buy Max"]:
            total += 4; reasons.append("⏳ Di atas zona, tunggu pullback")
        else:
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
        if dom.get("style") == "distrib":
            # Distribusi = penalti; kurangi langsung (conf_pts tidak dipakai positif)
            total -= 5
            reasons.append("⚠️ Sinyal distribusi bandar terdeteksi")
        else:
            total += conf_pts
            reasons.append(f"🔍 Bandar: {dom.get('label','')} ({dom.get('conf','')})")
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


def clamp_prob(x: float, lo: float = 5.0, hi: float = 95.0) -> float:
    """Batasi probabilitas agar tetap realistis dan mudah dibaca."""
    try:
        return round(max(lo, min(hi, float(x))), 1)
    except Exception:
        return lo


def probability_label(prob: float) -> str:
    if prob >= 75:
        return "Tinggi"
    if prob >= 60:
        return "Sedang"
    if prob >= 45:
        return "Spekulatif"
    return "Rendah"


def estimate_trade_probabilities(
    score: float,
    grade: str,
    live_price: float,
    buy_min: float,
    buy_max: float,
    stop_loss: float,
    tp1: float,
    tp2: float,
    tp3: float,
    atr_val: float,
    ind: dict,
    vol_ctx: dict,
    tape: dict,
    bandar: dict,
) -> dict:
    """
    Estimasi probabilitas rule-based untuk membandingkan kualitas setup.
    Angka ini bukan kepastian prediktif; gunakan sebagai confidence relatif.
    """
    base = float(score) * 0.65
    grade_bonus = {"A": 8.0, "B": 4.0, "C": 0.0}.get(grade, 0.0)

    if stop_loss and live_price <= stop_loss:
        status_adj = -35.0
    elif buy_min <= live_price <= buy_max:
        status_adj = 12.0
    elif live_price < buy_min:
        status_adj = -4.0
    else:
        over_zone = (live_price - buy_max) / max(buy_max, 1.0)
        status_adj = -8.0 - min(over_zone * 80.0, 18.0)

    trend_adj = 0.0
    if ind.get("above_ema20"):
        trend_adj += 3.0
    if ind.get("above_ema50"):
        trend_adj += 4.0
    if ind.get("above_ema200"):
        trend_adj += 3.0
    if ind.get("ema20_rising"):
        trend_adj += 3.0

    momentum_adj = 0.0
    rsi = ind.get("rsi_val", 50.0)
    if 45 <= rsi <= 65:
        momentum_adj += 5.0
    elif 65 < rsi <= 75:
        momentum_adj -= 2.0
    elif rsi > 75:
        momentum_adj -= 8.0
    elif rsi < 35:
        momentum_adj -= 5.0

    cmf = ind.get("cmf_val", 0.0)
    if cmf > 0.05:
        momentum_adj += 4.0
    elif cmf < -0.05:
        momentum_adj -= 5.0

    volume_adj = 0.0
    if vol_ctx.get("valid"):
        vol_ratio = vol_ctx.get("vol_ratio", 0.0)
        candle_dir = vol_ctx.get("candle_dir")
        if candle_dir == "bullish" and vol_ratio >= 1.3:
            volume_adj += 6.0
        elif vol_ratio >= 1.5:
            volume_adj += 3.0
        elif candle_dir == "bearish" and vol_ratio >= 1.3:
            volume_adj -= 6.0

    tape_adj = 0.0
    for sig in tape.get("signals", []):
        if isinstance(sig, (tuple, list)) and len(sig) >= 2:
            if sig[1] == "accum":
                tape_adj += 5.0
            elif sig[1] == "distrib":
                tape_adj -= 6.0
            elif sig[1] == "warn":
                tape_adj -= 3.0

    bandar_adj = 0.0
    dom = bandar.get("dominant")
    if dom:
        conf_weight = {"high": 7.0, "med": 4.0, "low": 2.0}.get(dom.get("conf"), 2.0)
        if dom.get("style") == "accum":
            bandar_adj += conf_weight
        elif dom.get("style") == "distrib":
            bandar_adj -= conf_weight

    atr_pct = atr_val / max(live_price, 1.0)
    volatility_adj = 0.0
    if atr_pct > 0.08:
        volatility_adj -= 8.0
    elif atr_pct > 0.05:
        volatility_adj -= 4.0
    elif 0.015 <= atr_pct <= 0.04:
        volatility_adj += 3.0

    prob_entry = clamp_prob(
        base + grade_bonus + status_adj + trend_adj + momentum_adj
        + volume_adj + tape_adj + bandar_adj + volatility_adj
    )
    if live_price <= stop_loss:
        prob_entry = min(prob_entry, 15.0)

    risk_per_share = max(live_price - stop_loss, 1.0)
    rr1 = (tp1 - live_price) / risk_per_share
    rr2 = (tp2 - live_price) / risk_per_share
    rr3 = (tp3 - live_price) / risk_per_share

    rr_bonus_1 = min(max((rr1 - 1.2) * 6.0, -8.0), 10.0)
    rr_bonus_2 = min(max((rr2 - 2.0) * 4.0, -10.0), 8.0)
    rr_bonus_3 = min(max((rr3 - 3.0) * 3.0, -12.0), 6.0)

    prob_tp1 = clamp_prob(prob_entry + rr_bonus_1 - atr_pct * 35.0)
    prob_tp2 = clamp_prob(prob_entry - 12.0 + rr_bonus_2 - atr_pct * 45.0)
    prob_tp3 = clamp_prob(prob_entry - 24.0 + rr_bonus_3 - atr_pct * 55.0)
    prob_sl = 95.0 if live_price <= stop_loss else clamp_prob(100.0 - prob_tp1 + atr_pct * 45.0, 5.0, 90.0)

    return {
        "Prob Entry": prob_entry,
        "Prob TP1": prob_tp1,
        "Prob TP2": prob_tp2,
        "Prob TP3": prob_tp3,
        "Prob SL": prob_sl,
        "Confidence": probability_label(prob_entry),
    }


def pick_best_buy(df: pd.DataFrame) -> tuple[str | None, float, list[str]]:
    """Pilih satu ticker dengan composite best-buy score tertinggi."""
    if df.empty:
        return None, 0.0, []

    best_ticker, best_score, best_reasons = None, 0.0, []
    for _, row in df.iterrows():
        s, r = compute_best_buy_score(row)
        if r and s > best_score:
            best_score, best_reasons, best_ticker = s, r, row["Ticker"]

    if best_ticker is None or best_score <= 0:
        return None, 0.0, []
    return best_ticker, best_score, best_reasons


def render_best_buy_banner(ticker: str, score: float, reasons: list[str], row: pd.Series):
    """Tampilkan banner Best Buy di atas hasil scan."""
    validity = _check_signal_validity(
        row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"]
    )
    if validity['status'] == 'valid':
        status_label = "🟢 Harga dalam zona — siap entry"
    elif row["Live Price"] > row["Buy Max"]:
        status_label = "🟡 Di atas zona — tunggu pullback"
    else:
        status_label = "🟡 Di bawah zona — pantau & tunggu"
    status_color = "#3fb950" if validity['status'] == 'valid' else "#e3b341"

    # Confidence bar visual
    bar_w = min(int(score), 100)
    bar_c = "#ffd700" if score >= 70 else "#e3b341" if score >= 50 else "#8b949e"

    prob_html = ""
    if "Prob Entry" in row:
        prob_html = (
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.55rem;'
            f'background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:0.45rem 0.55rem;">'
            f'  <div><div class="label">Prob Entry</div><div style="color:#58a6ff;font-weight:900;">{row["Prob Entry"]}%</div></div>'
            f'  <div><div class="label">Prob TP1</div><div style="color:#3fb950;font-weight:900;">{row["Prob TP1"]}%</div></div>'
            f'  <div><div class="label">Prob SL</div><div style="color:#f85149;font-weight:900;">{row["Prob SL"]}%</div></div>'
            f'  <div><div class="label">Confidence</div><div style="color:#e3b341;font-weight:900;">{row["Confidence"]}</div></div>'
            f'</div>'
        )

    reasons_html = prob_html + "".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,0.06);'
        f'border-radius:6px;padding:0.1rem 0.4rem;margin:0.1rem;font-size:0.68rem;color:#c9d1d9;">'
        f'{r}</span>'
        for r in reasons
    )

    lp_fmt  = f"{int(row['Live Price']):,}".replace(",", ".")
    bmin_fmt = f"{int(row['Buy Min']):,}".replace(",", ".")
    bmax_fmt = f"{int(row['Buy Max']):,}".replace(",", ".")
    sl_fmt  = f"{int(row['Stop Loss']):,}".replace(",", ".")
    tp1_fmt = f"{int(row['TP1']):,}".replace(",", ".")

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
        f'  <div style="color:#fff;font-weight:700;">{lp_fmt}</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">ZONA BELI</div>'
        f'  <div style="color:#fff;font-weight:700;">{bmin_fmt}–{bmax_fmt}</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">STOP LOSS</div>'
        f'  <div style="color:#f85149;font-weight:700;">{sl_fmt}</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">TARGET TP1</div>'
        f'  <div style="color:#3fb950;font-weight:700;">{tp1_fmt} <span style="font-size:0.65rem;">{row["Upside TP1"]}</span></div></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _check_signal_validity(live_price: int, stop_loss: int, buy_min: int, buy_max: int) -> dict:
    """
    Tentukan status validitas sinyal berdasarkan harga live vs level kunci.

    Status:
    - 'valid'   : harga berada di dalam zona beli dan masih di atas SL → siap entry
    - 'waiting' : harga di bawah/di atas zona beli tapi masih di atas SL → tunggu
    - 'expired' : harga menembus SL dengan margin > 1.5% → sinyal tidak valid

    Buffer 1.5% diterapkan pada expired check untuk mengakomodasi noise
    antara data live (yfinance fast_info) vs data historical yang dipakai
    saat kalkulasi SL. Harga live bisa sedikit berbeda karena bid/ask spread
    atau slight delay, sehingga tidak langsung dinyatakan expired.
    """
    SL_BUFFER_PCT = 0.015  # 1.5% buffer sebelum dinyatakan expired

    expired_threshold = stop_loss * (1 - SL_BUFFER_PCT)

    if live_price <= expired_threshold:
        gap_pct = round((stop_loss - live_price) / stop_loss * 100, 1)
        sl_fmt   = f"{stop_loss:,}".replace(",", ".")
        lp_fmt   = f"{live_price:,}".replace(",", ".")
        return {
            'status':   'expired',
            'title':    '⚠️ Sinyal Tidak Valid — Harga Breakdown',
            'detail':   f'Harga ({lp_fmt}) sudah {gap_pct}% di bawah SL ({sl_fmt}). Jangan entry — sinyal dihitung saat kondisi berbeda.',
            'action':   'Tunggu konfirmasi reversal atau skip saham ini.',
            'card_cls': 'signal-expired',
            'banner_cls': 'expired-banner',
            'title_color': '#f85149',
        }
    elif live_price < buy_min:
        gap_pct  = round((buy_min - live_price) / buy_min * 100, 1)
        bmin_fmt = f"{buy_min:,}".replace(",", ".")
        bmax_fmt = f"{buy_max:,}".replace(",", ".")
        lp_fmt   = f"{live_price:,}".replace(",", ".")
        return {
            'status':   'waiting',
            'title':    '⏳ Harga di Bawah Zona Beli',
            'detail':   f'Harga ({lp_fmt}) masih {gap_pct}% di bawah zona ({bmin_fmt}–{bmax_fmt}). SL masih aman — pantau, jangan entry dulu.',
            'action':   'Entry hanya jika harga masuk zona beli.',
            'card_cls': 'signal-waiting',
            'banner_cls': 'waiting-banner',
            'title_color': '#e3b341',
        }
    elif live_price > buy_max:
        gap_pct  = round((live_price - buy_max) / buy_max * 100, 1)
        bmin_fmt = f"{buy_min:,}".replace(",", ".")
        bmax_fmt = f"{buy_max:,}".replace(",", ".")
        lp_fmt   = f"{live_price:,}".replace(",", ".")
        return {
            'status':   'waiting',
            'title':    '⏳ Harga di Atas Zona Beli',
            'detail':   f'Harga ({lp_fmt}) sudah {gap_pct}% di atas zona ({bmin_fmt}–{bmax_fmt}). R/R memburuk jika dipaksakan entry sekarang.',
            'action':   'Tunggu pullback ke zona beli atau cari setup lain.',
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
                    + pill_from_bd("adx",   "ADX")
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
                    f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.4rem;'
                    f'margin-bottom:0.6rem;border-top:1px solid #30363d;padding-top:0.4rem;">'
                    f'  <div><div class="label">TP 1 <span class="rr-badge">({row["R/R TP1"]})</span></div>'
                    f'  <div class="tp">{int(row["TP1"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP1"]}</span></div></div>'
                    f'  <div><div class="label">TP 2 <span class="rr-badge">({row["R/R TP2"]})</span></div>'
                    f'  <div class="tp">{int(row["TP2"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP2"]}</span></div></div>'
                    f'  <div><div class="label">TP 3 <span class="rr-badge">({row["R/R TP3"]})</span></div>'
                    f'  <div class="tp" style="color:#bc8cff;">{int(row["TP3"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP3"]}</span></div></div>'
                    f'</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.4rem;">'
                    f'  <div><div class="label">Stop Loss</div>'
                    f'  <div class="sl">{int(row["Stop Loss"])} <span style="font-size:0.68rem;opacity:0.8">{row["Risk%"]}</span></div></div>'
                    f'  <div><div class="label">Trailing Strategy</div>'
                    f'  <div class="ts-rule" style="font-size:0.78rem;">{row["TS Kriteria"]}</div></div>'
                    f'</div>'
                    f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.35rem;margin-bottom:0.5rem;'
                    f'background:rgba(88,166,255,0.05);border:1px solid rgba(88,166,255,0.18);border-radius:6px;padding:0.45rem 0.5rem;">'
                    f'  <div><div class="label">Prob Entry</div><div style="color:#58a6ff;font-weight:800;">{row["Prob Entry"]}%</div></div>'
                    f'  <div><div class="label">Prob TP1</div><div style="color:#3fb950;font-weight:800;">{row["Prob TP1"]}%</div></div>'
                    f'  <div><div class="label">Prob SL</div><div style="color:#f85149;font-weight:800;">{row["Prob SL"]}%</div></div>'
                    f'  <div><div class="label">TP2</div><div style="color:#3fb950;font-weight:700;">{row["Prob TP2"]}%</div></div>'
                    f'  <div><div class="label">TP3</div><div style="color:#bc8cff;font-weight:700;">{row["Prob TP3"]}%</div></div>'
                    f'  <div><div class="label">Confidence</div><div style="color:#e3b341;font-weight:800;">{row["Confidence"]}</div></div>'
                    f'</div>'
                    f'<div style="margin-bottom:0.4rem;background:rgba(255,255,255,0.02);border-radius:6px;padding:0.3rem 0.5rem;border:1px solid #21262d;">'
                    f'  <div class="label" style="margin-bottom:0.15rem;">Rencana Partial Exit</div>'
                    f'  <div style="font-size:0.68rem;color:#c9d1d9;">{row["Partial Plan"]}</div>'
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
            s = sigs[0]
            # tape signal adalah tuple: (key, style, label, short, conf_pct)
            # index [2] = label — akses dengan guard panjang
            return s[2] if isinstance(s, (tuple, list)) and len(s) > 2 else str(s)

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
                "Target 3":    f"Rp {int(row['TP3']):,} ({row['Upside TP3']})".replace(",", "."),
                "Stop Loss":   f"Rp {int(row['Stop Loss']):,} ({row['Risk%']})".replace(",", "."),
                "R/R":         row["R/R TP1"],
                "Score":       row["Score"],
                "Grade":       row["Grade"],
                "Prob Entry":  f"{row['Prob Entry']}%",
                "Prob TP1":    f"{row['Prob TP1']}%",
                "Prob TP2":    f"{row['Prob TP2']}%",
                "Prob TP3":    f"{row['Prob TP3']}%",
                "Prob SL":     f"{row['Prob SL']}%",
                "Confidence":  row["Confidence"],
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
