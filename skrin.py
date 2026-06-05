import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
from datetime import datetime, timedelta

# =============================================================================
# 1. KONFIGURASI HALAMAN & CSS
# =============================================================================
st.set_page_config(
    page_title="Quant Trader - IDX Screener Ultra v4.0",
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
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. SESSION STATE
# =============================================================================
for key, default in [('raw_market_data', {}), ('last_loaded_mode', None)]:
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
    return tr.ewm(span=window, adjust=False).mean()

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
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)

def calculate_bb_squeeze(df: pd.DataFrame,
                          bb_window: int = 20, bb_std: float = 2.0,
                          kc_mult: float = 1.5, atr_window: int = 14) -> pd.Series:
    """
    Lazybear-style BB Squeeze:
    True  = BB berada DI DALAM Keltner Channel → kompresi (energi menumpuk).
    False = BB sudah keluar KC → squeeze release / breakout sedang terjadi.
    """
    basis   = df['Close'].rolling(bb_window).mean()
    bb_std_ = df['Close'].rolling(bb_window).std()
    bb_upper = basis + bb_std * bb_std_
    bb_lower = basis - bb_std * bb_std_

    atr = calculate_atr(df, window=atr_window)
    kc_upper = basis + kc_mult * atr
    kc_lower = basis - kc_mult * atr

    return (bb_upper < kc_upper) & (bb_lower > kc_lower)

