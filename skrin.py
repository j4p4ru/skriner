import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
import json
import requests
import concurrent.futures
from datetime import datetime, timedelta

# =============================================================================
# 1. KONFIGURASI HALAMAN & CSS
# =============================================================================
st.set_page_config(
    page_title="Quant Trader - IDX Screener AI (Gemini) v9.1",
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
    .ind-pill { display:inline-block; font-size:0.7rem; font-weight:600; padding:0.1rem 0.45rem; border-radius:10px; margin:0.1rem; }
    .ind-bull { background:rgba(63,185,80,.15);  color:#3fb950; border:1px solid rgba(63,185,80,.3); }
    .ind-bear { background:rgba(248,81,73,.15);  color:#f85149; border:1px solid rgba(248,81,73,.3); }
    .ind-neut { background:rgba(139,148,158,.12);color:#8b949e; border:1px solid rgba(139,148,158,.3);}
    .rr-badge  { font-size:0.75rem; font-weight:700; color:#d2a8ff; }
    
    .vol-ctx { background:rgba(255,255,255,0.03); border-radius:6px; padding:0.4rem 0.6rem; margin-bottom:0.5rem; border:1px solid #21262d; }
    .vol-bar-track { background:#21262d; border-radius:4px; height:5px; width:100%; margin-top:0.25rem; }
    .vol-bar-fill  { height:5px; border-radius:4px; transition:width 0.3s; }

    .section-divider { border-top:1px solid #21262d; margin:0.5rem 0 0.4rem; }
    .tape-pill { display:inline-block; font-size:0.65rem; font-weight:700; padding:0.12rem 0.4rem; border-radius:8px; margin:0.08rem 0.06rem; }
    .tape-accum   { background:rgba(63,185,80,.18);  color:#3fb950; border:1px solid rgba(63,185,80,.35); }
    .tape-distrib { background:rgba(248,81,73,.18);  color:#f85149; border:1px solid rgba(248,81,73,.35); }
    .tape-neutral { background:rgba(139,148,158,.12);color:#8b949e; border:1px solid rgba(139,148,158,.3);}
    .tape-warn    { background:rgba(219,109,40,.18); color:#db6d28; border:1px solid rgba(219,109,40,.35);}
    .tape-purple  { background:rgba(188,140,255,.15);color:#bc8cff; border:1px solid rgba(188,140,255,.3);}

    .conf-hi  { color:#3fb950; font-weight:800; font-size:0.65rem; }
    .conf-med { color:#e3b341; font-weight:800; font-size:0.65rem; }
    .conf-lo  { color:#8b949e; font-weight:700; font-size:0.65rem; }

    .narasi-tech  { font-size:0.72rem; color:#c9d1d9; font-style:italic; line-height:1.35; }
    .narasi-plain { font-size:0.7rem;  color:#8b949e; line-height:1.3; margin-top:0.15rem; }
    
    .signal-expired { border-color: #f85149 !important; background: rgba(248,81,73,0.04) !important; }
    .signal-waiting { border-color: #e3b341 !important; background: rgba(227,179,65,0.04) !important; }
    .expired-banner { background: rgba(248,81,73,0.12); border:1px solid rgba(248,81,73,0.4); border-radius:6px; padding:0.5rem 0.7rem; margin-bottom:0.5rem; text-align:center; }
    .waiting-banner { background: rgba(227,179,65,0.1); border:1px solid rgba(227,179,65,0.35); border-radius:6px; padding:0.5rem 0.7rem; margin-bottom:0.5rem; text-align:center; }
    .dimmed { opacity: 0.35; pointer-events:none; user-select:none; filter:grayscale(60%); }
    
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
    .adx-info {
        display:inline-block; font-size:0.66rem; font-weight:700;
        padding:0.08rem 0.4rem; border-radius:6px; margin-left:0.3rem;
        background:rgba(188,140,255,0.12); color:#bc8cff; border:1px solid rgba(188,140,255,0.3);
    }
    .watchlist-banner {
        background:linear-gradient(135deg,rgba(88,166,255,0.10),rgba(88,166,255,0.04));
        border:1px solid rgba(88,166,255,0.3); border-radius:8px;
        padding:0.7rem 1rem; margin-bottom:1.2rem;
    }
    .ai-box {
        background: linear-gradient(135deg, rgba(66, 133, 244, 0.08) 0%, #161b22 60%);
        border: 1px solid rgba(66, 133, 244, 0.4); border-radius: 8px;
        padding: 1.2rem; margin-top: 1rem; color: #e6edf3;
    }
    .ai-header { font-size: 1.1rem; font-weight: 800; color: #4285F4; margin-bottom: 0.5rem; border-bottom: 1px solid rgba(66, 133, 244, 0.3); padding-bottom: 0.5rem; }
    .ai-content { font-size: 0.88rem; line-height: 1.6; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. SESSION STATE
# =============================================================================
for key, default in [('raw_market_data', {}), ('last_loaded_mode', None), ('scan_meta', {})]:
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================================
# 3. HELPER & PARSER
# =============================================================================
def fmt_idr(val):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)): return "Rp 0"
        return f"Rp {int(val):,}".replace(",", ".")
    except: return "Rp 0"

def fmt_num(val) -> str:
    try: return f"{int(round(float(val))):,}".replace(",", ".")
    except: return "0"

def parse_tickers_from_df(df: pd.DataFrame) -> list:
    ticker_col = None
    for col in df.columns:
        if col.strip().lower() in ("ticker", "kode", "symbol", "emiten", "code"):
            ticker_col = col
            break
    if ticker_col is None: ticker_col = df.columns[0]
    tickers = df[ticker_col].dropna().astype(str).str.strip().tolist()
    return [t.upper() if t.upper().endswith(".JK") else f"{t.upper()}.JK" for t in tickers if t.strip() and t.strip().lower() not in ("nan", "none", "")]

@st.cache_data(show_spinner=False)
def load_local_emiten_csv():
    try: base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError: base_dir = os.getcwd()
    local_csv = os.path.join(base_dir, "emiten.csv")
    if os.path.exists(local_csv):
        try: return parse_tickers_from_df(pd.read_csv(local_csv))
        except: return []
    return []

def tickers_from_text(text: str) -> list:
    parts = re.split(r"[,\s\n]+", text.strip())
    return [t.upper() if t.upper().endswith(".JK") else f"{t.upper()}.JK" for t in parts if t.strip()]

# =============================================================================
# 4. INDIKATOR TEKNIKAL
# =============================================================================
def calculate_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df['Close'].shift(1)
    tr = pd.concat([df['High'] - df['Low'], (df['High'] - prev_close).abs(), (df['Low']  - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/window, adjust=False).mean()

def calculate_cmf(df: pd.DataFrame, window: int = 20) -> pd.Series:
    if len(df) < window: return pd.Series(0.0, index=df.index)
    hl_safe = (df['High'] - df['Low']).replace(0, np.nan)
    mfm = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / hl_safe
    mfv = mfm.fillna(0.0) * df['Volume']
    vol_sum = df['Volume'].rolling(window).sum().replace(0, np.nan)
    return (mfv.rolling(window).sum() / vol_sum).fillna(0.0)

def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.Series:
    delta = df['Close'].diff()
    gain, loss = delta.clip(lower=0), (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rsi = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, 1e-10)))
    return rsi.fillna(50.0)

def calculate_bb_squeeze(df: pd.DataFrame, bb_window: int = 20, bb_std: float = 2.0, kc_mult: float = 1.5, atr_window: int = 14) -> pd.Series:
    if len(df) < bb_window: return pd.Series(False, index=df.index)
    basis, bb_std_ = df['Close'].rolling(bb_window).mean(), df['Close'].rolling(bb_window).std(ddof=1)
    bb_upper, bb_lower = basis + bb_std * bb_std_, basis - bb_std * bb_std_
    atr = calculate_atr(df, window=atr_window)
    kc_upper, kc_lower = basis + kc_mult * atr, basis - kc_mult * atr
    return ((bb_upper < kc_upper) & (bb_lower > kc_lower)).fillna(False)

def calculate_adx(df: pd.DataFrame, window: int = 14) -> dict:
    if len(df) < window + 2: return {'adx': 0.0, 'di_plus': 0.0, 'di_minus': 0.0, 'bullish_dir': False, 'strength': 'weak'}
    high, low, close = df['High'].values, df['Low'].values, df['Close'].values
    prev_close = np.roll(close, 1); prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    up_move, down_move = high - np.roll(high, 1), np.roll(low, 1) - low
    up_move[0], down_move[0] = 0.0, 0.0
    dm_plus, dm_minus = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    alpha = 1.0 / window
    atr_w = pd.Series(tr).ewm(alpha=alpha, adjust=False).mean().values
    dmp_w = pd.Series(dm_plus).ewm(alpha=alpha, adjust=False).mean().values
    dmm_w = pd.Series(dm_minus).ewm(alpha=alpha, adjust=False).mean().values
    safe_atr = np.maximum(atr_w, 1e-9)
    di_plus, di_minus = 100.0 * dmp_w / safe_atr, 100.0 * dmm_w / safe_atr
    safe_di_sum = np.maximum(di_plus + di_minus, 1e-9)
    dx = 100.0 * np.abs(di_plus - di_minus) / safe_di_sum
    adx_s = pd.Series(dx).ewm(alpha=alpha, adjust=False).mean().values
    adx_val, dip_val, dim_val = float(adx_s[-1]), float(di_plus[-1]), float(di_minus[-1])
    strength = 'strong' if adx_val >= 25 else ('moderate' if adx_val >= 18 else 'weak')
    return {'adx': round(adx_val, 1), 'di_plus': round(dip_val, 1), 'di_minus': round(dim_val, 1), 'bullish_dir': dip_val > dim_val, 'strength': strength}

def calculate_indicators(df: pd.DataFrame) -> dict:
    close, volume = df['Close'], df['Volume']
    ema200, ema50, ema20 = close.ewm(span=200, adjust=False).mean(), close.ewm(span=50, adjust=False).mean(), close.ewm(span=20, adjust=False).mean()
    last_close = float(close.iloc[-1])
    ema200_available = len(close) >= 200
    atr_series, cmf_series, rsi_series, sq_series, adx_data = calculate_atr(df), calculate_cmf(df), calculate_rsi(df), calculate_bb_squeeze(df), calculate_adx(df)
    atr_val = float(atr_series.iloc[-1])
    return {
        'last_close': last_close, 'ema200_available': ema200_available,
        'above_ema200': last_close > float(ema200.iloc[-1]) if ema200_available else False,
        'above_ema50': last_close > float(ema50.iloc[-1]), 'above_ema20': last_close > float(ema20.iloc[-1]),
        'ema20_rising': float(ema20.iloc[-1]) > float(ema20.iloc[-3]) if len(ema20) >= 3 else False,
        'atr_val': atr_val, 'atr_pct': atr_val / last_close if last_close > 0 else 0.0,
        'cmf_val': float(cmf_series.iloc[-1]), 'cmf_rising': float(cmf_series.iloc[-1]) > float(cmf_series.iloc[-2]) if len(cmf_series) > 1 else False,
        'rsi_val': float(rsi_series.iloc[-1]), 'rsi_rising': float(rsi_series.iloc[-1]) > float(rsi_series.iloc[-2]) if len(rsi_series) > 1 else False,
        'in_squeeze': bool(sq_series.iloc[-1]), 'squeeze_release': (not bool(sq_series.iloc[-1])) and bool(sq_series.iloc[-2]) if len(sq_series) > 1 else False,
        'adx_val': adx_data['adx'], 'adx_di_plus': adx_data['di_plus'], 'adx_di_minus': adx_data['di_minus'],
        'adx_bullish_dir': adx_data['bullish_dir'], 'adx_strength': adx_data['strength'],
        'vol_spike': float(volume.iloc[-1]) / max(float(volume.rolling(15).mean().iloc[-1]), 1.0),
        'adtv': float(volume.rolling(20).mean().iloc[-1]) * last_close,
    }

# =============================================================================
# 4a. FILTER KUALITAS DATA
# =============================================================================
def is_tradeable_stock(df: pd.DataFrame, last_close: float, interval: str) -> tuple[bool, str]:
    if len(df) < 10: return False, "data terlalu pendek"
    if (df['Volume'].tail(3) <= 0).all(): return False, "volume 0 di 3 candle terakhir"
    if df['Close'].tail(5).nunique() == 1: return False, "harga stagnan 5 candle terakhir"
    try:
        last_date = df.index[-1]
        if hasattr(last_date, 'to_pydatetime'): last_date = last_date.to_pydatetime()
        if getattr(last_date, 'tzinfo', None) is not None: last_date = last_date.replace(tzinfo=None)
        days_stale = (datetime.now() - last_date).days
        if interval == "60m":
            if days_stale > 3: return False, f"data basi ({days_stale} hari)"
        else:
            if days_stale > 10: return False, f"data basi ({days_stale} hari)"
    except: pass
    if ((df['High'].tail(10) - df['Low'].tail(10)) <= 0).sum() >= 7: return False, "OHLC tidak wajar"
    if not np.isfinite(last_close) or last_close <= 0: return False, "harga tidak valid"
    return True, ""

# =============================================================================
# 4b. VOLUME & TAPE READING
# =============================================================================
def analyse_volume_context(df: pd.DataFrame) -> dict:
    if len(df) < 5: return {'valid': False}
    row = df.iloc[-1]
    o, h, l, c, vol = float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']), float(row['Volume'])
    rng = h - l if h > l else 1e-9
    return {'valid': True, 'candle_dir': "doji" if abs(c-o)/rng < 0.15 else ("bullish" if c>=o else "bearish"), 'body_pct': round(abs(c-o)/rng, 3), 'close_pos': round((c-l)/rng, 3), 'vol_ratio': round(vol / max(float(df['Volume'].rolling(20).mean().iloc[-1]), 1.0), 2)}

def analyse_tape(df: pd.DataFrame, atr_val: float) -> dict:
    if len(df) < 10: return {'signals': [], 'dominant': None}
    tail = df.tail(5)
    vol5, hi5, lo5, op5, cl5 = tail['Volume'].values, tail['High'].values, tail['Low'].values, tail['Open'].values, tail['Close'].values
    vol_ma = float(df['Volume'].rolling(20).mean().iloc[-1])
    ranges5, avg_range5 = hi5 - lo5, float(np.mean(hi5 - lo5)) if np.mean(hi5 - lo5) > 0 else 1e-9
    signals = []
    last_vol_ratio, last_range = vol5[-1] / max(vol_ma, 1.0), ranges5[-1]
    last_body, last_close_pos = abs(cl5[-1] - op5[-1]), (cl5[-1] - lo5[-1]) / max(last_range, 1e-9)
    if last_vol_ratio > 2.5 and last_body/max(last_range, 1e-9) > 0.6 and cl5[-1] > op5[-1] and last_close_pos > 0.7: signals.append(('buying_climax', 'distrib', 'Buying Climax', 'BC', min(int(last_vol_ratio/3.0*100), 90)))
    if last_vol_ratio > 2.5 and last_body/max(last_range, 1e-9) > 0.6 and cl5[-1] < op5[-1] and last_close_pos < 0.3: signals.append(('selling_climax', 'accum', 'Selling Climax', 'SC', min(int(last_vol_ratio/3.0*100), 90)))
    if last_vol_ratio > 1.8 and last_close_pos > 0.55 and abs(cl5[-1]-cl5[-2])/max(atr_val, 1e-9) < 0.5: signals.append(('absorption', 'accum', 'Absorption', 'ABS', min(int(last_close_pos*last_vol_ratio/2.5*100), 85)))
    if last_vol_ratio > 1.8 and last_range < avg_range5 * 0.6: signals.append(('exhaustion', 'warn', 'Exhaustion', 'EXH', min(int((avg_range5/max(last_range, 1e-9))*20), 80)))
    if all(v < vol_ma * 0.8 for v in vol5) and (max(cl5)-min(cl5))/max(atr_val, 1e-9) < 1.5: signals.append(('accum_quiet', 'accum', 'Akumulasi Senyap', 'AQ', 72))
    return {'signals': signals, 'dominant': signals[0] if signals else None}

def analyse_bandarmology(df: pd.DataFrame, atr_val: float) -> dict:
    if len(df) < 20: return {'signals': [], 'dominant': None, 'narasi_tech': '', 'narasi_plain': ''}
    vol_ma = float(df['Volume'].rolling(20).mean().iloc[-1])
    close, high_arr, low_arr, open_arr, vol_arr = df['Close'].values, df['High'].values, df['Low'].values, df['Open'].values, df['Volume'].values
    n, last = len(df), len(df) - 1
    def _cp(i): return (close[i] - low_arr[i]) / max(high_arr[i] - low_arr[i], 1e-9)
    def _vr(i): return vol_arr[i] / max(vol_ma, 1.0)
    def _clbl(p): return 'high' if p>=75 else ('med' if p>=50 else 'low')
    signals = []
    for i in range(max(0, n-3), n):
        if close[i] < close[i-1] and _cp(i) > 0.55 and _vr(i) > 1.4:
            conf = int(min((_cp(i)-0.55)/0.45*50 + (_vr(i)-1.4)/1.6*50, 95)); signals.append({'key':'accum_signal','style':'accum','label':'Akumulasi','short':'ACCU','conf_pct':conf,'conf':_clbl(conf),'candle_idx':i}); break
    for i in range(max(0, n-3), n):
        if close[i] > close[i-1] and _cp(i) < 0.45 and _vr(i) > 1.8:
            conf = int(min((1-_cp(i)-0.55)/0.45*50 + (_vr(i)-1.8)/2.2*50, 95)); signals.append({'key':'distrib_signal','style':'distrib','label':'Distribusi','short':'DIST','conf_pct':conf,'conf':_clbl(conf),'candle_idx':i}); break
    if np.mean(vol_arr[-5:]) > vol_ma * 1.05 and np.mean(vol_arr[-5:]) < vol_ma * 1.5 and (max(close[-5:])-min(close[-5:]))/max(atr_val, 1e-9) < 1.2: signals.append({'key':'stealth_accum','style':'accum','label':'Akum. Senyap','short':'STL','conf_pct':68,'conf':'med','candle_idx':last})
    if n >= 7 and open_arr[last] > close[-2]*1.005 and _vr(last) > 2.0 and (max(close[-7:-2])-min(close[-7:-2]))/max(atr_val, 1e-9) < 2.0: signals.append({'key':'markup','style':'purple','label':'Markup Phase','short':'MRK','conf_pct':int(min(60+(_vr(last)-2.0)/3.0*35, 95)),'conf':'high','candle_idx':last})
    if n >= 3 and close[-2] < close[-3] and (close[-1]-close[-2]) > abs(close[-2]-close[-3])*0.6 and _vr(last-1) > 1.5: signals.append({'key':'shakeout','style':'warn','label':'Shakeout','short':'SKO','conf_pct':int(min(55+abs(close[-2]-close[-3])/max(atr_val, 1e-9)*8, 88)),'conf':'med','candle_idx':last})
    signals.sort(key=lambda x: x['conf_pct'], reverse=True)
    dominant = signals[0] if signals else None
    n_map = {
        'accum_signal': ("Candle turun close di upper-half vol di atas rata — penyerapan.", "Harga turun tapi ada yang beli kuat. Bandar akumulasi."),
        'distrib_signal': ("Candle naik close di lower-half vol spike — distribusi institusional.", "Harga naik tapi bandar buang saham. Hati-hati jebakan."),
        'stealth_accum': ("Vol 5 candle sedikit di atas normal, harga sideways — akumulasi bertahap.", "Diam-diam dibeli. Tanda akan ada pergerakan besar."),
        'markup': ("Gap-up + volume tinggi setelah sideways — markup phase.", "Bandar dorong harga setelah akumulasi. Sinyal awal naik."),
        'shakeout': ("Drop tajam 1 candle dilitani recovery kuat — shakeout.", "Kemarin turun tajam balik hari ini. Bandar buang holder lemah."),
    }
    narasi_tech, narasi_plain = ("Tidak ada sinyal signifikan.", "Belum ada pola cukup kuat.") if not dominant else n_map.get(dominant['key'], ("Sinyal tidak dikenali.", "Pola belum terdefinisi."))
    return {'signals': signals, 'dominant': dominant, 'narasi_tech': narasi_tech, 'narasi_plain': narasi_plain}

# =============================================================================
# 5. SCORING ENGINE
# =============================================================================
def score_trend(ind): 
    if ind['above_ema50'] and ind['above_ema20']: return min(16.0 + (2.0 if ind.get('ema200_available') and ind['above_ema200'] else 0.0) + (2.0 if ind.get('ema20_rising') else 0.0), 20.0), "bull"
    elif ind['above_ema50']: return 10.0, "bull"
    elif ind['above_ema20']: return 4.0, "neut"
    return 0.0, "bear"

def score_rsi(ind):
    rsi = ind['rsi_val']
    if rsi > 75: return 2.0, "bear"
    if 40 <= rsi <= 65: return min(12.0 + (rsi-40)/25.0*3.0 + (3.0 if ind['rsi_rising'] else 0.0), 18.0), "bull"
    if 65 < rsi <= 75: return 9.0, "neut"
    if 30 <= rsi < 40: return 7.0, "neut"
    return 3.0, "bear"

def score_cmf(ind):
    cmf = ind['cmf_val']
    if cmf > 0: return min(20.0 * min(cmf/0.25, 1.0) + (1.5 if ind['cmf_rising'] else 0.0), 20.0), "bull"
    if cmf > -0.05: return 4.0, "neut"
    return 0.0, "bear"

def score_volume(ind):
    s = ind['vol_spike']
    if s >= 2.5: return 12.0, "bull"
    if s >= 1.5: return min(6.0 + 6.0*((s-1.5)/1.0), 12.0), "bull"
    if s >= 1.2: return 4.0, "neut"
    return 0.0, "neut"

def score_squeeze(ind):
    if ind['squeeze_release']: return 10.0, "bull"
    if ind['in_squeeze']: return 6.0, "neut"
    return 2.0, "neut"

def score_adx(ind):
    stg, bull = ind.get('adx_strength', 'weak'), ind.get('adx_bullish_dir', False)
    if stg == 'strong': base = 20.0 if bull else 4.0
    elif stg == 'moderate': base = 13.0 if bull else 7.0
    else: base = 8.0
    return base, "bull" if (bull and stg != 'weak') else ("bear" if stg == 'strong' else "neut")

def compute_total_score(ind):
    sc = {k: f(ind) for k, f in [('trend', score_trend), ('rsi', score_rsi), ('cmf', score_cmf), ('volume', score_volume), ('squeeze', score_squeeze), ('adx', score_adx)]}
    total = sum(v[0] for v in sc.values())
    if not ind['above_ema50'] and not ind['above_ema20']: total = min(total, 40.0)
    if ind.get('ema200_available') and not ind.get('above_ema200') and not ind['above_ema50']: total = min(total, 35.0)
    return round(total, 1), {k: (round(v[0],1), v[1]) for k, v in sc.items()}

# =============================================================================
# 6. TRADING PLAN
# =============================================================================
INTRADAY_PARAMS = {'atr_sl_mult': 1.5, 'min_rr1': 1.5, 'min_rr2': 2.5, 'min_rr3': 4.0, 'ts_rule': "Trailing 1× ATR; geser ke BEP saat TP1 hit", 'fixed_risk_pct': 3.0, 'buy_zone_atr_mult': 0.35}
SWING_PARAMS = {'atr_sl_mult': 2.0, 'min_rr1': 2.0, 'min_rr2': 3.5, 'min_rr3': 5.5, 'ts_rule': "Set BEP saat TP1 hit; trailing 2× ATR menuju TP2", 'fixed_risk_pct': 5.0, 'buy_zone_atr_mult': 0.5}

def snap_to_tick(price, direction="floor"):
    p = float(price)
    tick = 1 if p < 200 else 2 if p < 500 else 5 if p < 2000 else 10 if p < 5000 else 25
    return int(np.ceil(p/tick)*tick) if direction == "ceil" else int(np.floor(p/tick)*tick)

def build_trade_plan(last_close, atr_val, atr_pct, params):
    if atr_pct > 0.06: atr_adj = 0.8
    elif atr_pct < 0.02: atr_adj = 1.2
    else: atr_adj = 1.0
    sl_mult = params['atr_sl_mult'] * atr_adj
    buy_atr_mult = params['buy_zone_atr_mult'] * atr_adj
    buy_max_raw = last_close + (0.1 * atr_val)
    buy_min_raw = last_close - (buy_atr_mult * atr_val)
    buy_max = snap_to_tick(buy_max_raw, "ceil")
    buy_min = snap_to_tick(buy_min_raw, "floor")
    entry_ref = (buy_max + buy_min) / 2.0
    sl_dist = max(atr_val * sl_mult, entry_ref * (params['fixed_risk_pct']/100.0)*0.5)
    stop_loss = snap_to_tick(entry_ref - sl_dist, "floor") if entry_ref - sl_dist > 0 else snap_to_tick(entry_ref*0.95, "floor")
    sl_dist_actual = max(entry_ref - stop_loss, sl_dist)
    tp1 = snap_to_tick(entry_ref + sl_dist_actual * params['min_rr1'], "ceil")
    tp2 = snap_to_tick(entry_ref + sl_dist_actual * params['min_rr2'], "ceil")
    tp3 = snap_to_tick(entry_ref + sl_dist_actual * params['min_rr3'], "ceil")
    tick = 25 if last_close >= 5000 else 10 if last_close >= 2000 else 5 if last_close >= 500 else 2 if last_close >= 200 else 1
    if buy_min <= stop_loss:
        buy_min = stop_loss + tick
        entry_ref = (buy_max + buy_min) / 2.0
    if buy_max < buy_min:
        buy_max = buy_min
        entry_ref = (buy_max + buy_min) / 2.0
    if buy_max >= tp1:
        buy_max = snap_to_tick(tp1 - tick, "floor")
        entry_ref = (buy_max + buy_min) / 2.0
    return {
        'stop_loss': float(stop_loss), 'tp1': float(tp1), 'tp2': float(tp2), 'tp3': float(tp3), 
        'buy_min': float(buy_min), 'buy_max': float(buy_max), 'entry_ref': float(entry_ref),
        'sl_dist': sl_dist_actual, 
        'rr1': round((tp1-entry_ref)/sl_dist_actual, 2), 
        'rr2': round((tp2-entry_ref)/sl_dist_actual, 2), 
        'rr3': round((tp3-entry_ref)/sl_dist_actual, 2), 
        'ts_rule': params['ts_rule'], 
        'partial_plan': "TP1: exit 40% → geser SL ke BEP | TP2: exit 40% | TP3/Trail: sisa 20%", 
        'atr_adj': atr_adj
    }

def get_dynamic_risk(base_risk, grade, confidence):
    g_scale = {'A': 1.0, 'B': 0.75, 'C': 0.5}.get(grade, 0.5)
    c_scale = {'Tinggi': 1.0, 'Sedang': 0.8, 'Spekulatif': 0.6, 'Rendah': 0.4}.get(confidence, 0.5)
    return max(0.25, base_risk * g_scale * c_scale)

# =============================================================================
# 7. DOWNLOAD ENGINE
# =============================================================================
def download_ticker_chunk(tickers, period_days, interval):
    start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    res = {}
    try:
        data = yf.download(" ".join(tickers), start=start_date, end=end_date, interval=interval, group_by='ticker', auto_adjust=True, progress=False, threads=True, timeout=30)
        if data.empty: raise ValueError("Empty")
        is_multi = isinstance(data.columns, pd.MultiIndex)
        if len(tickers) == 1:
            if not is_multi and 'Close' in data.columns:
                df_c = data.dropna(subset=['Close'])
                if not df_c.empty: res[tickers[0]] = df_c
            elif is_multi:
                df_t = data[tickers[0]].dropna(subset=['Close']) if tickers[0] in data else None
                if df_t is not None and not df_t.empty: res[tickers[0]] = df_t
        else:
            if not is_multi: raise ValueError("Multi-ticker failed")
            for t in tickers:
                if t in data.columns.get_level_values(0):
                    df_t = data[t].dropna(subset=['Close'])
                    if not df_t.empty: res[t] = df_t
    except Exception:
        for t in tickers:
            try:
                df_s = yf.download(t, start=start_date, end=end_date, interval=interval, auto_adjust=True, progress=False, timeout=15)
                df_c = df_s.dropna(subset=['Close']) if not df_s.empty and 'Close' in df_s.columns else None
                if df_c is not None and not df_c.empty: res[t] = df_c
            except: continue
    return res

def _fetch_one_live(ticker):
    try:
        info = yf.Ticker(ticker).fast_info
        p = info.get('last_price') or info.get('lastPrice') or info.get('regularMarketPrice')
        if p and float(p) > 0: return ticker, float(p)
    except: pass
    return ticker, None

def fetch_live_prices(tickers_jk, max_workers=8):
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_one_live, t): t for t in tickers_jk}
        done, _ = concurrent.futures.wait(futs, timeout=30, return_when=concurrent.futures.ALL_COMPLETED)
        for f in done:
            try:
                t, p = f.result()
                if p: res[t] = p
            except: pass
    return res

# =============================================================================
# 8. PROBABILITY & VALIDITY
# =============================================================================
def _check_signal_validity(lp, sl, bmin, bmax):
    if lp <= sl * (1 - 0.015): return {'status':'expired','title':'⚠️ Sinyal Tidak Valid','detail':f'Harga ({fmt_num(lp)}) breakdown SL ({fmt_num(sl)}).','action':'Skip saham ini.','card_cls':'signal-expired','banner_cls':'expired-banner','title_color':'#f85149'}
    if lp < bmin: return {'status':'waiting','title':'⏳ Harga di Bawah Zona','detail':f'Harga ({fmt_num(lp)}) di bawah zona ({fmt_num(bmin)}–{fmt_num(bmax)}).','action':'Pantau, jangan entry dulu.','card_cls':'signal-waiting','banner_cls':'waiting-banner','title_color':'#e3b341'}
    if lp > bmax: return {'status':'waiting','title':'⏳ Harga di Atas Zona','detail':f'Harga ({fmt_num(lp)}) di atas zona ({fmt_num(bmin)}–{fmt_num(bmax)}).','action':'Tunggu pullback.','card_cls':'signal-waiting','banner_cls':'waiting-banner','title_color':'#e3b341'}
    return {'status':'valid','title':'','detail':'','action':'','card_cls':'','banner_cls':'','title_color':''}

def clamp_prob(x, lo=5.0, hi=95.0): return round(max(lo, min(hi, float(x))), 1)
def probability_label(p): return "Tinggi" if p>=75 else "Sedang" if p>=60 else "Spekulatif" if p>=45 else "Rendah"

def estimate_trade_probabilities(score, grade, lp, bmin, bmax, sl, tp1, tp2, tp3, atr_val, ind, vc, tape, bandar):
    base = float(score) * 0.65
    g_bonus = {"A": 8.0, "B": 4.0, "C": 0.0}.get(grade, 0.0)
    s_adj = -35.0 if lp <= sl else 12.0 if bmin <= lp <= bmax else -4.0 if lp < bmin else -8.0 - min((lp-bmax)/max(bmax,1.0)*80.0, 18.0)
    t_adj = (3 if ind.get("above_ema20") else 0) + (4 if ind.get("above_ema50") else 0) + (3 if ind.get("above_ema200") else 0) + (3 if ind.get("ema20_rising") else 0)
    rsi = ind.get("rsi_val", 50.0)
    m_adj = (5 if 45<=rsi<=65 else -2 if 65<rsi<=75 else -8 if rsi>75 else -5 if rsi<35 else 0) + (4 if ind.get("cmf_val",0)>0.05 else -5 if ind.get("cmf_val",0)<-0.05 else 0)
    v_adj = 0.0
    if vc.get("valid"):
        vr, cd = vc.get("vol_ratio",0), vc.get("candle_dir")
        v_adj = 6 if cd=="bullish" and vr>=1.3 else 3 if vr>=1.5 else -6 if cd=="bearish" and vr>=1.3 else 0
    tp_adj, bd_adj = 0.0, 0.0
    for s in tape.get("signals", []): tp_adj += 5 if s[1]=="accum" else -6 if s[1]=="distrib" else -3 if s[1]=="warn" else 0
    dom = bandar.get("dominant")
    if dom:
        cw = {"high":7.0,"med":4.0,"low":2.0}.get(dom.get("conf"),2.0)
        bd_adj = cw if dom.get("style")=="accum" else -cw
    a_adj = 0.0
    if ind.get("adx_strength")=="strong": a_adj = 5 if ind.get("adx_bullish_dir") else -6
    elif ind.get("adx_strength")=="moderate": a_adj = 2 if ind.get("adx_bullish_dir") else -2
    atr_pct = atr_val / max(lp, 1.0)
    vol_adj = -8 if atr_pct>0.08 else -4 if atr_pct>0.05 else 3 if 0.015<=atr_pct<=0.04 else 0
    p_entry = clamp_prob(base + g_bonus + s_adj + t_adj + m_adj + v_adj + tp_adj + bd_adj + a_adj + vol_adj)
    if lp <= sl: p_entry = min(p_entry, 15.0)
    rps = max(lp - sl, 1.0)
    p_tp1 = clamp_prob(p_entry + min(max(((tp1-lp)/rps-1.2)*6.0, -8.0), 10.0) - atr_pct*35.0)
    p_tp2 = clamp_prob(p_entry - 12.0 + min(max(((tp2-lp)/rps-2.0)*4.0, -10.0), 8.0) - atr_pct*45.0)
    p_tp3 = clamp_prob(p_entry - 24.0 + min(max(((tp3-lp)/rps-3.0)*3.0, -12.0), 6.0) - atr_pct*55.0)
    p_sl = 95.0 if lp <= sl else clamp_prob(100.0 - p_tp1 + atr_pct*45.0, 5.0, 90.0)
    return {"Prob Entry": p_entry, "Prob TP1": p_tp1, "Prob TP2": p_tp2, "Prob TP3": p_tp3, "Prob SL": p_sl, "Confidence": probability_label(p_entry)}

# =============================================================================
# 9. MAIN STRATEGY ENGINE & ACTIONABILITY RANKING
# =============================================================================
def quant_strategy_engine(all_data, config, trading_mode):
    mode_params = INTRADAY_PARAMS if trading_mode == "Intraday (Fast Trade)" else SWING_PARAMS
    interval = "60m" if trading_mode == "Intraday (Fast Trade)" else "1d"
    results, skipped = [], {}
    
    for t, df in all_data.items():
        if len(df) < 60: skipped[t] = "candle kurang"; continue
        df = df.copy()
        try: last_close_raw = float(df['Close'].iloc[-1])
        except: skipped[t] = "harga error"; continue
        
        tradeable, reason = is_tradeable_stock(df, last_close_raw, interval)
        if not tradeable: skipped[t] = reason; continue
        
        try: ind = calculate_indicators(df)
        except Exception as e: skipped[t] = f"indikator error: {e}"; continue
        
        lc = ind['last_close']
        if not np.isfinite(lc) or lc <= 0: skipped[t] = "harga invalid"; continue
        if lc < config['min_price'] or lc > config['max_price']: skipped[t] = "filter harga"; continue
        if ind['adtv'] < config['min_adtv']: skipped[t] = "ADTV rendah"; continue
        
        score, breakdown = compute_total_score(ind)
        if score < config['min_score_threshold']: skipped[t] = "score rendah"; continue
        
        grade = "A" if score >= 80 else "B" if score >= 65 else "C"
        vc, tape, bandar = analyse_volume_context(df), analyse_tape(df, ind['atr_val']), analyse_bandarmology(df, ind['atr_val'])
        plan = build_trade_plan(lc, ind['atr_val'], ind['atr_pct'], mode_params)
        
        entry_ref = float(plan['entry_ref'])
        loss_ps = entry_ref - float(plan['stop_loss'])
        if loss_ps <= 0: skipped[t] = "risk invalid"; continue
        
        results.append({
            "Ticker": t.split('.')[0], "_ticker_jk": t, "Score": score, "Grade": grade, "Last Price": int(round(lc)),
            "Buy Min": plan['buy_min'], "Buy Max": plan['buy_max'], "TP1": int(plan['tp1']), "TP2": int(plan['tp2']), "TP3": int(plan['tp3']),
            "Upside TP1": f"+{round((plan['tp1']-entry_ref)/entry_ref*100, 1)}%", "Upside TP2": f"+{round((plan['tp2']-entry_ref)/entry_ref*100, 1)}%", "Upside TP3": f"+{round((plan['tp3']-entry_ref)/entry_ref*100, 1)}%",
            "Stop Loss": int(plan['stop_loss']), "Risk%": f"-{round((entry_ref-plan['stop_loss'])/entry_ref*100, 1)}%", "R/R TP1": f"1:{plan['rr1']}", "R/R TP2": f"1:{plan['rr2']}", "R/R TP3": f"1:{plan['rr3']}",
            "ATR": round(ind['atr_val'], 1), "ATR Adj": plan['atr_adj'], "RSI": round(ind['rsi_val'], 1), "CMF": round(ind['cmf_val'], 3), "ADX": ind['adx_val'], "ADX Strength": ind['adx_strength'], "ADX Bullish": ind['adx_bullish_dir'],
            "TS Kriteria": plan['ts_rule'], "Partial Plan": plan['partial_plan'], "Entry Ref": entry_ref, "Loss Per Share": loss_ps, "Rr1_Raw": plan['rr1'],
            "_breakdown": breakdown, "_vol_ctx": vc, "_tape": tape, "_bandar": bandar, "_ind": ind
        })
        
    st.session_state['scan_meta'] = {'total_input': len(all_data), 'lolos': len(results), 'difilter': len(skipped), 'skipped': skipped}
    if not results: return pd.DataFrame()
    
    live_prices = fetch_live_prices([r["_ticker_jk"] for r in results])
    for r in results:
        lp = live_prices.get(r["_ticker_jk"])
        r["Live Price"] = int(round(float(lp))) if lp and np.isfinite(float(lp)) and float(lp) > 0 else int(r["Last Price"])
        r["Live Src"] = "live" if lp else "delayed"
        
        probs = estimate_trade_probabilities(r["Score"], r["Grade"], float(r["Live Price"]), float(r["Buy Min"]), float(r["Buy Max"]), float(r["Stop Loss"]), float(r["TP1"]), float(r["TP2"]), float(r["TP3"]), float(r["ATR"]), r["_ind"], r["_vol_ctx"], r["_tape"], r["_bandar"])
        r.update(probs)
        
        dyn_risk = get_dynamic_risk(config['capital_risk_limit_pct'], r["Grade"], r["Confidence"])
        r["Dyn Risk %"] = round(dyn_risk, 2)
        rp_risk = config['total_capital'] * (dyn_risk / 100.0)
        lots = int(rp_risk / r["Loss Per Share"] / 100)
        max_alloc = config['total_capital'] * (config['max_capital_allocation_pct'] / 100.0)
        req_cap = lots * 100 * r["Entry Ref"]
        if req_cap > max_alloc:
            lots = int(max_alloc / (100 * r["Entry Ref"]))
            req_cap = lots * 100 * r["Entry Ref"]
        r["Lots"] = int(lots)
        r["Alokasi (Rp)"] = req_cap
        del r["_ticker_jk"]
        
    df_out = pd.DataFrame(results)
    
    def _calculate_action_rank(row):
        v = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
        rank = 0.0
        if v['status'] == 'valid': rank += 1000
        elif v['status'] == 'waiting': rank += 500
        else: return -1000
        rank += row["Rr1_Raw"] * 50
        dom = row.get("_bandar", {}).get("dominant")
        if dom:
            if dom.get("style") == "accum": rank += {"high": 150, "med": 100, "low": 50}.get(dom.get("conf"), 0)
            elif dom.get("style") == "distrib": rank -= {"high": 150, "med": 100, "low": 50}.get(dom.get("conf"), 0)
        for sig in row.get("_tape", {}).get("signals", []):
            if sig[1] == "accum": rank += 80
            elif sig[1] == "distrib": rank -= 80
            elif sig[1] == "warn": rank -= 40
        if row.get("ADX Strength") == "strong": rank += 80 if row.get("ADX Bullish") else -80
        elif row.get("ADX Strength") == "moderate": rank += 40 if row.get("ADX Bullish") else -40
        rank += (row["Prob Entry"] - row["Prob SL"]) * 2
        rank += row["Score"]
        return rank

    df_out["_action_rank"] = df_out.apply(_calculate_action_rank, axis=1)
    
    def _gen_stars(row):
        r = row["_action_rank"]
        if r >= 1300: return "⭐⭐⭐⭐⭐"
        if r >= 1100: return "⭐⭐⭐⭐"
        if r >= 900:  return "⭐⭐⭐"
        if r >= 700:  return "⭐⭐"
        return "⭐"
        
    df_out["Sistem Rating"] = df_out.apply(_gen_stars, axis=1)
    
    return df_out.sort_values(by="_action_rank", ascending=False).drop(columns=["_action_rank"]).reset_index(drop=True)

# =============================================================================
# 10. RENDER HELPERS
# =============================================================================
def _pill(l, s): return f'<span class="ind-pill ind-{s}">{l}</span>'
def _tape_pill(s, st, c): return f'<span class="tape-pill tape-{st}">{s} {c}%</span>'
def _conf_badge(c): 
    cls, lbl = {'high':('conf-hi','▲ Tinggi'),'med':('conf-med','◆ Sedang'),'low':('conf-lo','● Rendah')}.get(c,('conf-lo','—'))
    return f'<span class="{cls}">{lbl}</span>'
def _adx_info(a, s, b): 
    lbl = {"strong": "Kuat", "moderate": "Sedang", "weak": "Lemah"}.get(s, "—")
    return f'<span class="adx-info">ADX {a:.0f} {"▲" if b else "▼"} {lbl}</span>'
def _grade_badge(g): return f'<span class="grade-{g}">Grade {g}</span>'

def _render_volume_ctx(vc):
    if not vc.get('valid'): return ''
    dc = {'bullish':('#3fb950','▲'),'bearish':('#f85149','▼'),'doji':('#8b949e','—')}.get(vc['candle_dir'],('#8b949e','—'))
    vr = vc['vol_ratio']
    bc, vl = ('#3fb950',f'{vr:.1f}× vol (spike)') if vr>=2.0 else ('#e3b341',f'{vr:.1f}× vol (atas rata)') if vr>=1.3 else ('#8b949e',f'{vr:.1f}× vol (normal)') if vr>=0.7 else ('#f85149',f'{vr:.1f}× vol (sepi)')
    return f'''<div class="vol-ctx"><div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:0.68rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;">Volume Konteks</span>
        <span style="font-size:0.72rem;font-weight:700;color:{dc[0]};">{dc[1]} {vc["candle_dir"].title()}</span></div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.3rem;margin-top:0.25rem;">
        <div><div style="font-size:0.6rem;color:#8b949e;">Vol vs MA</div><div style="font-size:0.7rem;font-weight:700;color:{bc};">{vl}</div></div>
        <div><div style="font-size:0.6rem;color:#8b949e;">Body Size</div><div style="font-size:0.7rem;font-weight:700;color:#c9d1d9;">{int(vc["body_pct"]*100)}% range</div></div>
        <div><div style="font-size:0.6rem;color:#8b949e;">Close Pos</div><div style="font-size:0.7rem;font-weight:700;color:#c9d1d9;">{int(vc["close_pos"]*100)}% hi-lo</div></div></div>
        <div class="vol-bar-track"><div class="vol-bar-fill" style="width:{min(int(vr/3.0*100),100)}%;background:{bc};"></div></div></div>'''

def _render_tape_bandar(tape, bandar):
    p = []
    if tape.get('signals'): 
        pills = "".join(_tape_pill(s[3],s[1],s[4]) for s in tape["signals"][:4])
        p.append(f'<div style="margin-bottom:0.25rem;"><span style="font-size:0.6rem;color:#8b949e;text-transform:uppercase;margin-right:0.3rem;">Tape</span>{pills}</div>')
    if bandar.get('signals'): 
        pills = "".join(_tape_pill(s["short"],s["style"],s["conf_pct"]) for s in bandar["signals"][:3])
        conf = _conf_badge(bandar["dominant"]["conf"]) if bandar.get("dominant") else ""
        p.append(f'<div style="display:flex;align-items:center;gap:0.3rem;flex-wrap:wrap;margin-bottom:0.25rem;"><span style="font-size:0.6rem;color:#8b949e;text-transform:uppercase;">Bandar</span>{pills}{conf}</div>')
    if bandar.get('narasi_tech'): p.append(f'<div style="background:rgba(255,255,255,0.02);border-left:2px solid #30363d;padding:0.3rem 0.5rem;border-radius:0 4px 4px 0;"><div class="narasi-tech">"{bandar["narasi_tech"]}"</div><div class="narasi-plain">→ {bandar["narasi_plain"]}</div></div>')
    return f'<div class="section-divider"></div><div style="margin-bottom:0.4rem;">{"".join(p)}</div>' if p else ''

def _price_status(lp, rc, bmin, bmax, src):
    c, i, l = ("#3fb950","●","Dalam Zona Beli") if bmin <= lp <= bmax else ("#58a6ff","↓","Di Bawah Zona") if lp < bmin else ("#e3b341","↑","Di Atas Zona")
    sl, sc = "Live" if src=="live" else "Delayed", "#3fb950" if src=="live" else "#8b949e"
    rn = ""
    if rc != lp:
        d = lp - rc; dp = d / rc * 100; s = "+" if d >= 0 else ""
        col = "#3fb950" if d>=0 else "#f85149"
        rn = f'<span style="font-size:0.68rem;color:{col};margin-left:0.3rem;">{s}{dp:.1f}% vs ref {fmt_num(rc)}</span>'
    return f'''<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.4rem;padding:0.35rem 0.6rem;background:rgba(255,255,255,0.04);border-radius:6px;border-left:3px solid {c};">
        <div style="display:flex;align-items:baseline;gap:0.4rem;flex-wrap:wrap;"><span style="font-size:1.3rem;font-weight:800;color:{c};">{fmt_num(lp)}</span>{rn}</div>
        <div style="text-align:right;"><div style="font-size:0.65rem;color:{sc};font-weight:700;">{sl}</div><div style="font-size:0.65rem;color:{c};font-weight:600;">{i} {l}</div></div></div>'''

# =============================================================================
# 11. AI INTEGRATION (GEMINI 1.5 FLASH CO-PILOT)
# =============================================================================
def analyze_with_gemini(api_key, stocks_data):
    if not api_key or not stocks_data: return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    sys_prompt = "Anda adalah Trader Proprietary Senior dan Analis Bandarmology di Bursa Efek Indonesia (BEI). Tugas Anda adalah mengaudit seluruh daftar hasil skrining kuantitatif, membedah narasi di balik angka, mendeteksi potensi jebakan, dan memilih saham paling superior. Gunakan Bahasa Indonesia yang profesional, tegas, dan to-the-point."
    
    data_str = ""
    for s in stocks_data:
        tape_sigs = s.get('_tape', {}).get('signals', [])
        tape_str = ", ".join([sig[2] for sig in tape_sigs]) if tape_sigs else 'None'
        
        dom = s.get('_bandar', {}).get('dominant')
        bandar_str = f"{dom['label']} ({dom['conf']})" if dom else 'None'
        
        adx_dir = 'Bullish' if s.get('ADX Bullish') else 'Bearish'
        vol_ctx = s.get('_vol_ctx', {})
        vol_ratio = vol_ctx.get('vol_ratio', 0)
        candle_dir = vol_ctx.get('candle_dir', 'N/A')
        
        rating_str = s.get('Sistem Rating', 'N/A')
        tp1_str = f"{fmt_num(s['TP1'])} ({s['Upside TP1']})"
        
        data_str += f"""
        Saham: {s['Ticker']} (Rating: {rating_str}, Grade: {s['Grade']}) | Harga: {fmt_num(s['Live Price'])} | Zona: {fmt_num(s['Buy Min'])}-{fmt_num(s['Buy Max'])} | TP1: {tp1_str} | SL: {fmt_num(s['Stop Loss'])} | R/R: {s['R/R TP1']} | ADX: {s['ADX']} ({s['ADX Strength']} {adx_dir}) | RSI: {s['RSI']} | VolRatio: {vol_ratio}x | Tape: {tape_str} | Bandar: {bandar_str}
        """
        
    user_prompt = f"""
    Berikut adalah hasil skrining kuantitatif untuk {len(stocks_data)} saham teratas hari ini:
    {data_str}
    
    Tolong analisa SEMUA saham di atas. Berikan jawaban dengan format MARKDOWN berikut:
    1. **🏆 Top Pick Utama:** Pilih 1 saham PALING layak dieksekusi hari ini dari daftar di atas (atau bilang "Skip Semua" jika semua berisiko). Jelaskan kenapa saham tersebut terpilih dibanding yang lain.
    2. **🕵️ Analisa Bandar & Tape Market:** Baca pola volume dan tape reading dari seluruh saham di list. Apakah market secara umum lagi fase akumulasi massal, atau ada tanda-taran distribusi institusional?
    3. **⚠️ Saham Berisiko (Trap):** Sebutkan saham mana saja di list yang berpotensi jadi jebakan (pump & dump, false breakout, atau buying climax) yang sebaiknya dihindari meskipun skornya bagus.
    4. **🎯 Strategi Eksekusi Top Pick:** Berikan rencana eksekusi detail (scaling in, partial profit, kapan cut loss) untuk saham Top Pick tadi.
    """
    
    payload = {
        "system_instruction": {
            "parts": [{"text": sys_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 2000
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error API Gemini: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Gagal konek ke API Gemini: {e}"

# =============================================================================
# 12. BEST BUY ENGINE
# =============================================================================
MIN_BEST_BUY_SCORE = 45.0

def compute_best_buy_score(row):
    r, total = [], 0.0
    v = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
    if v['status'] == 'valid': total += 30; r.append("✅ Harga dalam zona beli")
    elif v['status'] == 'waiting':
        if row["Live Price"] > row["Buy Max"]: total += 4; r.append("⏳ Di atas zona, tunggu pullback")
        else: total += 10; r.append("⏳ Di bawah zona, SL masih aman")
    else: return 0.0, []
    if row.get("Lots", 0) < 1: return 0.0, ["Modal tidak cukup untuk risiko minimum"]
    total += (row["Score"]/100.0)*25; r.append(f"📊 Score teknikal {row['Score']}")
    total += {"A":10,"B":6,"C":2}.get(row.get("Grade","C"), 2); r.append(f"🏅 Grade {row.get('Grade','C')}")
    dom = row.get("_bandar", {}).get("dominant")
    if dom:
        cp = {"high":15,"med":8,"low":3}.get(dom.get("conf","low"),3)
        if dom.get("style") == "distrib": total -= cp; r.append(f"⚠️ Sinyal distribusi ({dom.get('conf','')})")
        else: total += cp; r.append(f"🔍 Bandar: {dom.get('label','')} ({dom.get('conf','')})")
    else: r.append("— Tidak ada sinyal bandar")
    ts = row.get("_tape", {}).get("signals", [])
    if [s for s in ts if s[1] == "accum"]: total += 10; r.append("📼 Tape: Akumulasi")
    elif any(s[1] == "distrib" for s in ts): total -= 5; r.append("📼 Tape: Distribusi")
    vc = row.get("_vol_ctx", {})
    if vc.get("valid"):
        vo, bo = vc.get("vol_ratio",0) >= 1.3, vc.get("candle_dir") == "bullish"
        if vo and bo: total += 10; r.append("📊 Vol spike + candle bullish")
        elif vo: total += 5; r.append("📊 Vol spike")
        elif bo: total += 3; r.append("📊 Candle bullish")
    return round(max(total, 0.0), 1), r

def pick_best_buy(df):
    if df.empty: return None, 0.0, [], False
    bt, bs, br = None, -1.0, []
    for _, row in df.iterrows():
        if row["Live Price"] > row["Buy Max"]: continue
        s, r = compute_best_buy_score(row)
        if r and s > bs: bs, br, bt = s, r, row["Ticker"]
    if bt is None or bs < MIN_BEST_BUY_SCORE: return None, 0.0, [], False
    return bt, bs, br, True

def render_best_buy_banner(t, s, r, row):
    v = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
    sl, sc = ("🟢 Harga dalam zona — siap entry", "#3fb950") if v['status']=='valid' else ("🟡 Di bawah zona — pantau & tunggu", "#e3b341")
    bc = "#ffd700" if s>=70 else "#e3b341" if s>=50 else "#8b949e"
    ph = f'''<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.55rem;background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:0.45rem 0.55rem;">
        <div><div class="label">Prob Entry</div><div style="color:#58a6ff;font-weight:900;">{row["Prob Entry"]}%</div></div>
        <div><div class="label">Prob TP1</div><div style="color:#3fb950;font-weight:900;">{row["Prob TP1"]}%</div></div>
        <div><div class="label">Prob SL</div><div style="color:#f85149;font-weight:900;">{row["Prob SL"]}%</div></div>
        <div><div class="label">Confidence</div><div style="color:#e3b341;font-weight:900;">{row["Confidence"]}</div></div></div>''' if "Prob Entry" in row else ""
    rh = ph + "".join(f'<span style="display:inline-block;background:rgba(255,255,255,0.06);border-radius:6px;padding:0.1rem 0.4rem;margin:0.1rem;font-size:0.68rem;color:#c9d1d9;">{x}</span>' for x in r)
    st.markdown(f'''<div class="best-buy-banner"><div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">
        <div><span class="best-buy-crown">👑 BEST BUY</span><span style="font-size:1.5rem;font-weight:900;color:#ffd700;margin-left:0.5rem;">{t}</span><span style="font-size:0.8rem;color:{sc};margin-left:0.6rem;font-weight:700;">{sl}</span></div>
        <div style="text-align:right;"><div style="font-size:0.65rem;color:#8b949e;text-transform:uppercase;">Entry Score</div><div style="font-size:1.4rem;font-weight:900;color:#ffd700;">{s}<span style="font-size:0.7rem;color:#8b949e;">/100</span></div></div></div>
        <div style="margin-top:0.5rem;"><div class="vol-bar-track" style="margin-bottom:0.4rem;"><div class="vol-bar-fill" style="width:{min(int(s),100)}%;background:{bc};height:6px;border-radius:4px;"></div></div>
        <div style="font-size:0.65rem;color:#8b949e;margin-bottom:0.25rem;text-transform:uppercase;">Alasan Pemilihan</div><div style="line-height:1.8;">{rh}</div></div>
        <div style="margin-top:0.5rem;padding-top:0.4rem;border-top:1px solid rgba(255,215,0,0.2);display:grid;grid-template-columns:repeat(4,1fr);gap:0.4rem;font-size:0.72rem;">
        <div><div style="color:#8b949e;font-size:0.6rem;">HARGA LIVE</div><div style="color:#fff;font-weight:700;">{fmt_num(row["Live Price"])}</div></div>
        <div><div style="color:#8b949e;font-size:0.6rem;">ZONA BELI</div><div style="color:#fff;font-weight:700;">{fmt_num(row["Buy Min"])}–{fmt_num(row["Buy Max"])}</div></div>
        <div><div style="color:#8b949e;font-size:0.6rem;">STOP LOSS</div><div style="color:#f85149;font-weight:700;">{fmt_num(row["Stop Loss"])}</div></div>
        <div><div style="color:#8b949e;font-size:0.6rem;">TARGET TP1</div><div style="color:#3fb950;font-weight:700;">{fmt_num(row["TP1"])} <span style="font-size:0.65rem;">{row["Upside TP1"]}</span></div></div></div></div>''', unsafe_allow_html=True)

def render_no_best_buy_notice():
    st.markdown('''<div class="watchlist-banner"><div style="font-size:0.95rem;font-weight:700;color:#58a6ff;">ℹ️ Belum Ada Rekomendasi Kuat Hari Ini</div>
    <div style="font-size:0.78rem;color:#8b949e;margin-top:0.3rem;">Tidak ada saham memenuhi standar "Best Buy" (karena harga chasing atau score lemah). Cek tabel di bawah untuk kandidat "Tunggu Dulu".</div></div>''', unsafe_allow_html=True)

# =============================================================================
# 13. RENDER TRADE CARDS
# =============================================================================
def render_trade_cards(df, max_cards=6, best_ticker=None):
    if df.empty: st.info("ℹ️ Tidak ada saham yang memenuhi kriteria atau alokasi modal tidak cukup."); return
    cards = df.head(max_cards)
    for i in range(0, len(cards), 3):
        batch = cards.iloc[i:i+3]
        cols = st.columns(len(batch))
        for j, (_, row) in enumerate(batch.iterrows()):
            with cols[j]:
                bd = row.get("_breakdown", {})
                def pf(k, l): 
                    if k not in bd: return ""
                    sv, sg = bd[k]; return _pill(f"{l} {sv:.0f}", sg)
                ph = pf("trend","EMA")+pf("rsi","RSI")+pf("cmf","CMF")+pf("volume","VOL")+pf("squeeze","SQZ")+pf("adx","ADX")
                vh = _render_volume_ctx(row.get("_vol_ctx", {}))
                th = _render_tape_bandar(row.get("_tape", {}), row.get("_bandar", {}))
                ah = _adx_info(row["ADX"], row.get("ADX Strength","weak"), row.get("ADX Bullish", False))
                v = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
                is_best = row["Ticker"] == best_ticker
                cc = "best-buy-card" if is_best else v['card_cls']
                ch = '<div><span class="best-buy-crown">👑 Best Buy</span></div>' if is_best else ''
                bh = f'<div class="{v["banner_cls"]}"><div style="font-size:0.78rem;font-weight:800;color:{v["title_color"]};margin-bottom:0.2rem;">{v["title"]}</div><div style="font-size:0.68rem;color:#c9d1d9;line-height:1.35;">{v["detail"]}</div><div style="font-size:0.65rem;color:#8b949e;margin-top:0.2rem;font-style:italic;">{v["action"]}</div></div>' if v['status'] in ('expired','waiting') else ''
                do, dc = '<div class="dimmed">' if v['status']=='expired' else '<div>', '</div>'
                
                st.markdown(f'''<div class="metric-card {cc}">{ch}
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">
                        <span class="ticker">{row["Ticker"]}</span><div style="display:flex;gap:0.4rem;align-items:center;">{_grade_badge(row["Grade"])}<span class="score-badge">Score {row["Score"]}</span></div></div>
                    <div style="margin-bottom:0.5rem;">{ph}</div>{vh}{bh}{_price_status(row["Live Price"], row["Last Price"], row["Buy Min"], row["Buy Max"], row["Live Src"])}{do}
                    <div class="price-range">{fmt_num(row["Buy Min"])} – {fmt_num(row["Buy Max"])}</div>
                    <div class="label" style="margin-bottom:0.6rem;">Area Rentang Buy · ATR {row["ATR"]} {ah}</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.4rem;margin-bottom:0.6rem;border-top:1px solid #30363d;padding-top:0.4rem;">
                        <div><div class="label">TP 1 <span class="rr-badge">({row["R/R TP1"]})</span></div><div class="tp">{fmt_num(row["TP1"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP1"]}</span></div></div>
                        <div><div class="label">TP 2 <span class="rr-badge">({row["R/R TP2"]})</span></div><div class="tp">{fmt_num(row["TP2"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP2"]}</span></div></div>
                        <div><div class="label">TP 3 <span class="rr-badge">({row["R/R TP3"]})</span></div><div class="tp" style="color:#bc8cff;">{fmt_num(row["TP3"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP3"]}</span></div></div></div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.4rem;">
                        <div><div class="label">Stop Loss</div><div class="sl">{fmt_num(row["Stop Loss"])} <span style="font-size:0.68rem;opacity:0.8">{row["Risk%"]}</span></div></div>
                        <div><div class="label">Trailing Strategy</div><div class="ts-rule" style="font-size:0.78rem;">{row["TS Kriteria"]}</div></div></div>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.35rem;margin-bottom:0.5rem;background:rgba(88,166,255,0.05);border:1px solid rgba(88,166,255,0.18);border-radius:6px;padding:0.45rem 0.5rem;">
                        <div><div class="label">Prob Entry</div><div style="color:#58a6ff;font-weight:800;">{row["Prob Entry"]}%</div></div>
                        <div><div class="label">Prob TP1</div><div style="color:#3fb950;font-weight:800;">{row["Prob TP1"]}%</div></div>
                        <div><div class="label">Prob SL</div><div style="color:#f85149;font-weight:800;">{row["Prob SL"]}%</div></div>
                        <div><div class="label">TP2</div><div style="color:#3fb950;font-weight:700;">{row["Prob TP2"]}%</div></div>
                        <div><div class="label">TP3</div><div style="color:#bc8cff;font-weight:700;">{row["Prob TP3"]}%</div></div>
                        <div><div class="label">Confidence</div><div style="color:#e3b341;font-weight:800;">{row["Confidence"]}</div></div></div>
                    <div style="margin-bottom:0.4rem;background:rgba(255,255,255,0.02);border-radius:6px;padding:0.3rem 0.5rem;border:1px solid #21262d;">
                        <div class="label" style="margin-bottom:0.15rem;">Rencana Partial Exit</div><div style="font-size:0.68rem;color:#c9d1d9;">{row["Partial Plan"]}</div></div>
                    <div style="border-top:1px solid #30363d;padding-top:0.4rem;display:grid;grid-template-columns:1fr 1fr;gap:0.3rem;font-size:0.75rem;">
                        <div><div class="label">Lots (Risk {row["Dyn Risk %"]}% · ATR {row["ATR Adj"]}x)</div><div style="color:#fff;font-weight:600">{int(row["Lots"])} Lot</div></div>
                        <div><div class="label">Maks Alokasi</div><div style="color:#58a6ff;font-weight:600">{fmt_idr(row["Alokasi (Rp)"])}</div></div></div>{dc}{th}</div>''', unsafe_allow_html=True)

# =============================================================================
# 14. SIDEBAR & MAIN UI
# =============================================================================
st.sidebar.header("⚙️ Parameter Algoritma")
capital = st.sidebar.number_input("Total Modal Akun (Rp)", value=50_000_000, step=5_000_000, min_value=1_000_000)
risk_limit = st.sidebar.slider("Base Risk per Trade (%)", 0.5, 5.0, 2.0, 0.5, help="Risiko maksimum. Sistem akan memotong risiko ini secara dinamis untuk saham Grade B/C.")
allocation_limit = st.sidebar.slider("Maks Alokasi Dana per Saham (%)", 10, 50, 25, 5)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filter Likuiditas & Harga")
min_adtv_value = st.sidebar.number_input("Minimal ADTV (Rp)", value=500_000_000, step=100_000_000, min_value=0)
min_px = st.sidebar.number_input("Harga Minimal Saham (Rp)", value=100, step=50, min_value=1)
max_px = st.sidebar.number_input("Harga Maksimal Saham (Rp)", value=25_000, step=500, min_value=1)
min_score = st.sidebar.slider("Min Score Threshold", 50, 85, 60, 5, help="Semakin tinggi = sinyal lebih selektif")

st.sidebar.markdown("---")
st.sidebar.header("🤖 AI Co-Pilot (Gemini)")
gemini_api_key = st.sidebar.text_input("Google Gemini API Key", type="password", help="Dapatkan API Key gratis di aistudio.google.com/app/apikey")
ai_analyze_btn = st.sidebar.checkbox("Analisa Semua Hasil Skrining pakai AI", value=False)

if min_px >= max_px: st.sidebar.error("⚠️ Harga Minimal harus lebih kecil dari Harga Maksimal.")
st.sidebar.markdown("---")
debug_ph = st.sidebar.empty()

cfg = {'total_capital': capital, 'capital_risk_limit_pct': risk_limit, 'max_capital_allocation_pct': allocation_limit, 'min_adtv': min_adtv_value, 'min_price': min_px, 'max_price': max_px, 'min_score_threshold': float(min_score)}

trading_mode = st.radio("📊 **Pilih Gaya Trading:**", ["Swing Trading (Harian)", "Intraday (Fast Trade)"], horizontal=True)

st.markdown("### 📋 Daftar Saham")
input_tab, upload_tab = st.tabs(["✏️ Input Manual", "📂 Upload CSV"])
tickers_ready = ["BBRI.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

with input_tab:
    ticker_text = st.text_area("Kode Saham (pisah koma/spasi):", value="BBRI, BBCA, BMRI, TLKM, ASII", height=100)
    if ticker_text.strip(): tickers_ready = tickers_from_text(ticker_text)

uploaded_csv = None
with upload_tab:
    uploaded_csv = st.file_uploader("Upload CSV emiten:", type=["csv"])
    if uploaded_csv is not None:
        try:
            t_csv = parse_tickers_from_df(pd.read_csv(uploaded_csv))
            if t_csv: tickers_ready = t_csv; st.success(f"✅ {len(tickers_ready)} saham dimuat.")
            else: st.warning("⚠️ Tidak ada ticker valid dalam CSV.")
        except Exception as e: st.error(f"Error CSV: {e}")

if uploaded_csv is None:
    local_tickers = load_local_emiten_csv()
    if local_tickers: tickers_ready = local_tickers

st.markdown("---")
btn_col1, btn_col2 = st.columns([1, 4])
with btn_col1: execute_scan = st.button("🚀 Jalankan Skrining", type="primary", use_container_width=True)
with btn_col2:
    if st.button("🗑️ Reset Cache & State"):
        st.cache_data.clear()
        st.session_state['raw_market_data'] = {}
        st.session_state['last_loaded_mode'] = None
        st.session_state['scan_meta'] = {}
        st.success("Reset berhasil.")

# =============================================================================
# 15. EXECUTION CORE
# =============================================================================
if execute_scan:
    if not tickers_ready: st.error("❌ Daftar emiten kosong."); st.stop()
    if min_px >= max_px: st.error("❌ Filter harga tidak valid."); st.stop()

    p_days, p_interval = (30, "60m") if trading_mode == "Intraday (Fast Trade)" else (400, "1d")
    CHUNK_SIZE = 15 if trading_mode == "Intraday (Fast Trade)" else 40

    sorted_tickers = sorted(set(tickers_ready))
    chunks = [sorted_tickers[i:i + CHUNK_SIZE] for i in range(0, len(sorted_tickers), CHUNK_SIZE)]
    buffer = {}
    status_ph, progress_b = st.empty(), st.progress(0)

    for idx, chunk in enumerate(chunks):
        n_done = min((idx + 1) * CHUNK_SIZE, len(sorted_tickers))
        status_ph.markdown(f"⏳ Mengunduh {n_done}/{len(sorted_tickers)} emiten (Batch {idx+1}/{len(chunks)})…")
        progress_b.progress(int((idx + 1) / len(chunks) * 100))
        buffer.update(download_ticker_chunk(chunk, p_days, p_interval))

    status_ph.empty(); progress_b.empty()

    if not buffer: st.error("❌ Tidak ada data berhasil diunduh. Cek koneksi atau daftar ticker."); st.stop()

    st.session_state['raw_market_data'] = buffer
    st.session_state['last_loaded_mode'] = trading_mode
    st.success(f"✅ Data berhasil untuk {len(buffer)}/{len(sorted_tickers)} saham.")

if st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] == trading_mode:
    final_df = quant_strategy_engine(st.session_state['raw_market_data'], cfg, trading_mode)
    st.markdown(f"### 📈 Hasil Scan [{trading_mode}]")

    if not final_df.empty:
        v_counts = final_df.apply(lambda r: _check_signal_validity(r["Live Price"], r["Stop Loss"], r["Buy Min"], r["Buy Max"])['status'], axis=1).value_counts()
        m_cols = st.columns(4)
        m_cols[0].metric("Total Saham Lolos", len(final_df))
        m_cols[1].metric("✅ Siap Entry", int(v_counts.get('valid', 0)))
        m_cols[2].metric("⏳ Tunggu Dulu", int(v_counts.get('waiting', 0)))
        m_cols[3].metric("🚫 Hindari", int(v_counts.get('expired', 0)))

    best_ticker, best_score, best_reasons, has_rec = pick_best_buy(final_df)
    if best_ticker:
        best_row = final_df[final_df["Ticker"] == best_ticker].iloc[0]
        render_best_buy_banner(best_ticker, best_score, best_reasons, best_row)
    elif not final_df.empty:
        render_no_best_buy_notice()
    else:
        st.info("ℹ️ Tidak ada saham yang lolos filter pada scan ini.")

    # ── AI Co-Pilot Execution (Gemini 1.5 Flash) ──────────────────────────
    if ai_analyze_btn and gemini_api_key and not final_df.empty:
        with st.spinner(f"🤖 AI Co-Pilot (Gemini 1.5 Flash) sedang menganalisa {len(final_df)} saham hasil skrining..."):
            all_data = final_df.to_dict(orient='records')
            ai_response = analyze_with_gemini(gemini_api_key, all_data)
            if ai_response:
                st.markdown(f'''<div class="ai-box">
                    <div class="ai-header">🤖 Analisa AI Co-Pilot (Gemini) - Market Overview</div>
                    <div class="ai-content">{ai_response}</div>
                </div>''', unsafe_allow_html=True)
            else:
                st.error("Gagal mendapatkan respons dari AI.")
    elif ai_analyze_btn and not gemini_api_key:
        st.warning("⚠️ Masukkan Google Gemini API Key di sidebar untuk mengaktifkan AI.")
    # ──────────────────────────────────────────────────────────────────────

    render_trade_cards(final_df, max_cards=6, best_ticker=best_ticker)

    if not final_df.empty:
        st.markdown("---")
        st.markdown("### 📋 Ringkasan Semua Hasil Skrining")
        st.caption("Saham diurutkan berdasarkan Sistem Rating (Actionability Rank) yang memperhitungkan Validitas, R/R, Bandar, ADX, dan Probabilitas.")

        def _vl(row): 
            v = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
            return {"valid": "✅ Siap Entry", "waiting": "⏳ Tunggu Dulu", "expired": "🚫 Hindari"}[v["status"]]
            
        def _bl(row): 
            dom = row.get("_bandar", {}).get("dominant")
            if not dom: return "—"
            icon = {'high':'🔴','med':'🟡','low':'⚪'}.get(dom['conf'], '')
            return f"{icon} {dom['label']}"
            
        def _tl(row): 
            sigs = row.get("_tape", {}).get("signals", [])
            return sigs[0][2] if sigs else "—"
            
        def _al(row): 
            stg = {'strong':'Kuat','moderate':'Sedang','weak':'Lemah'}.get(row.get('ADX Strength','weak'), '—')
            return f"{row['ADX']:.0f} {'▲' if row.get('ADX Bullish') else '▼'} ({stg})"

        tabel_rows = []
        for _, row in final_df.iterrows():
            tabel_rows.append({
                "Rating": row["Sistem Rating"],
                "🏆": "👑" if row["Ticker"] == best_ticker else "", 
                "Saham": row["Ticker"], "Harga Skrg": f"Rp {fmt_num(row['Live Price'])}",
                "Zona Beli": f"Rp {fmt_num(row['Buy Min'])} – {fmt_num(row['Buy Max'])}", "Target 1": f"Rp {fmt_num(row['TP1'])} ({row['Upside TP1']})",
                "Target 2": f"Rp {fmt_num(row['TP2'])} ({row['Upside TP2']})", "Target 3": f"Rp {fmt_num(row['TP3'])} ({row['Upside TP3']})",
                "Stop Loss": f"Rp {fmt_num(row['Stop Loss'])} ({row['Risk%']})", "R/R": row["R/R TP1"], "Score": row["Score"], "Grade": row["Grade"],
                "ADX": _al(row), "Risk Dyn": f"{row['Dyn Risk %']}%", "Lots": f"{int(row['Lots'])} lot",
                "Prob Entry": f"{row['Prob Entry']}%", "Prob TP1": f"{row['Prob TP1']}%", "Prob SL": f"{row['Prob SL']}%",
                "Confidence": row["Confidence"], "Status": _vl(row), "Sinyal Bandar": _bl(row), "Tape": _tl(row),
                "Alokasi": fmt_idr(row["Alokasi (Rp)"])
            })

        tabel_df = pd.DataFrame(tabel_rows)
        def _sr(row): 
            s = row["Status"]
            bg = "background-color: rgba(63,185,80,0.07)" if "Siap" in s else "background-color: rgba(227,179,65,0.07)" if "Tunggu" in s else "background-color: rgba(248,81,73,0.07)" if "Hindari" in s else ""
            return [bg] * len(row)
        
        st.dataframe(tabel_df.style.apply(_sr, axis=1).set_properties(**{"font-size": "0.82rem", "text-align": "left"}).set_table_styles([{"selector": "th", "props": [("font-size", "0.75rem"), ("text-transform", "uppercase"), ("letter-spacing", "0.4px"), ("color", "#8b949e")]}]), use_container_width=True, hide_index=True, height=min(80 + len(tabel_rows) * 38, 600))

    meta = st.session_state.get('scan_meta', {})
    with debug_ph.expander("🔬 Debug / Audit Scan", expanded=False):
        st.write(f"**Input:** {meta.get('total_input', 0)} saham | **Lolos:** {meta.get('lolos', 0)} | **Difilter:** {meta.get('difilter', 0)}")
        if meta.get('skipped'): st.dataframe(pd.DataFrame(list(meta['skipped'].items()), columns=["Ticker", "Alasan"]), use_container_width=True, height=200)
        else: st.caption("Semua saham lolos filter.")

elif st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] != trading_mode:
    st.warning("⚠️ Mode trading diubah. Klik **🚀 Jalankan Skrining** untuk memperbarui data.")
else:
    with debug_ph.expander("🔬 Debug / Audit Scan", expanded=False): st.caption("Jalankan skrining dulu.")
