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
# CHANGELOG AUDIT v6.0 (rombak dari v4.2)
# =============================================================================
# BUG KRITIS YANG DIPERBAIKI:
#  1. snap_to_tick(): tabel fraksi harga SALAH — ada tier fiktif Rp50 untuk
#     harga >=10000. Aturan resmi BEI (Kep-00023/BEI/04-2016, masih berlaku
#     per Kep-00055/BEI/03-2023) HANYA 5 tier, tier terakhir >=Rp5.000 = Rp25
#     berlaku TANPA BATAS ATAS. Saham >Rp10.000 (banyak blue-chip) selama ini
#     dapat level TP/SL/buy-zone yang TIDAK VALID di sistem JATS.
#  2. buy_max di-snap FLOOR ("ke bawah") dari last_close. Akibatnya saat harga
#     live gagal di-fetch dan fallback ke last_close, harga tersebut HAMPIR
#     SELALU jatuh di ATAS buy_max (karena floor-snap menggeser ke bawah),
#     membuat status selalu "waiting/chasing" walau seharusnya "valid".
#     Diverifikasi via simulasi: bug ini sistemik, mempengaruhi SEMUA saham
#     setiap kali live price tidak tersedia. Fix: snap CEIL untuk buy_max.
#  3. ema200_available nyaris tidak pernah True — window download swing
#     hanya 120 hari kalender (~85 trading day) < 200 yang dibutuhkan.
#     Bonus EMA200 di score_trend jadi dead code. Fix: window swing 400 hari.
#  4. calculate_adx() memicu RuntimeWarning "invalid value in divide" karena
#     np.where mengevaluasi cabang pembagian sebelum masking. Fix: denominator
#     di-guard dulu sebelum pembagian.
#  5. ADX dihitung tapi HANYA jadi modifier kecil di score_squeeze (+5 pt,
#     hanya aktif saat squeeze_release True — jarang terjadi). Padahal ADX
#     adalah indikator kekuatan tren yang valid dan seharusnya berbobot
#     nyata. Fix: ADX jadi komponen scoring independen (20 pt), bobot lain
#     diskalakan ulang agar total tetap 100.
#  6. Pill "ADX 25" di kartu trade tampil dengan style IDENTIK dengan pill
#     skor lain (EMA/RSI/CMF/VOL/SQZ) padahal isinya RAW INDICATOR VALUE,
#     bukan poin skor — membingungkan. Fix: setelah ADX jadi skor sungguhan
#     (poin 0-20), pill otomatis konsisten; raw reading ditampilkan terpisah.
#  7. pick_best_buy() bisa menahkotai saham yang harganya CHASING (di atas
#     zona beli, tidak actionable) sebagai "BEST BUY" walau scorenya lemah
#     (terverifikasi: score 29/100 tetap dimahkotai). Fix: kandidat chasing
#     dikeluarkan dari kandidasi Best Buy + minimum quality gate (score>=45).
#  8. Format angka tidak konsisten — Buy Zone/TP1/TP2/TP3/SL di kartu trade
#     tampil TANPA pemisah ribuan ("19150") sementara harga live di sebelahnya
#     pakai pemisah ("19.256"). Fix: format seragam di semua kartu.
#  9. estimate_trade_probabilities() dipanggil 2x per saham — hasil panggilan
#     pertama langsung dibuang/ditimpa setelah live price didapat. Fix:
#     hanya dihitung sekali, setelah live price diketahui.
#  10. Tidak ada filter kualitas data (saham suspend/zombie/data basi/OHLC
#      rusak) — sinyal bisa dihasilkan dari data yang secara fundamental
#      tidak bisa ditradingkan. Fix: tambah is_tradeable_stock().
# =============================================================================
# CHANGELOG AUDIT RONDE 2 — v6.1 (audit ulang menyeluruh atas v6.0)
# =============================================================================
# Catatan: audit ronde 2 TIDAK menemukan lagi bug fatal sekelas #1/#2 di atas
# (tabel tick salah, arah snap buy_max salah) — logika inti (scoring 6
# komponen, trading plan berbasis ATR, tick-compliance, tape/bandarmology)
# terbukti solid saat diuji ulang. Yang ditemukan kali ini lebih ke arah
# konsistensi, robustness, dan kelengkapan — semuanya dibuktikan lewat
# eksekusi kode nyata (bukan sekadar baca kode), sesuai standar audit yang
# sama dengan ronde 1:
#
#  R2-1. DRY violation: snap_to_tick() & idx_tick_of() punya tabel fraksi
#        harga yang terduplikasi independen — risiko keduanya diam-diam
#        tidak sinkron kalau salah satu diubah di masa depan. Fix:
#        idx_tick_of() jadi satu-satunya sumber, snap_to_tick() memanggilnya.
#  R2-2. (KRITIS, terbukti lewat eksekusi) Guard "buy_min <= stop_loss" &
#        "buy_max >= tp1" di build_trade_plan menambah/mengurangi tick MENTAH
#        tanpa snap ulang, dan tick yang dipakai berasal dari bracket
#        last_close — bukan bracket milik stop_loss/tp1 sendiri. Terbukti:
#        last_close=505 (tick=5), stop_loss=494 (tick=2) → guard lama hasilkan
#        buy_min=499, BUKAN kelipatan tick=2 di bracketnya sendiri (harga
#        ilegal di JATS). Fix: re-snap pakai tick milik bracket harga hasil,
#        urutan guard direstrukturisasi + collapse-safety terakhir.
#  R2-3. (Terbukti lewat eksekusi) _validity_rank (dipakai utk sorting) pakai
#        ambang SL sendiri (`live_price<=stop_loss`, tanpa buffer) yang BEDA
#        dari _check_signal_validity (buffer noise 1.5%) yang dipakai utk
#        status yang DITAMPILKAN. Terbukti: kasus live_price 1% di bawah SL
#        ditampilkan sbg "⏳ Tunggu Dulu" tapi disortir sbg peringkat expired
#        (rank=2) — status yang terlihat & urutan tampil saling bertentangan.
#        Fix: _validity_rank kini delegasi langsung ke _check_signal_validity.
#  R2-4. (KRITIS, terbukti lewat eksekusi) R/R TP1/2/3, Risk%, Upside% yang
#        DITAMPILKAN di kartu dihitung SEKALI di waktu scan (basis last_close/
#        buy_max) dan beku setelahnya, padahal estimator probabilitas di
#        bagian lain kartu yang SAMA sudah pakai live price. Terbukti dgn
#        angka: kartu menampilkan "R/R TP1 = 1:2.0" padahal kondisi live
#        sebenarnya "1:0.36" (harga naik 6% sejak scan) — selisih besar yang
#        bisa menyesatkan keputusan entry. Fix: compute_live_rr() sebagai
#        satu sumber kebenaran, dipakai baik oleh tampilan maupun estimator
#        probabilitas; utk kartu yang sudah expired, angka rencana-awal
#        (bukan live) tetap ditampilkan karena angka live tidak informatif
#        pada kondisi itu (rasio bisa meledak/terbalik).
#  R2-5. fetch_live_prices() tidak di-cache, padahal quant_strategy_engine()
#        dipanggil ulang pada SETIAP rerun Streamlit (termasuk interaksi
#        yang tidak terkait, misalnya geser slider risiko) — network call
#        baru ke Yahoo Finance setiap kali. Fix: cache TTL 20 detik.
#  R2-6. Panel Debug/Audit di-render sampai 2-3x lewat blok if/elif yang
#        tumpang tindih, dan pada kasus mode-mismatch bisa diam-diam
#        menampilkan data BASI dari mode sebelumnya tanpa label. Fix:
#        konsolidasi jadi satu blok, label staleness eksplisit.
#  R2-7. Ticker yang gagal DIUNDUH SAMA SEKALI (bukan gagal di filter
#        pipeline) tidak pernah tercatat di mana pun — cuma toast vague
#        "Data berhasil 15/20". Fix: dilacak eksplisit & digabung ke tabel
#        debug yang sama dgn alasan filter pipeline.
#  R2-8. Tidak ada disclaimer bahwa "Prob Entry/TP/SL" adalah skor heuristik,
#        bukan probabilitas statistik tervalidasi. Fix: caption singkat
#        ditambahkan di dekat kolom probabilitas.
#  R2-9. Robustness tambahan: klem Prob TP1>=TP2>=TP3 (monoton menurun
#        seiring jarak target) — menutup celah teoretis (sangat tidak
#        mungkin terjadi secara praktis, tapi murah utk dicegah) di
#        kombinasi ekstrem batas clamp.
#  R2-10. First-load state: sebelumnya tidak ada apa pun ditampilkan sebelum
#         scan pertama dijalankan. Ditambah info prompt yang ramah.
# =============================================================================

# =============================================================================
# 1. KONFIGURASI HALAMAN & CSS
# =============================================================================
st.set_page_config(
    page_title="Quant Trader - IDX Screener Ultra v6.1",
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
    /* ADX raw-reading info badge — sengaja dibedakan dari pill skor */
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
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. SESSION STATE
# =============================================================================
for key, default in [
    ('raw_market_data', {}), ('last_loaded_mode', None), ('scan_meta', {}),
    ('download_failures', {}),
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

def fmt_num(val) -> str:
    """Format angka dengan pemisah ribuan ala Indonesia (titik). Dipakai
    seragam di semua tempat (kartu trade, banner, tabel) — FIX #8."""
    try:
        return f"{int(round(float(val))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"

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
    """Average True Range — Wilder smoothing (alpha = 1/window)."""
    prev_close = df['Close'].shift(1)
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - prev_close).abs(),
        (df['Low']  - prev_close).abs(),
    ], axis=1).max(axis=1)
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
    """RSI Wilder. avg_loss=0 → RSI=100 (bukan NaN)."""
    delta = df['Close'].diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rsi = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, 1e-10)))
    return rsi.fillna(50.0)