def calculate_indicators(df: pd.DataFrame) -> dict:
    """
    Hitung semua indikator sekaligus dan kembalikan sebagai dict scalar
    untuk nilai terakhir + beberapa nilai historis yang dibutuhkan scoring.
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
    atr_pct     = atr_val / last_close if last_close > 0 else 0.0   # ATR sebagai % harga

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
    # Squeeze baru saja release = candle sebelumnya masih squeeze, sekarang tidak
    squeeze_release = (not in_squeeze) and bool(sq_series.iloc[-2]) if len(sq_series) > 1 else False

    # Volume spike vs MA-15
    vol_ma15    = float(volume.rolling(15).mean().iloc[-1])
    vol_last    = float(volume.iloc[-1])
    vol_spike   = vol_last / (vol_ma15 + 1e-9)

    # ADTV (MA-20 volume × harga)
    vol_ma20    = float(volume.rolling(20).mean().iloc[-1])
    adtv        = vol_ma20 * last_close

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
        return 25.0, "bull"   # Bullish penuh
    elif ind['above_ema50']:
        return 12.0, "bull"   # Di atas tren utama tapi EMA20 belum
    elif ind['above_ema20']:
        return 5.0,  "neut"   # EMA20 saja, tren utama masih bearish
    else:
        return 0.0,  "bear"   # Di bawah kedua EMA → hard filter

def score_rsi(ind: dict) -> tuple[float, str]:
    """
    B. RSI 14.
    - Zona ideal setup: 40–65 (tidak OB, masih ada ruang naik)
    - RSI sedang naik menambah poin
    - RSI > 75 = overbought → penalty besar (sinyal entry terlambat)
    - RSI < 30 = potensi reversal tapi berisiko, poin sedang
    """
    rsi = ind['rsi_val']
    if rsi > 75:                      # Overbought — entry terlambat
        return 2.0, "bear"
    elif 40 <= rsi <= 65:             # Zona sweet spot
        base = 20.0
        bonus = 5.0 if ind['rsi_rising'] else 0.0   # Momentum masih naik = bonus
        return min(base + bonus, 20.0), "bull"
    elif 65 < rsi <= 75:              # Kuat tapi mendekati OB
        return 10.0, "neut"
    elif 30 <= rsi < 40:              # Lemah tapi bisa reversal
        return 8.0, "neut"
    else:                             # RSI < 30 — terlalu lemah / downtrend
        return 4.0, "bear"

def score_cmf(ind: dict) -> tuple[float, str]:
    """
    C. CMF 20.
    Skala linier 0–25 untuk CMF positif.
    CMF negatif = distribusi institusional → skor minimal.
    """
    cmf = ind['cmf_val']
    if cmf > 0:
        base  = 25.0 * min(cmf / 0.25, 1.0)   # Saturasi di CMF = 0.25
        bonus = 2.0 if ind['cmf_rising'] else 0.0
        return min(base + bonus, 25.0), "bull"
    elif cmf > -0.05:
        return 5.0, "neut"    # CMF sedikit negatif — netral
    else:
        return 0.0, "bear"    # Distribusi kuat

def score_volume(ind: dict) -> tuple[float, str]:
    """D. Volume spike vs MA-15."""
    spike = ind['vol_spike']
    if spike >= 2.5:
        return 15.0, "bull"   # Lonjakan signifikan
    elif spike >= 1.5:
        return 15.0 * ((spike - 1.5) / 1.0 + 0.5), "bull"
    elif spike >= 1.2:
        return 7.0, "neut"    # Sedikit di atas rata-rata
    else:
        return 0.0, "neut"    # Volume biasa

def score_squeeze(ind: dict) -> tuple[float, str]:
    """
    E. Bollinger Band Squeeze.
    Squeeze release mendapat poin penuh — ini sinyal breakout paling kuat.
    Masih dalam squeeze mendapat poin sedang — potensi tapi belum terkonfirmasi.
    """
    if ind['squeeze_release']:
        return 15.0, "bull"   # Breakout dari kompresi
    elif ind['in_squeeze']:
        return 8.0, "neut"    # Masih kompresi — siap, tapi tunggu
    else:
        return 3.0, "neut"    # Normal, tidak ada sinyal khusus

def compute_total_score(ind: dict) -> tuple[float, dict]:
    """
    Gabungkan semua komponen. Kembalikan (total_score, breakdown_dict).
    Hard filter: jika trend bearish total (score_trend=0), cap score maksimal 40.
    """
    st_score, st_sig = score_trend(ind)
    rs_score, rs_sig = score_rsi(ind)
    cm_score, cm_sig = score_cmf(ind)
    vo_score, vo_sig = score_volume(ind)
    sq_score, sq_sig = score_squeeze(ind)

    total = st_score + rs_score + cm_score + vo_score + sq_score

    # Hard filter: saham di bawah EMA50 DAN EMA20 tidak boleh lolos ≥ 60
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
# Filosofi:
#   SL = last_close - (atr_mult × ATR)            → berbasis volatilitas nyata
#   TP1 menjamin R/R ≥ rr1 : 1 dari SL distance
#   TP2 menjamin R/R ≥ rr2 : 1 dari SL distance
#   Jika ATR terlalu kecil (misal saham konsolidasi ketat), SL minimal 0.5×ATR
#   agar tidak kena noise biasa.

INTRADAY_PARAMS = {
    'atr_window':  14,
    'atr_sl_mult': 1.5,    # SL = 1.5 × ATR di bawah entry
    'min_rr1':     1.5,    # TP1 minimal R/R 1.5:1
    'min_rr2':     2.5,    # TP2 minimal R/R 2.5:1
    'ts_rule':     "Trailing 1× ATR; geser ke BEP saat TP1 hit",
    'fixed_risk_pct': 3.0, # fallback jika ATR tidak valid
}

SWING_PARAMS = {
    'atr_window':  14,
    'atr_sl_mult': 2.0,    # SL = 2 × ATR — lebih longgar untuk swing
    'min_rr1':     2.0,    # TP1 minimal R/R 2:1
    'min_rr2':     3.5,    # TP2 minimal R/R 3.5:1
    'ts_rule':     "Set BEP saat TP1 hit; trailing 2× ATR",
    'fixed_risk_pct': 5.0,
}

def build_trade_plan(last_close: float, atr_val: float, mode_params: dict) -> dict:
    """
    Hitung level TP/SL dengan:
    1. SL berbasis ATR (volatilitas aktual)
    2. TP dijamin memenuhi minimum R/R ratio
    3. Fallback ke persen flat jika ATR tidak valid
    """
    sl_dist = atr_val * mode_params['atr_sl_mult']

    # Fallback safety: jika ATR terlalu kecil atau tidak valid
    min_sl_dist = last_close * (mode_params['fixed_risk_pct'] / 100.0) * 0.5
    sl_dist = max(sl_dist, min_sl_dist)

    stop_loss = last_close - sl_dist

    # TP dihitung dari jarak SL aktual, bukan dari persentase flat
    tp1_dist = sl_dist * mode_params['min_rr1']
    tp2_dist = sl_dist * mode_params['min_rr2']

    tp1 = last_close + tp1_dist
    tp2 = last_close + tp2_dist

    # Aktual R/R ratio (untuk display)
    rr1_actual = tp1_dist / sl_dist
    rr2_actual = tp2_dist / sl_dist

    return {
        'stop_loss': np.floor(stop_loss),
        'tp1':       np.ceil(tp1),
        'tp2':       np.ceil(tp2),
        'sl_dist':   sl_dist,
        'rr1':       round(rr1_actual, 2),
        'rr2':       round(rr2_actual, 2),
        'ts_rule':   mode_params['ts_rule'],
    }

# =============================================================================
# 7. DOWNLOAD ENGINE
# =============================================================================
def download_ticker_chunk(tickers: list, period_days: int, interval: str) -> dict:
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
        )
        if data.empty:
            raise ValueError("Empty response")

        if len(tickers) == 1:
            if 'Close' in data.columns:
                df_t = data.dropna(subset=['Close'])
                if not df_t.empty:
                    chunk_results[tickers[0]] = df_t
        else:
            available = data.columns.get_level_values(0).unique().tolist()
            for t in tickers:
                if t in available:
                    result = _safe_extract(data, t)
                    if result is not None:
                        chunk_results[t] = result

    except Exception:
        for t in tickers:
            try:
                df_s = yf.download(t, start=start_date, end=end_date,
                                   interval=interval, auto_adjust=True, progress=False)
                if not df_s.empty and 'Close' in df_s.columns:
                    df_c = df_s.dropna(subset=['Close'])
                    if not df_c.empty:
                        chunk_results[t] = df_c
            except Exception:
                continue

    return chunk_results

# =============================================================================
# 7b. LIVE PRICE FETCHER (fast_info — lebih aktual dari OHLCV batch)
# =============================================================================
def fetch_live_prices(tickers_jk: list) -> dict:
    """
    Ambil harga live via yf.Ticker.fast_info['last_price'].
    Jauh lebih aktual dari close OHLCV batch (yang bisa delayed 1 hari).
    Kembalikan dict: { 'HATM.JK': 320.0, ... }
    """
    result = {}
    for t in tickers_jk:
        try:
            info  = yf.Ticker(t).fast_info
            price = info.get('last_price') or info.get('lastPrice')
            if price and float(price) > 0:
                result[t] = float(price)
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
    MIN_CANDLES = 60   # Butuh minimal 60 candle agar EMA50 + indikator lain warm

    results = []

    for ticker, df in all_data.items():
        # ── Guard: data cukup ──────────────────────────────────────────────
        if len(df) < MIN_CANDLES:
            continue

        df = df.copy()

        # ── Hitung semua indikator ─────────────────────────────────────────
        try:
            ind = calculate_indicators(df)
        except Exception:
            continue

        last_close = ind['last_close']
        if not np.isfinite(last_close) or last_close <= 0:
            continue

        # ── Filter harga & likuiditas ──────────────────────────────────────
        if last_close < config['min_price'] or last_close > config['max_price']:
            continue
        if ind['adtv'] < config['min_adtv']:
            continue

        # ── Scoring ───────────────────────────────────────────────────────
        total_score, breakdown = compute_total_score(ind)
        if total_score < config['min_score_threshold']:
            continue

        # ── Grade label ───────────────────────────────────────────────────
        if total_score >= 80:
            grade = "A"
        elif total_score >= 65:
            grade = "B"
        else:
            grade = "C"

        # ── Trading plan ──────────────────────────────────────────────────
        plan = build_trade_plan(last_close, ind['atr_val'], mode_params)
        stop_loss = plan['stop_loss']
        tp1       = plan['tp1']
        tp2       = plan['tp2']

        # ── Buy range: ±0.5 ATR dari last_close (lebih realistis dari ±1% flat) ─
        buy_min = int(np.floor(last_close - 0.5 * ind['atr_val']))
        buy_max = int(np.ceil(last_close + 0.3 * ind['atr_val']))

        # ── Position sizing ───────────────────────────────────────────────
        loss_per_share = last_close - stop_loss
        if loss_per_share <= 0:
            continue

        rupiah_risk    = config['total_capital'] * (config['capital_risk_limit_pct'] / 100.0)
        calc_lots      = int(rupiah_risk / loss_per_share / 100)

        max_alloc      = config['total_capital'] * (config['max_capital_allocation_pct'] / 100.0)
        required_cap   = calc_lots * 100 * last_close
        if required_cap > max_alloc:
            calc_lots    = int(max_alloc / (100 * last_close))
            required_cap = calc_lots * 100 * last_close

        if calc_lots < 1:
            continue

        clean_ticker = ticker.split('.')[0]
        results.append({
            "Ticker":       clean_ticker,
            "_ticker_jk":  ticker,          # internal: dipakai fetch_live_prices, dihapus setelahnya
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
            "_breakdown":   breakdown,   # private — untuk render pills
        })

    if not results:
        return pd.DataFrame()

    # ── Fetch harga live untuk semua ticker yang lolos scoring ─────────────
    # Dilakukan SETELAH loop agar hanya fetch ticker yang benar-benar relevan
    passed_tickers_jk = [r["_ticker_jk"] for r in results]
    live_prices = fetch_live_prices(passed_tickers_jk)

    for r in results:
        lp = live_prices.get(r["_ticker_jk"])
        r["Live Price"] = int(round(lp)) if lp else r["Last Price"]
        r["Live Src"]   = "live" if lp else "delayed"
        del r["_ticker_jk"]   # bersihkan field internal

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

def _grade_badge(grade: str) -> str:
    cls = {"A": "grade-A", "B": "grade-B", "C": "grade-C"}.get(grade, "grade-C")
    return f'<span class="{cls}">Grade {grade}</span>'

def _price_status_html(live_price: int, ref_close: int, buy_min: int, buy_max: int, live_src: str) -> str:
    """
    Tampilkan harga live + ref close + status zona beli.
    live_src: 'live' = dari fast_info, 'delayed' = fallback ke OHLCV close
    """
    if buy_min <= live_price <= buy_max:
        color, icon, label = "#3fb950", "●", "Dalam Zona Beli"
    elif live_price < buy_min:
        color, icon, label = "#58a6ff", "↓", "Di Bawah Zona"
    else:
        color, icon, label = "#e3b341", "↑", "Di Atas Zona"

    src_label = "Live" if live_src == "live" else "Delayed"
    src_color = "#3fb950" if live_src == "live" else "#8b949e"

    # Tampilkan ref close hanya jika berbeda dari live price
    ref_note = ""
    if ref_close != live_price:
        diff     = live_price - ref_close
        diff_pct = diff / ref_close * 100
        sign     = "+" if diff >= 0 else ""
        ref_col  = "#3fb950" if diff >= 0 else "#f85149"
        ref_note = (
            f'<span style="font-size:0.68rem;color:{ref_col};margin-left:0.3rem;">'
            f'{sign}{diff_pct:.1f}% vs ref {ref_close:,}'.replace(",", ".") +
            f'</span>'
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


def render_trade_cards(df: pd.DataFrame, max_cards: int = 6):
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
                bd = row.get("_breakdown", {})

                # Bangun pill indikator
                def pill_from_bd(key, label):
                    if key not in bd:
                        return ""
                    score_val, sig = bd[key]
                    return _pill(f"{label} {score_val:.0f}", sig)

                pills_html = (
                    pill_from_bd("trend",   "EMA")
                    + pill_from_bd("rsi",   "RSI")
                    + pill_from_bd("cmf",   "CMF")
                    + pill_from_bd("volume","VOL")
                    + pill_from_bd("squeeze","SQZ")
                )

                html = (
                    f'<div class="metric-card">'

                    # Header: ticker + score + grade
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">'
                    f'  <span class="ticker">{row["Ticker"]}</span>'
                    f'  <div style="display:flex;gap:0.4rem;align-items:center;">'
                    f'    {_grade_badge(row["Grade"])}'
                    f'    <span class="score-badge">Score {row["Score"]}</span>'
                    f'  </div>'
                    f'</div>'

                    # Indicator pills
                    f'<div style="margin-bottom:0.5rem;">{pills_html}</div>'

                    # Harga live + status zona
                    f'{_price_status_html(row["Live Price"], row["Last Price"], row["Buy Min"], row["Buy Max"], row["Live Src"])}'

                    # Buy range
                    f'<div class="price-range">{int(row["Buy Min"])} – {int(row["Buy Max"])}</div>'
                    f'<div class="label" style="margin-bottom:0.6rem;">Area Rentang Buy · ATR {row["ATR"]}</div>'

                    # TP grid
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;'
                    f'margin-bottom:0.6rem;border-top:1px solid #30363d;padding-top:0.4rem;">'
                    f'  <div><div class="label">TP 1 <span class="rr-badge">({row["R/R TP1"]})</span></div>'
                    f'  <div class="tp">{int(row["TP1"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP1"]}</span></div></div>'
                    f'  <div><div class="label">TP 2 <span class="rr-badge">({row["R/R TP2"]})</span></div>'
                    f'  <div class="tp">{int(row["TP2"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP2"]}</span></div></div>'
                    f'</div>'

                    # SL + trailing
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.6rem;">'
                    f'  <div><div class="label">Stop Loss</div>'
                    f'  <div class="sl">{int(row["Stop Loss"])} <span style="font-size:0.68rem;opacity:0.8">{row["Risk%"]}</span></div></div>'
                    f'  <div><div class="label">Trailing Strategy</div>'
                    f'  <div class="ts-rule" style="font-size:0.78rem;">{row["TS Kriteria"]}</div></div>'
                    f'</div>'

                    # Lots + alokasi
                    f'<div style="border-top:1px solid #30363d;padding-top:0.4rem;'
                    f'display:grid;grid-template-columns:1fr 1fr;gap:0.3rem;font-size:0.75rem;">'
                    f'  <div><div class="label">Lots Berbasis Risiko</div>'
                    f'  <div style="color:#fff;font-weight:600">{int(row["Lots"])} Lot</div></div>'
                    f'  <div><div class="label">Maks Alokasi</div>'
                    f'  <div style="color:#58a6ff;font-weight:600">{fmt_idr(row["Alokasi (Rp)"])}</div></div>'
                    f'</div>'

                    f'</div>'
                )
                st.markdown(html, unsafe_allow_html=True)

# =============================================================================
# 10. SIDEBAR
# =============================================================================
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

    # Intraday: ambil 30 hari × 60m agar ada ≥ 200 candle untuk EMA50 warmup
    # Swing  : ambil 120 hari daily agar EMA50 cukup stabil
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
    render_trade_cards(final_df, max_cards=6)

    if not final_df.empty:
        st.markdown("### 📋 Tabel Lengkap")
        display_cols = [c for c in final_df.columns if not c.startswith("_") and c != "Live Src"]
        st.dataframe(final_df[display_cols], use_container_width=True)

elif st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] != trading_mode:
    st.warning("⚠️ Mode trading diubah. Klik **🚀 Jalankan Skrining** untuk memperbarui data.")