def calculate_bb_squeeze(df: pd.DataFrame,
                          bb_window: int = 20, bb_std: float = 2.0,
                          kc_mult: float = 1.5, atr_window: int = 14) -> pd.Series:
    """
    Lazybear-style BB Squeeze:
    True  = BB berada DI DALAM Keltner Channel → kompresi (energi menumpuk).
    False = BB sudah keluar KC → squeeze release / breakout sedang terjadi.
    Fallback: jika data < bb_window, kembalikan Series False.
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
    Average Directional Index (ADX) — kekuatan tren + arah dominan (DI+/DI-).

    FIX #4: np.where lama tetap mengevaluasi pembagian 0/0 di cabang yang
    TIDAK dipilih, memicu RuntimeWarning meski hasil akhirnya benar. Sekarang
    denominator di-guard (np.maximum(..., epsilon)) SEBELUM pembagian, jadi
    tidak ada operasi 0/0 yang dievaluasi sama sekali.

    ADX > 25 = tren kuat | 18–25 = tren mulai terbentuk | < 18 = sideways.
    """
    if len(df) < window + 2:
        return {'adx': 0.0, 'di_plus': 0.0, 'di_minus': 0.0,
                'bullish_dir': False, 'strength': 'weak'}

    high  = df['High'].values.astype(float)
    low   = df['Low'].values.astype(float)
    close = df['Close'].values.astype(float)

    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low,
         np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))

    up_move   = high - np.roll(high, 1)
    down_move = np.roll(low, 1) - low
    up_move[0]   = 0.0
    down_move[0] = 0.0

    dm_plus  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    dm_minus = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    alpha = 1.0 / window
    atr_w = pd.Series(tr).ewm(alpha=alpha, adjust=False).mean().values
    dmp_w = pd.Series(dm_plus).ewm(alpha=alpha, adjust=False).mean().values
    dmm_w = pd.Series(dm_minus).ewm(alpha=alpha, adjust=False).mean().values

    safe_atr = np.maximum(atr_w, 1e-9)             # guard SEBELUM pembagian
    di_plus  = 100.0 * dmp_w / safe_atr
    di_minus = 100.0 * dmm_w / safe_atr

    safe_di_sum = np.maximum(di_plus + di_minus, 1e-9)   # guard lagi di sini
    dx    = 100.0 * np.abs(di_plus - di_minus) / safe_di_sum
    adx_s = pd.Series(dx).ewm(alpha=alpha, adjust=False).mean().values

    adx_val  = float(adx_s[-1])
    dip_val  = float(di_plus[-1])
    dim_val  = float(di_minus[-1])
    strength = 'strong' if adx_val >= 25 else ('moderate' if adx_val >= 18 else 'weak')

    return {
        'adx':         round(adx_val, 1),
        'di_plus':     round(dip_val, 1),
        'di_minus':    round(dim_val, 1),
        'bullish_dir': dip_val > dim_val,
        'strength':    strength,
    }


def calculate_indicators(df: pd.DataFrame) -> dict:
    """
    Hitung semua indikator sekaligus dan kembalikan sebagai dict scalar.
    Kalkulasi dilakukan sekali, bukan berulang di setiap fungsi scoring.
    """
    close  = df['Close']
    volume = df['Volume']

    ema200 = close.ewm(span=200, adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema20  = close.ewm(span=20,  adjust=False).mean()
    last_close = float(close.iloc[-1])
    ema200_available = len(close) >= 200
    above_ema200 = last_close > float(ema200.iloc[-1]) if ema200_available else False
    above_ema50  = last_close > float(ema50.iloc[-1])
    above_ema20  = last_close > float(ema20.iloc[-1])

    ema20_vals   = ema20.iloc[-4:].values
    ema20_rising = float(ema20_vals[-1]) > float(ema20_vals[-3]) if len(ema20_vals) >= 3 else False

    atr_series  = calculate_atr(df)
    atr_val     = float(atr_series.iloc[-1])
    atr_pct     = atr_val / last_close if last_close > 0 else 0.0

    cmf_series  = calculate_cmf(df)
    cmf_val     = float(cmf_series.iloc[-1])
    cmf_prev    = float(cmf_series.iloc[-2]) if len(cmf_series) > 1 else 0.0
    cmf_rising  = cmf_val > cmf_prev

    rsi_series  = calculate_rsi(df)
    rsi_val     = float(rsi_series.iloc[-1])
    rsi_prev    = float(rsi_series.iloc[-2]) if len(rsi_series) > 1 else 50.0
    rsi_rising  = rsi_val > rsi_prev

    sq_series   = calculate_bb_squeeze(df)
    in_squeeze  = bool(sq_series.iloc[-1])
    squeeze_release = (not in_squeeze) and bool(sq_series.iloc[-2]) if len(sq_series) > 1 else False

    # ADX — sekarang komponen scoring independen (lihat skema bobot di §5)
    adx_data = calculate_adx(df)

    vol_ma15  = float(volume.rolling(15).mean().iloc[-1])
    vol_last  = float(volume.iloc[-1])
    vol_spike = vol_last / max(vol_ma15, 1.0)

    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    adtv     = vol_ma20 * last_close

    if not np.isfinite(atr_val) or atr_val <= 0:
        raise ValueError(f"ATR tidak valid: {atr_val}")

    return {
        'last_close':       last_close,
        'ema200_available': ema200_available,
        'above_ema200':     above_ema200,
        'above_ema50':      above_ema50,
        'above_ema20':      above_ema20,
        'ema20_rising':     ema20_rising,
        'atr_val':          atr_val,
        'atr_pct':          atr_pct,
        'cmf_val':          cmf_val,
        'cmf_rising':       cmf_rising,
        'rsi_val':          rsi_val,
        'rsi_rising':       rsi_rising,
        'in_squeeze':       in_squeeze,
        'squeeze_release':  squeeze_release,
        'adx_val':          adx_data['adx'],
        'adx_di_plus':      adx_data['di_plus'],
        'adx_di_minus':     adx_data['di_minus'],
        'adx_bullish_dir':  adx_data['bullish_dir'],
        'adx_strength':     adx_data['strength'],
        'vol_spike':        vol_spike,
        'adtv':             adtv,
    }

# =============================================================================
# 4a. FILTER KUALITAS DATA (FIX #10 — baru)
# =============================================================================
def is_tradeable_stock(df: pd.DataFrame, last_close: float) -> tuple[bool, str]:
    """
    Saring saham yang secara fundamental tidak bisa/tidak layak ditradingkan
    sebelum masuk pipeline scoring, agar sinyal tidak dihasilkan dari data
    yang rusak atau dari saham yang sebenarnya sedang suspend/tidak aktif.

    Cek yang dilakukan (sengaja minimal & defensif — hindari false positive
    pada saham yang sekadar low-volatility/sideways):
    1. Volume 0 di 3 candle terakhir       → indikasi suspend/tidak ada transaksi
    2. Close identik di 5 candle terakhir   → tidak ada price discovery riil
    3. Data terlalu basi (>10 hari kalender sejak candle terakhir)
    4. High==Low di mayoritas 10 candle terakhir → data OHLC tidak wajar
    """
    if len(df) < 10:
        return False, "data terlalu pendek untuk cek kualitas"

    recent = df.tail(10)

    last3_vol = df['Volume'].tail(3)
    if (last3_vol <= 0).all():
        return False, "volume 0 di 3 candle terakhir (indikasi suspend)"

    last5_close = df['Close'].tail(5)
    if last5_close.nunique() == 1:
        return False, "harga stagnan 5 candle terakhir (indikasi tidak aktif)"

    try:
        last_date = df.index[-1]
        if hasattr(last_date, 'to_pydatetime'):
            last_date = last_date.to_pydatetime()
        if getattr(last_date, 'tzinfo', None) is not None:
            last_date = last_date.replace(tzinfo=None)
        days_stale = (datetime.now() - last_date).days
        if days_stale > 10:
            return False, f"data basi ({days_stale} hari sejak candle terakhir)"
    except Exception:
        pass

    rng_zero = (recent['High'] - recent['Low']) <= 0
    if rng_zero.sum() >= 7:
        return False, "data OHLC tidak wajar (High=Low di mayoritas candle)"

    if not np.isfinite(last_close) or last_close <= 0:
        return False, "harga tidak valid"

    return True, ""

# =============================================================================
# 4b. VOLUME CONTEXT — analisis candle terakhir
# =============================================================================
def analyse_volume_context(df: pd.DataFrame) -> dict:
    if len(df) < 5:
        return {'valid': False}

    row   = df.iloc[-1]
    o, h, l, c = float(row['Open']), float(row['High']), float(row['Low']), float(row['Close'])
    vol   = float(row['Volume'])
    rng   = h - l if h > l else 1e-9

    body      = abs(c - o)
    body_pct  = body / rng
    upper_sh  = h - max(c, o)
    lower_sh  = min(c, o) - l
    close_pos = (c - l) / rng

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

    signals = []

    last_vol_ratio = vol5[-1] / max(vol_ma, 1.0)
    last_range     = ranges5[-1]
    last_body      = abs(cl5[-1] - op5[-1])
    last_close_pos = (cl5[-1] - lo5[-1]) / max(last_range, 1e-9)

    if (last_vol_ratio > 2.5 and last_body / max(last_range, 1e-9) > 0.6
            and cl5[-1] > op5[-1] and last_close_pos > 0.7):
        signals.append(('buying_climax', 'distrib',
                        'Buying Climax', 'BC',
                        min(int(last_vol_ratio / 3.0 * 100), 90)))

    if (last_vol_ratio > 2.5 and last_body / max(last_range, 1e-9) > 0.6
            and cl5[-1] < op5[-1] and last_close_pos < 0.3):
        signals.append(('selling_climax', 'accum',
                        'Selling Climax', 'SC',
                        min(int(last_vol_ratio / 3.0 * 100), 90)))

    if (last_vol_ratio > 1.8 and last_close_pos > 0.55
            and abs(cl5[-1] - cl5[-2]) / max(atr5, 1e-9) < 0.5):
        signals.append(('absorption', 'accum',
                        'Absorption', 'ABS',
                        min(int(last_close_pos * last_vol_ratio / 2.5 * 100), 85)))

    if (last_vol_ratio > 1.8 and last_range < avg_range5 * 0.6):
        signals.append(('exhaustion', 'warn',
                        'Exhaustion', 'EXH',
                        min(int((avg_range5 / max(last_range, 1e-9)) * 20), 80)))

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
    if len(df) < 20:
        return {'signals': [], 'dominant': None, 'narasi_tech': '', 'narasi_plain': ''}

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

    for i in range(max(0, n-3), n):
        if (close[i] < close[i-1] and _close_pos(i) > 0.55 and _vol_ratio(i) > 1.4):
            cp, vr = _close_pos(i), _vol_ratio(i)
            conf = int(min((cp - 0.55)/0.45 * 50 + (vr - 1.4)/1.6 * 50, 95))
            signals.append({'key': 'accum_signal', 'style': 'accum', 'label': 'Akumulasi',
                             'short': 'ACCU', 'conf_pct': conf, 'conf': _conf_label(conf), 'candle_idx': i})
            break

    for i in range(max(0, n-3), n):
        if (close[i] > close[i-1] and _close_pos(i) < 0.45 and _vol_ratio(i) > 1.8):
            cp, vr = 1 - _close_pos(i), _vol_ratio(i)
            conf = int(min((cp - 0.55)/0.45 * 50 + (vr - 1.8)/2.2 * 50, 95))
            signals.append({'key': 'distrib_signal', 'style': 'distrib', 'label': 'Distribusi',
                             'short': 'DIST', 'conf_pct': conf, 'conf': _conf_label(conf), 'candle_idx': i})
            break

    tail5_vol   = vol_arr[-5:]
    tail5_close = close[-5:]
    vol_slightly_above = np.mean(tail5_vol) > vol_ma * 1.05 and np.mean(tail5_vol) < vol_ma * 1.5
    price_range_tight  = (max(tail5_close) - min(tail5_close)) / max(atr_val, 1e-9) < 1.2
    if vol_slightly_above and price_range_tight:
        conf = 68
        signals.append({'key': 'stealth_accum', 'style': 'accum', 'label': 'Akum. Senyap',
                         'short': 'STL', 'conf_pct': conf, 'conf': _conf_label(conf), 'candle_idx': last})

    if n >= 7:
        gap_up       = open_arr[last] > close[-2] * 1.005
        big_vol      = _vol_ratio(last) > 2.0
        was_sideways = (max(close[-7:-2]) - min(close[-7:-2])) / max(atr_val, 1e-9) < 2.0
        if gap_up and big_vol and was_sideways:
            vr   = _vol_ratio(last)
            conf = int(min(60 + (vr - 2.0)/3.0 * 35, 95))
            signals.append({'key': 'markup', 'style': 'purple', 'label': 'Markup Phase',
                             'short': 'MRK', 'conf_pct': conf, 'conf': _conf_label(conf), 'candle_idx': last})

    if n >= 3:
        prev_drop   = close[-2] - close[-3]
        today_recov = close[-1] - close[-2]
        drop_size   = abs(prev_drop) / max(atr_val, 1e-9)
        if (prev_drop < 0 and drop_size > 1.5 and today_recov > abs(prev_drop) * 0.6
                and _vol_ratio(last-1) > 1.5):
            conf = int(min(55 + drop_size * 8, 88))
            signals.append({'key': 'shakeout', 'style': 'warn', 'label': 'Shakeout',
                             'short': 'SKO', 'conf_pct': conf, 'conf': _conf_label(conf), 'candle_idx': last})

    signals.sort(key=lambda x: x['conf_pct'], reverse=True)
    dominant = signals[0] if signals else None
    narasi_tech, narasi_plain = _build_narasi(signals, dominant)

    return {'signals': signals, 'dominant': dominant,
            'narasi_tech': narasi_tech, 'narasi_plain': narasi_plain}


def _build_narasi(signals: list, dominant: dict | None) -> tuple[str, str]:
    if dominant is None:
        return ("Tidak ada sinyal price-action signifikan.",
                "Belum ada pola yang cukup kuat untuk dibaca.")

    key, conf = dominant['key'], dominant['conf_pct']
    narasi_map = {
        'accum_signal': (
            f"Candle turun namun close di upper-half dengan volume {conf}% di atas rata — indikasi penyerapan.",
            "Harga turun tapi ada yang beli kuat di bawah. Kemungkinan bandar sedang akumulasi."
        ),
        'distrib_signal': (
            "Candle naik namun close di lower-half + volume spike — pola distribusi institusional.",
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
    return narasi_map.get(key, ("Sinyal tidak dikenali.", "Pola belum terdefinisi."))


# =============================================================================
# 5. SCORING ENGINE (6 KOMPONEN BERBOBOT) — FIX #5
# =============================================================================
# Bobot total = 100 poin
# Komponen         Maks     Filosofi
# ─────────────────────────────────────────────────────
# A. Trend (EMA)    20 pt   Konfirmasi arah pasar utama
# B. Momentum (RSI) 18 pt   Kekuatan momentum, hindari OB
# C. Money Flow     20 pt   Tekanan beli institusional
# D. Vol Spike      12 pt   Partisipasi pasar
# E. BB Squeeze     10 pt   Potensi breakout terkompresi
# F. ADX            20 pt   Kekuatan + arah tren terverifikasi (BARU,
#                            sebelumnya cuma modifier kecil di komponen E)
# ─────────────────────────────────────────────────────
# Catatan audit: versi lama menghitung ADX tapi cuma dipakai sebagai bonus
# +5 di skor squeeze (hanya aktif saat squeeze_release True — kondisi yang
# jarang terjadi). Akibatnya ADX nyaris tidak pernah berdampak ke skor akhir
# meski tampil sebagai "pill" di setiap kartu. Sekarang ADX berdiri sendiri
# sebagai komponen scoring agar kekuatan tren benar-benar tersaring.

def score_trend(ind: dict) -> tuple[float, str]:
    """A. Trend filter EMA200 + EMA50 + EMA20 slope. Maks 20 poin."""
    above_200 = ind.get('above_ema200', False)
    ema200_ok = ind.get('ema200_available', False)
    above_50  = ind['above_ema50']
    above_20  = ind['above_ema20']
    slope_ok  = ind.get('ema20_rising', False)

    if above_50 and above_20:
        base  = 16.0
        bonus = (2.0 if ema200_ok and above_200 else 0.0) + (2.0 if slope_ok else 0.0)
        return min(base + bonus, 20.0), "bull"
    elif above_50:
        return 10.0, "bull"
    elif above_20:
        return 4.0, "neut"
    else:
        return 0.0, "bear"

def score_rsi(ind: dict) -> tuple[float, str]:
    """
    B. RSI 14. Maks 18 poin.
    Zona ideal 40–65 → base 12-15 (linear) + bonus rising 3 = maks 18.
    Bonus rising HANYA aktif di zona sweet spot.
    """
    rsi = ind['rsi_val']
    if rsi > 75:
        return 2.0, "bear"
    elif 40 <= rsi <= 65:
        base  = 12.0 + (rsi - 40) / 25.0 * 3.0
        bonus = 3.0 if ind['rsi_rising'] else 0.0
        return min(base + bonus, 18.0), "bull"
    elif 65 < rsi <= 75:
        return 9.0, "neut"
    elif 30 <= rsi < 40:
        return 7.0, "neut"
    else:
        return 3.0, "bear"

def score_cmf(ind: dict) -> tuple[float, str]:
    """C. CMF. Maks 20 poin — skala linier untuk CMF positif."""
    cmf = ind['cmf_val']
    if cmf > 0:
        base  = 20.0 * min(cmf / 0.25, 1.0)
        bonus = 1.5 if ind['cmf_rising'] else 0.0
        return min(base + bonus, 20.0), "bull"
    elif cmf > -0.05:
        return 4.0, "neut"
    else:
        return 0.0, "bear"

def score_volume(ind: dict) -> tuple[float, str]:
    """D. Volume spike vs MA-15. Maks 12 poin."""
    spike = ind['vol_spike']
    if spike >= 2.5:
        return 12.0, "bull"
    elif spike >= 1.5:
        score = min(6.0 + 6.0 * ((spike - 1.5) / 1.0), 12.0)
        return score, "bull"
    elif spike >= 1.2:
        return 4.0, "neut"
    else:
        return 0.0, "neut"

def score_squeeze(ind: dict) -> tuple[float, str]:
    """
    E. Bollinger Band Squeeze. Maks 10 poin.
    Tidak lagi bercampur dengan ADX (lihat score_adx) — pemisahan ini
    membuat setiap komponen independen dan lebih mudah diaudit.
    """
    if ind['squeeze_release']:
        return 10.0, "bull"
    elif ind['in_squeeze']:
        return 6.0, "neut"
    else:
        return 2.0, "neut"

def score_adx(ind: dict) -> tuple[float, str]:
    """
    F. ADX — kekuatan tren + arah dominan (DI+/DI-). Maks 20 poin. (BARU)

    ADX kuat (>=25) + arah bullish (DI+ > DI-)   → 20 (skor maksimal)
    ADX kuat tapi arah bearish                    → 4  (tren kuat tapi turun)
    ADX moderat (18-25) + bullish                 → 13
    ADX moderat + bearish                         → 7
    ADX lemah (<18, sideways)                     → 8  (netral — arah tidak
                                                          reliable saat tren lemah)
    """
    strength = ind.get('adx_strength', 'weak')
    bullish  = ind.get('adx_bullish_dir', False)

    if strength == 'strong':
        base = 20.0 if bullish else 4.0
    elif strength == 'moderate':
        base = 13.0 if bullish else 7.0
    else:
        base = 8.0

    sig = "bull" if (bullish and strength != 'weak') else ("bear" if strength == 'strong' else "neut")
    return base, sig

def compute_total_score(ind: dict) -> tuple[float, dict]:
    """
    Gabungkan 6 komponen. Hard filter: trend bearish total → cap skor.
    """
    st_score, st_sig = score_trend(ind)
    rs_score, rs_sig = score_rsi(ind)
    cm_score, cm_sig = score_cmf(ind)
    vo_score, vo_sig = score_volume(ind)
    sq_score, sq_sig = score_squeeze(ind)
    ax_score, ax_sig = score_adx(ind)

    total = st_score + rs_score + cm_score + vo_score + sq_score + ax_score

    if not ind['above_ema50'] and not ind['above_ema20']:
        total = min(total, 40.0)
    if ind.get('ema200_available', False) and not ind.get('above_ema200', False) and not ind['above_ema50']:
        total = min(total, 35.0)

    breakdown = {
        'trend':   (round(st_score, 1), st_sig),
        'rsi':     (round(rs_score, 1), rs_sig),
        'cmf':     (round(cm_score, 1), cm_sig),
        'volume':  (round(vo_score, 1), vo_sig),
        'squeeze': (round(sq_score, 1), sq_sig),
        'adx':     (round(ax_score, 1), ax_sig),
    }
    return round(total, 1), breakdown

# =============================================================================
# 6. TRADING PLAN: ATR-BASED + MINIMUM R/R GUARANTEE
# =============================================================================
INTRADAY_PARAMS = {
    'atr_window':       14,
    'atr_sl_mult':      1.5,
    'min_rr1':          1.5,
    'min_rr2':          2.5,
    'min_rr3':          4.0,
    'ts_rule':          "Trailing 1× ATR; geser ke BEP saat TP1 hit",
    'fixed_risk_pct':   3.0,
    'buy_zone_atr_mult': 0.35,   # lebar zona beli lebih ketat untuk fast trade
}

SWING_PARAMS = {
    'atr_window':       14,
    'atr_sl_mult':       2.0,
    'min_rr1':           2.0,
    'min_rr2':           3.5,
    'min_rr3':           5.5,
    'ts_rule':          "Set BEP saat TP1 hit; trailing 2× ATR menuju TP2",
    'fixed_risk_pct':    5.0,
    'buy_zone_atr_mult': 0.5,    # lebar zona beli standar untuk swing
}

def idx_tick_of(price: float) -> int:
    """
    Satu-satunya sumber kebenaran (single source of truth) untuk fraksi
    harga IDX. Sebelumnya tabel ini terduplikasi di dua fungsi berbeda
    (snap_to_tick + idx_tick_of) — risiko nyata: kalau regulasi BEI berubah
    lagi di masa depan dan hanya satu tempat yang di-update, keduanya jadi
    tidak sinkron secara diam-diam. AUDIT RONDE 2 — FIX DRY.

    Fraksi harga IDX (BEI) yang benar (Kep-00023/BEI/04-2016, dikonfirmasi
    masih berlaku per Kep-00055/BEI/03-2023):
    < 200        → Rp1
    200 – 500    → Rp2
    500 – 2.000  → Rp5
    2.000 – 5.000→ Rp10
    >= 5.000     → Rp25  (tidak ada tier lebih lanjut, termasuk saham >Rp10rb)
    """
    p = float(price)
    if p < 200: return 1
    if p < 500: return 2
    if p < 2000: return 5
    if p < 5000: return 10
    return 25


def snap_to_tick(price: float, direction: str = "floor") -> int:
    """
    Snap harga ke fraksi harga IDX yang valid, memakai idx_tick_of() sebagai
    satu-satunya sumber tabel tick (lihat AUDIT RONDE 2 — FIX DRY di atas).
    direction: "floor" membulatkan ke bawah, "ceil" ke atas.
    """
    p = float(price)
    tick = idx_tick_of(p)
    if direction == "ceil":
        return int(np.ceil(p / tick) * tick)
    else:
        return int(np.floor(p / tick) * tick)


def build_trade_plan(last_close: float, atr_val: float, mode_params: dict) -> dict:
    """
    Hitung level TP/SL + zona beli, semua di-snap ke fraksi harga IDX valid.

    FIX #2 (ronde 1, tetap berlaku): buy_max di-snap CEIL (bukan floor) agar
    last_close selalu masuk zona buy_min..buy_max ketika live price tidak
    tersedia dan fallback ke last_close.

    AUDIT RONDE 2 — FIX BARU (kritis, terbukti lewat eksekusi nyata):
    Guard "buy_min <= stop_loss" dan "buy_max >= tp1" versi sebelumnya
    menambah/mengurangi tick MENTAH (`stop_loss + tick`) tanpa snap ulang,
    dan tick yang dipakai berasal dari bracket last_close — bukan bracket
    milik stop_loss/tp1 itu sendiri. Saat stop_loss atau tp1 jatuh di
    bracket fraksi-harga yang BEDA dari last_close (umum terjadi karena
    ATR/RR bisa membawa harga melewati batas Rp200/500/2.000/5.000), hasil
    penjumlahan itu bisa TIDAK valid di grid IDX. Contoh terverifikasi:
    last_close=505 (tick=5), stop_loss=494 (tick=2) → guard lama
    menghasilkan buy_min = 494+5 = 499, padahal 499 BUKAN kelipatan tick=2
    di bracket miliknya sendiri (<500) — harga ilegal yang akan
    dibulatkan paksa atau ditolak oleh JATS.

    Fix: setiap guard sekarang men-snap ulang memakai tick milik bracket
    HARGA HASIL itu sendiri, dan urutan guard direstrukturisasi supaya
    setiap invarian (buy_max < tp1, buy_min > stop_loss) berlaku independen
    dari efek samping guard lainnya, ditutup dengan collapse-safety terakhir.

    Partial Exit Plan:
    - TP1 → exit 40% posisi, geser SL ke BEP
    - TP2 → exit 40% posisi
    - TP3 → exit sisa (20%) atau trailing stop
    """
    sl_dist     = atr_val * mode_params['atr_sl_mult']
    min_sl_dist = last_close * (mode_params['fixed_risk_pct'] / 100.0) * 0.5
    sl_dist     = max(sl_dist, min_sl_dist)

    stop_loss_raw = last_close - sl_dist
    if stop_loss_raw <= 0:
        sl_dist       = last_close * 0.95
        stop_loss_raw = last_close - sl_dist

    stop_loss = snap_to_tick(stop_loss_raw, "floor")

    sl_dist_actual = last_close - stop_loss
    if sl_dist_actual <= 0:
        sl_dist_actual = sl_dist

    tp1_dist = sl_dist_actual * mode_params['min_rr1']
    tp2_dist = sl_dist_actual * mode_params['min_rr2']
    tp3_dist = sl_dist_actual * mode_params['min_rr3']

    tp1 = snap_to_tick(last_close + tp1_dist, "ceil")
    tp2 = snap_to_tick(last_close + tp2_dist, "ceil")
    tp3 = snap_to_tick(last_close + tp3_dist, "ceil")

    rr1_actual = round((tp1 - last_close) / sl_dist_actual, 2)
    rr2_actual = round((tp2 - last_close) / sl_dist_actual, 2)
    rr3_actual = round((tp3 - last_close) / sl_dist_actual, 2)

    # ── Zona beli ────────────────────────────────────────────────────────
    buy_atr_mult = mode_params.get('buy_zone_atr_mult', 0.5)
    buy_min_raw  = last_close - buy_atr_mult * atr_val
    buy_max_raw  = last_close

    buy_min = snap_to_tick(buy_min_raw, "floor")
    buy_max = snap_to_tick(buy_max_raw, "ceil")

    # Guard 1 — buy_max tidak boleh menyentuh/melewati tp1. Dicek LEBIH DULU
    # dan independen dari guard SL, memakai tick milik bracket tp1 sendiri,
    # lalu di-snap ulang supaya hasilnya selalu valid di grid IDX.
    if buy_max >= tp1:
        tp1_tick = idx_tick_of(tp1)
        buy_max  = snap_to_tick(tp1 - tp1_tick, "floor")

    # Guard 2 — buy_min tidak boleh di bawah/sama dengan stop_loss, memakai
    # tick milik bracket stop_loss sendiri, lalu di-snap ulang (ceil) agar
    # valid di grid IDX-nya sendiri, bukan grid milik last_close.
    if buy_min <= stop_loss:
        sl_tick = idx_tick_of(stop_loss)
        buy_min = snap_to_tick(stop_loss + sl_tick, "ceil")

    # Guard 3 — collapse-safety terakhir: kalau kedua guard di atas saling
    # bertabrakan (buy_min naik melewati buy_max yang sudah diciutkan oleh
    # guard 1 — skenario ekstrem, praktiknya nyaris mustahil berkat floor
    # min_sl_dist, tapi tetap dijaga defensif), ciutkan jadi satu titik harga.
    if buy_max < buy_min:
        buy_max = buy_min

    partial_plan = "TP1: exit 40% → geser SL ke BEP | TP2: exit 40% | TP3/Trail: sisa 20%"

    return {
        'stop_loss':    float(stop_loss),
        'tp1':          float(tp1),
        'tp2':          float(tp2),
        'tp3':          float(tp3),
        'buy_min':      float(buy_min),
        'buy_max':      float(buy_max),
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
    start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
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
            timeout=30,
        )
        if data.empty:
            raise ValueError("Empty response")

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
# 7b. LIVE PRICE FETCHER (paralel)
# =============================================================================
def _fetch_one_live(ticker: str) -> tuple[str, float | None]:
    try:
        info  = yf.Ticker(ticker).fast_info
        price = info.get('last_price') or info.get('lastPrice')
        if price and float(price) > 0:
            return ticker, float(price)
    except Exception:
        pass
    return ticker, None

def fetch_live_prices(tickers_jk: list, max_workers: int = 8) -> dict:
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


@st.cache_data(ttl=20, show_spinner=False)
def _cached_fetch_live_prices(tickers_tuple: tuple) -> dict:
    """
    AUDIT RONDE 2 — FIX: Streamlit menjalankan ulang SELURUH script pada
    setiap interaksi widget apa pun (termasuk yang tidak terkait, misalnya
    menggeser slider risiko atau membuka expander debug). Tanpa cache,
    quant_strategy_engine() — dan fetch_live_prices() di dalamnya — akan
    menghasilkan panggilan network baru ke Yahoo Finance SETIAP kali,
    walau data pasar (raw_market_data) tidak berubah sama sekali. TTL 20
    detik cukup untuk menyerap rentetan interaksi UI beruntun tanpa
    membanjiri network, sambil tetap me-refresh harga secara berkala.
    """
    return fetch_live_prices(list(tickers_tuple))

# =============================================================================
# 8. MAIN STRATEGY ENGINE
# =============================================================================
def quant_strategy_engine(all_data: dict, config: dict, trading_mode: str) -> pd.DataFrame:
    """
    Pipeline:
    1. Filter panjang data & kualitas data (is_tradeable_stock — FIX #10)
    2. Hitung indikator (termasuk ADX yang sudah diperbaiki — FIX #4)
    3. Scoring 6 komponen (termasuk ADX sungguhan — FIX #5)
    4. Trading plan ATR-based dengan zona beli yang sudah diperbaiki (FIX #2)
    5. Position sizing
    6. Fetch live price, lalu hitung probabilitas SEKALI saja (FIX #9)
    """
    mode_params = INTRADAY_PARAMS if trading_mode == "Intraday (Fast Trade)" else SWING_PARAMS
    MIN_CANDLES = 60

    results = []
    skipped_reason = {}

    for ticker, df in all_data.items():
        if len(df) < MIN_CANDLES:
            skipped_reason[ticker] = f"candle kurang ({len(df)} < {MIN_CANDLES})"
            continue

        df = df.copy()

        try:
            last_close_raw = float(df['Close'].iloc[-1])
        except Exception:
            skipped_reason[ticker] = "harga tidak terbaca"
            continue

        # FIX #10: filter kualitas data SEBELUM komputasi indikator
        tradeable, reason = is_tradeable_stock(df, last_close_raw)
        if not tradeable:
            skipped_reason[ticker] = reason
            continue

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

        vol_ctx = analyse_volume_context(df)
        tape    = analyse_tape(df)
        bandar  = analyse_bandarmology(df)

        plan      = build_trade_plan(last_close, ind['atr_val'], mode_params)
        stop_loss = plan['stop_loss']
        tp1, tp2, tp3 = plan['tp1'], plan['tp2'], plan['tp3']
        buy_min, buy_max = plan['buy_min'], plan['buy_max']

        entry_ref      = float(buy_max)
        loss_per_share = entry_ref - stop_loss
        if loss_per_share <= 0:
            skipped_reason[ticker] = "loss_per_share ≤ 0"
            continue

        rupiah_risk  = config['total_capital'] * (config['capital_risk_limit_pct'] / 100.0)
        calc_lots    = int(rupiah_risk / loss_per_share / 100)

        max_alloc    = config['total_capital'] * (config['max_capital_allocation_pct'] / 100.0)
        required_cap = calc_lots * 100 * entry_ref
        if required_cap > max_alloc:
            calc_lots    = int(max_alloc / (100 * entry_ref))
            required_cap = calc_lots * 100 * entry_ref

        if calc_lots < 1:
            skipped_reason[ticker] = "modal tidak cukup untuk 1 lot"
            continue

        clean_ticker = ticker.split('.')[0]
        tv_link = f"https://www.tradingview.com/chart/?symbol=IDX%3A{clean_ticker}"

        # FIX #9: probabilitas TIDAK dihitung di sini lagi — baru dihitung
        # sekali setelah live price diketahui (lihat blok di bawah), agar
        # tidak ada komputasi yang langsung dibuang.
        results.append({
            "Ticker":       clean_ticker,
            "_ticker_jk":   ticker,
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
            "ATR":          round(ind['atr_val'], 1),
            "RSI":          round(ind['rsi_val'], 1),
            "CMF":          round(ind['cmf_val'], 3),
            "ADX":          ind['adx_val'],
            "ADX Strength": ind['adx_strength'],
            "ADX Bullish":  ind['adx_bullish_dir'],
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

    st.session_state['scan_meta'] = {
        'total_input': len(all_data),
        'lolos':       len(results),
        'difilter':    len(skipped_reason),
        'skipped':     skipped_reason,
    }

    if not results:
        return pd.DataFrame()

    passed_tickers_jk = [r["_ticker_jk"] for r in results]
    live_prices = _cached_fetch_live_prices(tuple(sorted(passed_tickers_jk)))

    for r in results:
        lp = live_prices.get(r["_ticker_jk"])
        if lp and np.isfinite(float(lp)) and float(lp) > 0:
            r["Live Price"] = int(round(float(lp)))
            r["Live Src"]   = "live"
        else:
            r["Live Price"] = int(r["Last Price"])
            r["Live Src"]   = "delayed"

        # AUDIT RONDE 2 — FIX: selaraskan Risk%/Upside/R-R yang TAMPIL dengan
        # harga LIVE saat ini. Sebelumnya nilai ini beku sejak waktu scan
        # (berbasis buy_max/last_close) sementara estimator probabilitas di
        # bawah sudah pakai live price — dua bagian dari kartu yang sama bisa
        # cerita beda soal risk/reward yang sama persis. Dikecualikan untuk
        # kartu yang SUDAH expired (live price menembus SL lebih dari buffer
        # noise 1.5%): di kondisi itu angka live-based bisa meledak/terbalik
        # dan tidak informatif, jadi tetap tampilkan angka RENCANA AWAL
        # (dari waktu scan) — selaras dengan kartu yang memang didim & diberi
        # banner peringatan.
        live_price_f = float(r["Live Price"])
        stop_loss_f  = float(r["Stop Loss"])
        is_expired_now = live_price_f <= stop_loss_f * (1 - 0.015)

        if not is_expired_now:
            live_rr = compute_live_rr(live_price_f, stop_loss_f, float(r["TP1"]), float(r["TP2"]), float(r["TP3"]))
            risk_pct_display = max(live_rr['risk_pct'], 0.0)
            r["Risk%"]      = f"-{round(risk_pct_display, 1)}%"
            r["Upside TP1"] = f"{'+' if live_rr['up1_pct'] >= 0 else ''}{round(live_rr['up1_pct'], 1)}%"
            r["Upside TP2"] = f"{'+' if live_rr['up2_pct'] >= 0 else ''}{round(live_rr['up2_pct'], 1)}%"
            r["Upside TP3"] = f"{'+' if live_rr['up3_pct'] >= 0 else ''}{round(live_rr['up3_pct'], 1)}%"
            r["R/R TP1"]    = f"1:{round(live_rr['rr1'], 2)}"
            r["R/R TP2"]    = f"1:{round(live_rr['rr2'], 2)}"
            r["R/R TP3"]    = f"1:{round(live_rr['rr3'], 2)}"
        # else: biarkan nilai rencana-awal (dari build_trade_plan) tetap tampil

        probs = estimate_trade_probabilities(
            score=r["Score"], grade=r["Grade"], live_price=float(r["Live Price"]),
            buy_min=float(r["Buy Min"]), buy_max=float(r["Buy Max"]),
            stop_loss=float(r["Stop Loss"]), tp1=float(r["TP1"]), tp2=float(r["TP2"]), tp3=float(r["TP3"]),
            atr_val=float(r["ATR"]), ind=r.get("_ind", {}), vol_ctx=r.get("_vol_ctx", {}),
            tape=r.get("_tape", {}), bandar=r.get("_bandar", {}),
        )
        r.update(probs)
        del r["_ticker_jk"]

    df_out = pd.DataFrame(results)

    def _validity_rank(row) -> int:
        """
        AUDIT RONDE 2 — FIX (terbukti lewat eksekusi nyata): versi lama
        memakai ambang sendiri (`live_price <= stop_loss`, tanpa buffer),
        BEDA dari _check_signal_validity() yang punya toleransi noise 1.5%.
        Akibatnya sebuah kartu bisa menampilkan status "⏳ Tunggu Dulu"
        (karena _check_signal_validity masih mentolerir) tapi disortir
        seakan-akan "🚫 Hindari" (expired) — status yang terlihat dan urutan
        tampil jadi tidak konsisten satu sama lain. Fix: delegasikan
        LANGSUNG ke _check_signal_validity() sebagai satu-satunya sumber
        kebenaran, supaya keduanya tidak mungkin lagi berbeda pendapat.
        """
        v = _check_signal_validity(
            row.get("Live Price", 0), row.get("Stop Loss", 0),
            row.get("Buy Min", 0), row.get("Buy Max", 0),
        )
        return {"valid": 0, "waiting": 1, "expired": 2}[v["status"]]

    df_out["_validity_rank"] = df_out.apply(_validity_rank, axis=1)
    return (
        df_out
        .sort_values(by=["_validity_rank", "Prob Entry", "Score"], ascending=[True, False, False])
        .drop(columns=["_validity_rank"])
        .reset_index(drop=True)
    )

# =============================================================================
# 9. RENDER HELPERS
# =============================================================================
def _pill(label: str, signal: str) -> str:
    return f'<span class="ind-pill ind-{signal}">{label}</span>'

def _tape_pill(short: str, style: str, conf_pct: int) -> str:
    return f'<span class="tape-pill tape-{style}">{short} {conf_pct}%</span>'

def _conf_badge(conf: str) -> str:
    cls = {'high': 'conf-hi', 'med': 'conf-med', 'low': 'conf-lo'}.get(conf, 'conf-lo')
    label = {'high': '▲ Tinggi', 'med': '◆ Sedang', 'low': '● Rendah'}.get(conf, '—')
    return f'<span class="{cls}">{label}</span>'

def _adx_info_badge(adx_val: float, strength: str, bullish: bool) -> str:
    """
    Badge kecil menampilkan RAW ADX reading (bukan poin skor) — terpisah
    dari pill skor agar tidak ambigu (FIX #6).
    """
    dir_icon = "▲" if bullish else "▼"
    strength_label = {"strong": "Kuat", "moderate": "Sedang", "weak": "Lemah"}.get(strength, "—")
    return f'<span class="adx-info">ADX {adx_val:.0f} {dir_icon} {strength_label}</span>'

def _render_volume_ctx_html(vc: dict) -> str:
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
    parts = []

    tape_sigs = tape.get('signals', [])
    if tape_sigs:
        pills_html = ''.join(_tape_pill(s[3], s[1], s[4]) for s in tape_sigs[:4])
        parts.append(
            f'<div style="margin-bottom:0.25rem;">'
            f'<span style="font-size:0.6rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;margin-right:0.3rem;">Tape</span>'
            f'{pills_html}</div>'
        )

    bandar_sigs = bandar.get('signals', [])
    if bandar_sigs:
        pills_html = ''.join(_tape_pill(s['short'], s['style'], s['conf_pct']) for s in bandar_sigs[:3])
        dominant = bandar.get('dominant')
        conf_badge = _conf_badge(dominant['conf']) if dominant else ''
        parts.append(
            f'<div style="display:flex;align-items:center;gap:0.3rem;flex-wrap:wrap;margin-bottom:0.25rem;">'
            f'<span style="font-size:0.6rem;color:#8b949e;text-transform:uppercase;letter-spacing:0.4px;">Bandar</span>'
            f'{pills_html}{conf_badge}</div>'
        )

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
    return f'<div class="section-divider"></div><div style="margin-bottom:0.4rem;">' + ''.join(parts) + '</div>'

def _grade_badge(grade: str) -> str:
    cls = {"A": "grade-A", "B": "grade-B", "C": "grade-C"}.get(grade, "grade-C")
    return f'<span class="{cls}">Grade {grade}</span>'

def _price_status_html(live_price: int, ref_close: int, buy_min: int, buy_max: int, live_src: str) -> str:
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
        ref_note = (
            f'<span style="font-size:0.68rem;color:{ref_col};margin-left:0.3rem;">'
            f'{sign}{diff_pct:.1f}% vs ref {fmt_num(ref_close)}</span>'
        )

    return (
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:0.4rem;padding:0.35rem 0.6rem;'
        f'background:rgba(255,255,255,0.04);border-radius:6px;'
        f'border-left:3px solid {color};">'
        f'  <div style="display:flex;align-items:baseline;gap:0.4rem;flex-wrap:wrap;">'
        f'    <span style="font-size:1.3rem;font-weight:800;color:{color};">'
        f'      {fmt_num(live_price)}'
        f'    </span>'
        f'    {ref_note}'
        f'  </div>'
        f'  <div style="text-align:right;">'
        f'    <div style="font-size:0.65rem;color:{src_color};font-weight:700;">{src_label}</div>'
        f'    <div style="font-size:0.65rem;color:{color};font-weight:600;">{icon} {label}</div>'
        f'  </div>'
        f'</div>'
    )


# =============================================================================
# 10. SIGNAL VALIDITY CHECK
# =============================================================================
def _check_signal_validity(live_price: int, stop_loss: int, buy_min: int, buy_max: int) -> dict:
    """
    'valid'   : harga di dalam zona beli, di atas SL → siap entry
    'waiting' : harga di bawah ATAU di atas zona, tapi masih di atas SL
    'expired' : harga menembus SL dengan margin > 1.5% (buffer noise data)
    """
    SL_BUFFER_PCT = 0.015
    expired_threshold = stop_loss * (1 - SL_BUFFER_PCT)

    if live_price <= expired_threshold:
        gap_pct = round((stop_loss - live_price) / stop_loss * 100, 1)
        return {
            'status':   'expired',
            'title':    '⚠️ Sinyal Tidak Valid — Harga Breakdown',
            'detail':   f'Harga ({fmt_num(live_price)}) sudah {gap_pct}% di bawah SL ({fmt_num(stop_loss)}). Jangan entry — sinyal dihitung saat kondisi berbeda.',
            'action':   'Tunggu konfirmasi reversal atau skip saham ini.',
            'card_cls': 'signal-expired', 'banner_cls': 'expired-banner', 'title_color': '#f85149',
        }
    elif live_price < buy_min:
        gap_pct = round((buy_min - live_price) / buy_min * 100, 1)
        return {
            'status':   'waiting',
            'title':    '⏳ Harga di Bawah Zona Beli',
            'detail':   f'Harga ({fmt_num(live_price)}) masih {gap_pct}% di bawah zona ({fmt_num(buy_min)}–{fmt_num(buy_max)}). SL masih aman — pantau, jangan entry dulu.',
            'action':   'Entry hanya jika harga masuk zona beli.',
            'card_cls': 'signal-waiting', 'banner_cls': 'waiting-banner', 'title_color': '#e3b341',
        }
    elif live_price > buy_max:
        gap_pct = round((live_price - buy_max) / buy_max * 100, 1)
        return {
            'status':   'waiting',
            'title':    '⏳ Harga di Atas Zona Beli',
            'detail':   f'Harga ({fmt_num(live_price)}) sudah {gap_pct}% di atas zona ({fmt_num(buy_min)}–{fmt_num(buy_max)}). R/R memburuk jika dipaksakan entry sekarang.',
            'action':   'Tunggu pullback ke zona beli atau cari setup lain.',
            'card_cls': 'signal-waiting', 'banner_cls': 'waiting-banner', 'title_color': '#e3b341',
        }
    else:
        return {'status': 'valid', 'title': '', 'detail': '', 'action': '',
                'card_cls': '', 'banner_cls': '', 'title_color': ''}


def compute_live_rr(live_price: float, stop_loss: float, tp1: float, tp2: float, tp3: float) -> dict:
    """
    AUDIT RONDE 2 — FIX (terbukti lewat eksekusi nyata): sebelumnya ada TIGA
    referensi harga berbeda untuk "R/R" yang sama pada satu kartu — string
    "R/R TP1" ditampilkan berbasis last_close, "Upside/Risk%" berbasis
    buy_max, sementara estimator probabilitas internal sudah pakai LIVE
    PRICE. Ketiganya nyaris identik selama harga tidak bergerak jauh dari
    saat scan — tapi begitu harga bergerak (skenario chasing yang justru
    coba dideteksi sistem validity-check), angka yang tampil ke user bisa
    menyesatkan. Contoh terverifikasi: kartu menampilkan "R/R TP1 = 1:2.0"
    saat kondisi live sebenarnya sudah "1:0.36" (harga naik 6% dari saat
    scan) — selisih besar yang bisa membuat trader salah menilai setup.

    Fungsi ini jadi SATU sumber kebenaran untuk R/R, Risk%, dan Upside% —
    dipakai baik oleh tampilan kartu/tabel maupun oleh estimator
    probabilitas, sehingga keduanya tidak akan pernah berbeda lagi.
    """
    risk_per_share = max(live_price - stop_loss, 1e-6)
    live_price_safe = max(live_price, 1e-6)
    return {
        'rr1': (tp1 - live_price) / risk_per_share,
        'rr2': (tp2 - live_price) / risk_per_share,
        'rr3': (tp3 - live_price) / risk_per_share,
        'risk_per_share': risk_per_share,
        'risk_pct': (live_price - stop_loss) / live_price_safe * 100,
        'up1_pct':  (tp1 - live_price) / live_price_safe * 100,
        'up2_pct':  (tp2 - live_price) / live_price_safe * 100,
        'up3_pct':  (tp3 - live_price) / live_price_safe * 100,
    }


def estimate_trade_probabilities(
    score: float, grade: str, live_price: float, buy_min: float, buy_max: float,
    stop_loss: float, tp1: float, tp2: float, tp3: float, atr_val: float,
    ind: dict, vol_ctx: dict, tape: dict, bandar: dict,
) -> dict:
    """
    Estimasi probabilitas rule-based untuk membandingkan kualitas setup
    secara relatif. INI BUKAN simulasi Monte Carlo atau model statistik
    terkalibrasi — murni heuristik dari skor & konteks indikator, dipakai
    sebagai proxy "confidence" relatif antar saham, bukan probabilitas
    presisi yang bisa diandalkan untuk taruhan.
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
    if ind.get("above_ema20"): trend_adj += 3.0
    if ind.get("above_ema50"): trend_adj += 4.0
    if ind.get("above_ema200"): trend_adj += 3.0
    if ind.get("ema20_rising"): trend_adj += 3.0

    momentum_adj = 0.0
    rsi = ind.get("rsi_val", 50.0)
    if 45 <= rsi <= 65: momentum_adj += 5.0
    elif 65 < rsi <= 75: momentum_adj -= 2.0
    elif rsi > 75: momentum_adj -= 8.0
    elif rsi < 35: momentum_adj -= 5.0

    cmf = ind.get("cmf_val", 0.0)
    if cmf > 0.05: momentum_adj += 4.0
    elif cmf < -0.05: momentum_adj -= 5.0

    volume_adj = 0.0
    if vol_ctx.get("valid"):
        vol_ratio = vol_ctx.get("vol_ratio", 0.0)
        candle_dir = vol_ctx.get("candle_dir")
        if candle_dir == "bullish" and vol_ratio >= 1.3: volume_adj += 6.0
        elif vol_ratio >= 1.5: volume_adj += 3.0
        elif candle_dir == "bearish" and vol_ratio >= 1.3: volume_adj -= 6.0

    tape_adj = 0.0
    for sig in tape.get("signals", []):
        if isinstance(sig, (tuple, list)) and len(sig) >= 2:
            if sig[1] == "accum": tape_adj += 5.0
            elif sig[1] == "distrib": tape_adj -= 6.0
            elif sig[1] == "warn": tape_adj -= 3.0

    bandar_adj = 0.0
    dom = bandar.get("dominant")
    if dom:
        conf_weight = {"high": 7.0, "med": 4.0, "low": 2.0}.get(dom.get("conf"), 2.0)
        if dom.get("style") == "accum": bandar_adj += conf_weight
        elif dom.get("style") == "distrib": bandar_adj -= conf_weight

    # ADX kini ikut menyesuaikan probabilitas — tren kuat & searah menambah
    # keyakinan, tren kuat berlawanan arah mengurangi.
    adx_adj = 0.0
    adx_strength = ind.get("adx_strength", "weak")
    adx_bullish  = ind.get("adx_bullish_dir", False)
    if adx_strength == "strong":
        adx_adj += 5.0 if adx_bullish else -6.0
    elif adx_strength == "moderate":
        adx_adj += 2.0 if adx_bullish else -2.0

    atr_pct = atr_val / max(live_price, 1.0)
    volatility_adj = 0.0
    if atr_pct > 0.08: volatility_adj -= 8.0
    elif atr_pct > 0.05: volatility_adj -= 4.0
    elif 0.015 <= atr_pct <= 0.04: volatility_adj += 3.0

    prob_entry = clamp_prob(
        base + grade_bonus + status_adj + trend_adj + momentum_adj
        + volume_adj + tape_adj + bandar_adj + adx_adj + volatility_adj
    )
    if live_price <= stop_loss:
        prob_entry = min(prob_entry, 15.0)

    live_rr = compute_live_rr(live_price, stop_loss, tp1, tp2, tp3)
    rr1, rr2, rr3 = live_rr['rr1'], live_rr['rr2'], live_rr['rr3']

    rr_bonus_1 = min(max((rr1 - 1.2) * 6.0, -8.0), 10.0)
    rr_bonus_2 = min(max((rr2 - 2.0) * 4.0, -10.0), 8.0)
    rr_bonus_3 = min(max((rr3 - 3.0) * 3.0, -12.0), 6.0)

    prob_tp1 = clamp_prob(prob_entry + rr_bonus_1 - atr_pct * 35.0)
    prob_tp2 = clamp_prob(prob_entry - 12.0 + rr_bonus_2 - atr_pct * 45.0)
    prob_tp3 = clamp_prob(prob_entry - 24.0 + rr_bonus_3 - atr_pct * 55.0)
    prob_sl  = 95.0 if live_price <= stop_loss else clamp_prob(100.0 - prob_tp1 + atr_pct * 45.0, 5.0, 90.0)

    # AUDIT RONDE 2 — robustness tambahan: paksa monoton menurun (target
    # lebih jauh tidak boleh punya probabilitas lebih tinggi dari target
    # yang lebih dekat). Secara matematis nyaris tidak mungkin dilanggar
    # mengingat rr1/rr2/rr3 berasal dari satu drift harga yang sama
    # (lihat compute_live_rr), tapi klem ini murah dan menutup celah teori
    # di kombinasi ekstrem batas clamp — jaring pengaman tanpa downside.
    prob_tp2 = min(prob_tp2, prob_tp1)
    prob_tp3 = min(prob_tp3, prob_tp2)

    return {
        "Prob Entry": prob_entry, "Prob TP1": prob_tp1, "Prob TP2": prob_tp2,
        "Prob TP3": prob_tp3, "Prob SL": prob_sl, "Confidence": probability_label(prob_entry),
    }


def clamp_prob(x: float, lo: float = 5.0, hi: float = 95.0) -> float:
    try:
        return round(max(lo, min(hi, float(x))), 1)
    except Exception:
        return lo

def probability_label(prob: float) -> str:
    if prob >= 75: return "Tinggi"
    if prob >= 60: return "Sedang"
    if prob >= 45: return "Spekulatif"
    return "Rendah"


# =============================================================================
# 11. BEST BUY ENGINE
# =============================================================================
MIN_BEST_BUY_SCORE = 45.0   # FIX #7: gerbang kualitas minimum untuk dimahkotai

def compute_best_buy_score(row: pd.Series) -> tuple[float, list[str]]:
    """
    Composite score "layak entry sekarang" (berbeda dari Score teknikal).

    1. Signal validity         30   valid=30, waiting-below=10, waiting-above(chasing)=4, expired=0
    2. Score teknikal (norm.)  25   score/100 × 25
    3. Grade bonus             10   A=10, B=6, C=2
    4. Bandar confidence       15   accum: high=15/med=8/low=3 | distrib: penalti skala confidence
    5. Tape confirmation       10   accum=+10, distrib=-5
    6. Volume konteks          10   vol spike + candle bullish=+10
    """
    reasons = []
    total   = 0.0

    validity = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
    if validity['status'] == 'valid':
        total += 30; reasons.append("✅ Harga dalam zona beli")
    elif validity['status'] == 'waiting':
        if row["Live Price"] > row["Buy Max"]:
            total += 4; reasons.append("⏳ Di atas zona, tunggu pullback")
        else:
            total += 10; reasons.append("⏳ Di bawah zona, SL masih aman")
    else:
        return 0.0, []

    tech_pts = (row["Score"] / 100.0) * 25
    total += tech_pts
    reasons.append(f"📊 Score teknikal {row['Score']}")

    grade_map = {"A": 10, "B": 6, "C": 2}
    total += grade_map.get(row.get("Grade", "C"), 2)
    reasons.append(f"🏅 Grade {row.get('Grade','C')}")

    bandar = row.get("_bandar", {})
    dom    = bandar.get("dominant")
    if dom:
        conf_pts = {"high": 15, "med": 8, "low": 3}.get(dom.get("conf", "low"), 3)
        if dom.get("style") == "distrib":
            # Penalti kini skala dengan confidence (dulu flat -5) — sinyal
            # distribusi confidence tinggi lebih berbahaya dari yang lemah.
            total -= conf_pts
            reasons.append(f"⚠️ Sinyal distribusi bandar ({dom.get('conf','')})")
        else:
            total += conf_pts
            reasons.append(f"🔍 Bandar: {dom.get('label','')} ({dom.get('conf','')})")
    else:
        reasons.append("— Tidak ada sinyal bandar")

    tape      = row.get("_tape", {})
    tape_sigs = tape.get("signals", [])
    accum_tape = [s for s in tape_sigs if s[1] == "accum"]
    if accum_tape:
        total += 10; reasons.append(f"📼 Tape: {accum_tape[0][2]}")
    elif any(s[1] == "distrib" for s in tape_sigs):
        total -= 5; reasons.append("📼 Tape: sinyal distribusi")

    vc = row.get("_vol_ctx", {})
    if vc.get("valid"):
        vol_ok  = vc.get("vol_ratio", 0) >= 1.3
        bull_ok = vc.get("candle_dir") == "bullish"
        if vol_ok and bull_ok:
            total += 10; reasons.append("📊 Vol spike + candle bullish")
        elif vol_ok:
            total += 5; reasons.append("📊 Vol spike (candle netral/bear)")
        elif bull_ok:
            total += 3; reasons.append("📊 Candle bullish (vol normal)")

    return round(max(total, 0.0), 1), reasons


def pick_best_buy(df: pd.DataFrame) -> tuple[str | None, float, list[str], bool]:
    """
    FIX #7: dua perbaikan terhadap versi lama —
    1. Kandidat yang harganya CHASING (di atas buy_max — tidak actionable)
       dikeluarkan dari kandidasi mahkota "Best Buy" sepenuhnya.
    2. Minimum quality gate (MIN_BEST_BUY_SCORE) — kalau kandidat terbaik
       pun masih lemah, sistem TIDAK memaksakan rekomendasi "Best Buy"
       (mengembalikan None) alih-alih menahkotai opsi seadanya.

    Return tambahan `is_watchlist`: True jika ada kandidat valid/waiting-below
    yang melewati gate, False jika tidak ada (caller bisa menampilkan
    pesan "tidak ada rekomendasi" alih-alih banner Best Buy).
    """
    if df.empty:
        return None, 0.0, [], False

    best_ticker, best_score, best_reasons = None, -1.0, []
    for _, row in df.iterrows():
        if row["Live Price"] > row["Buy Max"]:
            continue   # chasing — tidak boleh dimahkotai, walau tetap tampil di tabel
        s, r = compute_best_buy_score(row)
        if r and s > best_score:
            best_score, best_reasons, best_ticker = s, r, row["Ticker"]

    if best_ticker is None or best_score < MIN_BEST_BUY_SCORE:
        return None, 0.0, [], False

    return best_ticker, best_score, best_reasons, True


def render_best_buy_banner(ticker: str, score: float, reasons: list[str], row: pd.Series):
    validity = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
    if validity['status'] == 'valid':
        status_label, status_color = "🟢 Harga dalam zona — siap entry", "#3fb950"
    else:
        status_label, status_color = "🟡 Di bawah zona — pantau & tunggu", "#e3b341"

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
        f'border-radius:6px;padding:0.1rem 0.4rem;margin:0.1rem;font-size:0.68rem;color:#c9d1d9;">{r}</span>'
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
        f'  <div style="color:#fff;font-weight:700;">{fmt_num(row["Live Price"])}</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">ZONA BELI</div>'
        f'  <div style="color:#fff;font-weight:700;">{fmt_num(row["Buy Min"])}–{fmt_num(row["Buy Max"])}</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">STOP LOSS</div>'
        f'  <div style="color:#f85149;font-weight:700;">{fmt_num(row["Stop Loss"])}</div></div>'
        f'  <div><div style="color:#8b949e;font-size:0.6rem;">TARGET TP1</div>'
        f'  <div style="color:#3fb950;font-weight:700;">{fmt_num(row["TP1"])} <span style="font-size:0.65rem;">{row["Upside TP1"]}</span></div></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_no_best_buy_notice():
    """FIX #7: pesan jujur saat tidak ada kandidat yang cukup layak —
    dipisah dari banner Best Buy agar tidak ada tekanan untuk memaksakan
    rekomendasi pada hari yang memang lemah."""
    st.markdown(
        '<div class="watchlist-banner">'
        '<div style="font-size:0.95rem;font-weight:700;color:#58a6ff;">ℹ️ Belum Ada Rekomendasi Kuat Hari Ini</div>'
        '<div style="font-size:0.78rem;color:#8b949e;margin-top:0.3rem;">'
        'Tidak ada saham di hasil scan yang memenuhi standar minimum untuk dimahkotai '
        '"Best Buy" — baik karena harga sedang chasing (di atas zona beli) maupun '
        'karena skor kelayakan entry belum cukup kuat. Cek tabel ringkasan di bawah '
        'untuk kandidat yang masih dalam tahap "Tunggu Dulu".'
        '</div></div>',
        unsafe_allow_html=True
    )


# =============================================================================
# 12. RENDER TRADE CARDS
# =============================================================================
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
                    + pill_from_bd("adx",   "ADX")     # sekarang poin skor sungguhan (FIX #5/#6)
                )

                vol_ctx_html     = _render_volume_ctx_html(vol_ctx)
                tape_bandar_html = _render_tape_bandar_html(tape, bandar)
                adx_info_html    = _adx_info_badge(row["ADX"], row.get("ADX Strength", "weak"), row.get("ADX Bullish", False))

                validity = _check_signal_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
                is_best  = (row["Ticker"] == best_ticker)
                card_cls = validity['card_cls']
                if is_best:
                    card_cls = "best-buy-card"

                crown_html = '<div><span class="best-buy-crown">👑 Best Buy</span></div>' if is_best else ''

                is_expired = validity['status'] == 'expired'
                is_waiting = validity['status'] == 'waiting'
                if is_expired or is_waiting:
                    banner_html = (
                        f'<div class="{validity["banner_cls"]}">'
                        f'  <div style="font-size:0.78rem;font-weight:800;color:{validity["title_color"]};margin-bottom:0.2rem;">{validity["title"]}</div>'
                        f'  <div style="font-size:0.68rem;color:#c9d1d9;line-height:1.35;">{validity["detail"]}</div>'
                        f'  <div style="font-size:0.65rem;color:#8b949e;margin-top:0.2rem;font-style:italic;">{validity["action"]}</div>'
                        f'</div>'
                    )
                else:
                    banner_html = ''

                dim_open  = '<div class="dimmed">' if is_expired else '<div>'
                dim_close = '</div>'

                # FIX #8: semua angka harga pakai fmt_num (pemisah ribuan konsisten)
                html = (
                    f'<div class="metric-card {card_cls}">'
                    f'{crown_html}'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">'
                    f'  <span class="ticker">{row["Ticker"]}</span>'
                    f'  <div style="display:flex;gap:0.4rem;align-items:center;">'
                    f'    {_grade_badge(row["Grade"])}'
                    f'    <span class="score-badge">Score {row["Score"]}</span>'
                    f'  </div>'
                    f'</div>'
                    f'<div style="margin-bottom:0.5rem;">{pills_html}</div>'
                    f'{vol_ctx_html}'
                    f'{banner_html}'
                    f'{_price_status_html(row["Live Price"], row["Last Price"], row["Buy Min"], row["Buy Max"], row["Live Src"])}'
                    f'{dim_open}'
                    f'<div class="price-range">{fmt_num(row["Buy Min"])} – {fmt_num(row["Buy Max"])}</div>'
                    f'<div class="label" style="margin-bottom:0.6rem;">Area Rentang Buy · ATR {row["ATR"]} {adx_info_html}</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.4rem;'
                    f'margin-bottom:0.6rem;border-top:1px solid #30363d;padding-top:0.4rem;">'
                    f'  <div><div class="label">TP 1 <span class="rr-badge">({row["R/R TP1"]})</span></div>'
                    f'  <div class="tp">{fmt_num(row["TP1"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP1"]}</span></div></div>'
                    f'  <div><div class="label">TP 2 <span class="rr-badge">({row["R/R TP2"]})</span></div>'
                    f'  <div class="tp">{fmt_num(row["TP2"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP2"]}</span></div></div>'
                    f'  <div><div class="label">TP 3 <span class="rr-badge">({row["R/R TP3"]})</span></div>'
                    f'  <div class="tp" style="color:#bc8cff;">{fmt_num(row["TP3"])} <span style="font-size:0.68rem;opacity:0.8">{row["Upside TP3"]}</span></div></div>'
                    f'</div>'
                    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.4rem;">'
                    f'  <div><div class="label">Stop Loss</div>'
                    f'  <div class="sl">{fmt_num(row["Stop Loss"])} <span style="font-size:0.68rem;opacity:0.8">{row["Risk%"]}</span></div></div>'
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
                    f'{tape_bandar_html}'
                    f'</div>'
                )
                st.markdown(html, unsafe_allow_html=True)

# =============================================================================
# 13. SIDEBAR & CONFIG
# =============================================================================
st.sidebar.header("⚙️ Parameter Algoritma")
capital          = st.sidebar.number_input("Total Modal Akun (Rp)", value=50_000_000, step=5_000_000, min_value=1_000_000)
risk_limit       = st.sidebar.slider("Maks Risiko per Trade (%)", 0.5, 5.0, 2.0, 0.5)
allocation_limit = st.sidebar.slider("Maks Alokasi Dana per Saham (%)", 10, 50, 25, 5)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filter Likuiditas & Harga")
min_adtv_value = st.sidebar.number_input("Minimal ADTV (Rp)", value=500_000_000, step=100_000_000, min_value=0)
min_px         = st.sidebar.number_input("Harga Minimal Saham (Rp)", value=100, step=50, min_value=1)
max_px         = st.sidebar.number_input("Harga Maksimal Saham (Rp)", value=25_000, step=500, min_value=1)
min_score      = st.sidebar.slider("Min Score Threshold", 50, 85, 60, 5,
                                    help="Semakin tinggi = sinyal lebih selektif")

if min_px >= max_px:
    st.sidebar.error("⚠️ Harga Minimal harus lebih kecil dari Harga Maksimal.")

st.sidebar.markdown("---")
debug_placeholder = st.sidebar.empty()

config_engine = {
    'total_capital':              capital,
    'capital_risk_limit_pct':     risk_limit,
    'max_capital_allocation_pct': allocation_limit,
    'min_adtv':                   min_adtv_value,
    'min_price':                  min_px,
    'max_price':                  max_px,
    'min_score_threshold':        float(min_score),
}

# =============================================================================
# 14. MAIN UI
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
        st.session_state['download_failures'] = {}
        st.success("Reset berhasil.")

# =============================================================================
# 15. EXECUTION CORE
# =============================================================================
if execute_scan:
    if not tickers_ready:
        st.error("❌ Daftar emiten kosong.")
        st.stop()
    if min_px >= max_px:
        st.error("❌ Filter harga tidak valid.")
        st.stop()

    # FIX #3: window swing diperpanjang dari 120 → 400 hari kalender (~280
    # trading day) agar EMA200 benar-benar punya cukup data untuk aktif.
    # Versi lama (120 hari ≈ 85 trading day) membuat bonus EMA200 di
    # score_trend jadi dead code untuk hampir semua saham.
    p_days, p_interval = (30, "60m") if trading_mode == "Intraday (Fast Trade)" else (400, "1d")
    CHUNK_SIZE = 15 if trading_mode == "Intraday (Fast Trade)" else 40

    sorted_tickers = sorted(set(tickers_ready))
    chunks         = [sorted_tickers[i:i + CHUNK_SIZE] for i in range(0, len(sorted_tickers), CHUNK_SIZE)]
    total_chunks   = len(chunks)
    buffer         = {}

    status_ph  = st.empty()
    progress_b = st.progress(0)

    for idx, chunk in enumerate(chunks):
        n_done = min((idx + 1) * CHUNK_SIZE, len(sorted_tickers))
        status_ph.markdown(f"⏳ Mengunduh {n_done}/{len(sorted_tickers)} emiten (Batch {idx+1}/{total_chunks})…")
        progress_b.progress(int((idx + 1) / total_chunks * 100))
        buffer.update(download_ticker_chunk(chunk, p_days, p_interval))

    status_ph.empty()
    progress_b.empty()

    if not buffer:
        st.error("❌ Tidak ada data berhasil diunduh. Cek koneksi atau daftar ticker.")
        st.stop()

    # AUDIT RONDE 2 — FIX: ticker yang gagal diunduh SAMA SEKALI sebelumnya
    # hilang tanpa jejak — tidak pernah masuk ke `all_data`, sehingga tidak
    # pernah tercatat di `skipped_reason` milik quant_strategy_engine (yang
    # hanya mengiterasi ticker yang BERHASIL diunduh). Pengguna hanya melihat
    # toast "Data berhasil untuk 15/20 saham" tanpa tahu 5 mana & kenapa.
    # Sekarang dicatat eksplisit dan digabung ke panel debug yang sama.
    missing_tickers = sorted(set(sorted_tickers) - set(buffer.keys()))
    st.session_state['download_failures'] = {
        t: "gagal diunduh (kode tidak ditemukan / tidak ada respons dari sumber data)"
        for t in missing_tickers
    }

    st.session_state['raw_market_data']  = buffer
    st.session_state['last_loaded_mode'] = trading_mode
    if missing_tickers:
        st.warning(
            f"⚠️ {len(missing_tickers)} dari {len(sorted_tickers)} saham gagal diunduh — "
            f"lihat panel Debug/Audit Scan di sidebar untuk daftar lengkapnya."
        )
    st.success(f"✅ Data berhasil untuk {len(buffer)}/{len(sorted_tickers)} saham.")

# ── Auto-render jika data tersedia & mode cocok ────────────────────────────
if st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] == trading_mode:
    final_df = quant_strategy_engine(st.session_state['raw_market_data'], config_engine, trading_mode)

    st.markdown(f"### 📈 Hasil Scan [{trading_mode}]")
    st.caption(
        "Kolom **Prob Entry/TP/SL** adalah estimasi heuristik dari kombinasi skor "
        "teknikal & konteks (tape, bandarmology, volatilitas) — **bukan** probabilitas "
        "statistik yang tervalidasi/backtested. Gunakan sebagai perbandingan relatif "
        "antar saham, bukan angka presisi untuk sizing taruhan."
    )

    best_ticker, best_score, best_reasons, has_rec = pick_best_buy(final_df)
    if best_ticker:
        best_row = final_df[final_df["Ticker"] == best_ticker].iloc[0]
        render_best_buy_banner(best_ticker, best_score, best_reasons, best_row)
    elif not final_df.empty:
        render_no_best_buy_notice()
    else:
        st.info("ℹ️ Tidak ada saham yang lolos filter pada scan ini.")

    render_trade_cards(final_df, max_cards=6, best_ticker=best_ticker)

    # ── Tabel Ringkas ──────────────────────────────────────────────────────
    if not final_df.empty:
        st.markdown("---")
        st.markdown("### 📋 Ringkasan Semua Hasil Skrining")
        st.caption("Semua saham yang lolos filter, diurutkan dari yang paling direkomendasikan.")

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
            return s[2] if isinstance(s, (tuple, list)) and len(s) > 2 else str(s)

        def _adx_label(row):
            dir_icon = "▲" if row.get("ADX Bullish") else "▼"
            strength_map = {"strong": "Kuat", "moderate": "Sedang", "weak": "Lemah"}
            return f"{row['ADX']:.0f} {dir_icon} ({strength_map.get(row.get('ADX Strength','weak'),'—')})"

        tabel_rows = []
        for _, row in final_df.iterrows():
            is_best = row["Ticker"] == best_ticker
            tabel_rows.append({
                "🏆":          "👑" if is_best else "",
                "Saham":       row["Ticker"],
                "Harga Skrg":  f"Rp {fmt_num(row['Live Price'])}",
                "Zona Beli":   f"Rp {fmt_num(row['Buy Min'])} – {fmt_num(row['Buy Max'])}",
                "Target 1":    f"Rp {fmt_num(row['TP1'])} ({row['Upside TP1']})",
                "Target 2":    f"Rp {fmt_num(row['TP2'])} ({row['Upside TP2']})",
                "Target 3":    f"Rp {fmt_num(row['TP3'])} ({row['Upside TP3']})",
                "Stop Loss":   f"Rp {fmt_num(row['Stop Loss'])} ({row['Risk%']})",
                "R/R":         row["R/R TP1"],
                "Score":       row["Score"],
                "Grade":       row["Grade"],
                "ADX":         _adx_label(row),
                "Prob Entry":  f"{row['Prob Entry']}%",
                "Prob TP1":    f"{row['Prob TP1']}%",
                "Prob SL":     f"{row['Prob SL']}%",
                "Confidence":  row["Confidence"],
                "Status":      _validity_label(row),
                "Sinyal Bandar": _bandar_label(row),
                "Tape":        _tape_label(row),
                "Lot Saran":   f"{int(row['Lots'])} lot",
                "Alokasi":     fmt_idr(row["Alokasi (Rp)"]),
            })

        tabel_df = pd.DataFrame(tabel_rows)

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
            .set_properties(**{"font-size": "0.82rem", "text-align": "left"})
            .set_table_styles([{
                "selector": "th",
                "props": [("font-size", "0.75rem"), ("text-transform", "uppercase"),
                          ("letter-spacing", "0.4px"), ("color", "#8b949e")]
            }])
        )

        st.dataframe(styled, use_container_width=True, hide_index=True,
                     height=min(80 + len(tabel_rows) * 38, 600))

elif st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] != trading_mode:
    st.warning("⚠️ Mode trading diubah. Klik **🚀 Jalankan Skrining** untuk memperbarui data.")

else:
    st.info("👋 Belum ada hasil scan. Isi daftar saham di atas, lalu klik **🚀 Jalankan Skrining** untuk memulai.")

# =============================================================================
# 16. PANEL DEBUG/AUDIT — render tunggal (AUDIT RONDE 2 — FIX)
# =============================================================================
# Versi sebelumnya menyebar logika ini ke 3 blok if/elif terpisah yang bisa
# saling menimpa isi `debug_placeholder` dalam satu run yang sama (boros,
# walau tak fatal), dan pada kasus mode-mismatch bisa diam-diam menampilkan
# data BASI dari scan mode sebelumnya tanpa memberi tahu pengguna bahwa itu
# bukan data untuk mode yang sedang aktif. Sekarang: satu blok tunggal,
# selalu mencerminkan state saat ini dengan akurat, dan melabeli data basi
# secara eksplisit. Ticker yang gagal DIUNDUH (jaringan/kode salah) dan yang
# gagal di tahap FILTER PIPELINE sekarang digabung jadi satu tabel, sehingga
# perjalanan penuh (download → filter → skor) terlihat di satu tempat.
with debug_placeholder.expander("🔬 Debug / Audit Scan", expanded=False):
    if not st.session_state.get('raw_market_data'):
        st.caption("Jalankan skrining dulu.")
    else:
        if st.session_state['last_loaded_mode'] != trading_mode:
            st.caption(
                f"⚠️ Mode aktif saat ini (**{trading_mode}**) berbeda dari mode scan "
                f"terakhir (**{st.session_state['last_loaded_mode']}**) — info di bawah "
                f"BASI, dari scan mode sebelumnya. Jalankan ulang untuk info terkini."
            )

        meta = st.session_state.get('scan_meta', {})
        st.write(f"**Input:** {meta.get('total_input', 0)} saham")
        st.write(f"**Lolos:** {meta.get('lolos', 0)} saham")
        st.write(f"**Difilter (pipeline):** {meta.get('difilter', 0)} saham")

        download_failures = st.session_state.get('download_failures', {})
        if download_failures:
            st.write(f"**Gagal diunduh:** {len(download_failures)} saham")

        combined_reasons = {**download_failures, **meta.get('skipped', {})}
        if combined_reasons:
            st.dataframe(
                pd.DataFrame(list(combined_reasons.items()), columns=["Ticker", "Alasan"]),
                use_container_width=True, height=200
            )
        else:
            st.caption("Semua saham lolos filter atau tidak ada yang difilter.")
