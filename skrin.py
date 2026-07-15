import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
import hashlib
import concurrent.futures
from datetime import datetime, timedelta

# Auto-fallback ke Altair jika Plotly tidak terinstall
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    import altair as alt

# =============================================================================
# CHANGELOG v9.4 (HASH FIX)
# =============================================================================
# 1. [HOTFIX] Memperbaiki ValueError pada _hash_d saat menerima input DataFrame Pandas (IHSG).
# =============================================================================

SECTOR_MAP = {
    'BBRI': 'Banking', 'BBCA': 'Banking', 'BMRI': 'Banking', 'BBNI': 'Banking', 'BBTN': 'Banking', 'BNII': 'Banking', 'BNGA': 'Banking', 'BJBR': 'Banking', 'BTPS': 'Banking', 'BRIS': 'Banking',
    'TLKM': 'Telecom', 'EXCL': 'Telecom', 'ISAT': 'Telecom', 'FREN': 'Telecom', 'MTEL': 'Telecom',
    'ASII': 'Automotive', 'AUTO': 'Automotive', 'IMAS': 'Automotive', 'UNTR': 'Heavy Mach.', 'CPIN': 'Food',
    'UNVR': 'Consumer', 'INDF': 'Consumer', 'ICBP': 'Consumer', 'MYOR': 'Consumer', 'GGRM': 'Consumer',
    'ADRO': 'Coal', 'ITMG': 'Coal', 'PTBA': 'Coal', 'HRUM': 'Coal', 'BUMI': 'Coal', 'INDY': 'Coal',
    'MDKA': 'Metals', 'ANTM': 'Metals', 'INCO': 'Metals', 'INAF': 'Metals', 'ISSP': 'Metals',
    'JSMR': 'Infra', 'WIKA': 'Infra', 'WSKT': 'Infra', 'PTPP': 'Infra', 'PPRE': 'Infra', 'ACST': 'Infra',
    'KLBF': 'Pharma', 'DVLA': 'Pharma', 'KAEF': 'Pharma',
    'GOTO': 'Tech', 'BUKA': 'Tech', 'EMTK': 'Tech', 'MLPT': 'Tech', 'MTDL': 'Tech',
    'TPIA': 'Chemical', 'BRPT': 'Energy', 'AKRA': 'Energy', 'PGAS': 'Energy',
}

st.set_page_config(page_title="Quant Trader - IDX Screener v9.4", layout="wide", initial_sidebar_state="expanded")

if 'theme' not in st.session_state: st.session_state['theme'] = 'dark'

def inject_css():
    bg_color = "#0d1117" if st.session_state['theme'] == 'dark' else "#ffffff"
    text_color = "#c9d1d9" if st.session_state['theme'] == 'dark' else "#1f2328"
    card_bg = "#161b22" if st.session_state['theme'] == 'dark' else "#f6f8fa"
    border_color = "#30363d" if st.session_state['theme'] == 'dark' else "#d0d7de"
    
    st.markdown(f"""
    <style>
        .stApp {{ background-color: {bg_color}; color: {text_color}; }}
        .metric-card {{ background-color: {card_bg}; border: 1px solid {border_color}; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.2s, border-color 0.2s; }}
        .metric-card:hover {{ transform: translateY(-2px); border-color: #58a6ff; }}
        .ticker {{ font-size: 1.6rem; font-weight: 800; color: #58a6ff; letter-spacing: 0.5px; }}
        .score-badge {{ background-color: rgba(56, 139, 253, 0.15); color: #58a6ff; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.85rem; font-weight: 700; border: 1px solid rgba(56, 139, 253, 0.3); }}
        .grade-A  {{ background: rgba(63,185,80,.15);  color:#3fb950; border:1px solid rgba(63,185,80,.3);  padding:0.15rem 0.5rem; border-radius:12px; font-weight:700; }}
        .grade-B  {{ background: rgba(88,166,255,.15); color:#58a6ff; border:1px solid rgba(88,166,255,.3); padding:0.15rem 0.5rem; border-radius:12px; font-weight:700; }}
        .grade-C  {{ background: rgba(219,109,40,.15); color:#db6d28; border:1px solid rgba(219,109,40,.3); padding:0.15rem 0.5rem; border-radius:12px; font-weight:700; }}
        .price-range {{ font-size: 1.8rem; font-weight: 700; color: {text_color}; margin-top: 0.2rem; }}
        .label {{ font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }}
        .tp  {{ font-size: 1.1rem; font-weight: 700; color: #3fb950; }}
        .sl  {{ font-size: 1.1rem; font-weight: 700; color: #f85149; }}
        .ts-rule {{ font-size: 0.85rem; font-weight: 600; color: #db6d28; }}
        .ind-pill {{ display:inline-block; font-size:0.7rem; font-weight:600; padding:0.1rem 0.45rem; border-radius:10px; margin:0.1rem; }}
        .ind-bull {{ background:rgba(63,185,80,.15);  color:#3fb950; border:1px solid rgba(63,185,80,.3); }}
        .ind-bear {{ background:rgba(248,81,73,.15);  color:#f85149; border:1px solid rgba(248,81,73,.3); }}
        .ind-neut {{ background:rgba(139,148,158,.12);color:#8b949e; border:1px solid rgba(139,148,158,.3);}}
        .rr-badge  {{ font-size:0.75rem; font-weight:700; color:#d2a8ff; }}
        .vol-ctx {{ background:rgba(255,255,255,0.03); border-radius:6px; padding:0.4rem 0.6rem; margin-bottom:0.5rem; border:1px solid {border_color}; }}
        .vol-bar-track {{ background:{border_color}; border-radius:4px; height:5px; width:100%; margin-top:0.25rem; }}
        .vol-bar-fill  {{ height:5px; border-radius:4px; transition:width 0.3s; }}
        .section-divider {{ border-top:1px solid {border_color}; margin:0.5rem 0 0.4rem; }}
        .tape-pill {{ display:inline-block; font-size:0.65rem; font-weight:700; padding:0.12rem 0.4rem; border-radius:8px; margin:0.08rem 0.06rem; }}
        .tape-accum   {{ background:rgba(63,185,80,.18);  color:#3fb950; border:1px solid rgba(63,185,80,.35); }}
        .tape-distrib {{ background:rgba(248,81,73,.18);  color:#f85149; border:1px solid rgba(248,81,73,.35); }}
        .tape-warn    {{ background:rgba(219,109,40,.18); color:#db6d28; border:1px solid rgba(219,109,40,.35);}}
        .tape-purple  {{ background:rgba(188,140,255,.15);color:#bc8cff; border:1px solid rgba(188,140,255,.3);}}
        .narasi-tech  {{ font-size:0.72rem; color:{text_color}; font-style:italic; line-height:1.35; }}
        .narasi-plain {{ font-size:0.7rem;  color:#8b949e; line-height:1.3; margin-top:0.15rem; }}
        .signal-expired {{ border-color: #f85149 !important; background: rgba(248,81,73,0.04) !important; }}
        .signal-waiting {{ border-color: #e3b341 !important; background: rgba(227,179,65,0.04) !important; }}
        .expired-banner {{ background: rgba(248,81,73,0.12); border:1px solid rgba(248,81,73,0.4); border-radius:6px; padding:0.5rem 0.7rem; margin-bottom:0.5rem; text-align:center; }}
        .waiting-banner {{ background: rgba(227,179,65,0.1); border:1px solid rgba(227,179,65,0.35); border-radius:6px; padding:0.5rem 0.7rem; margin-bottom:0.5rem; text-align:center; }}
        .dimmed {{ opacity: 0.35; pointer-events:none; user-select:none; filter:grayscale(60%); }}
        .best-buy-card {{ border-color: #ffd700 !important; background: linear-gradient(135deg, rgba(255,215,0,0.06) 0%, {card_bg} 60%) !important; box-shadow: 0 0 0 2px rgba(255,215,0,0.25), 0 6px 20px rgba(255,215,0,0.1) !important; }}
        .best-buy-crown {{ display:inline-flex; align-items:center; gap:0.3rem; background:linear-gradient(90deg,#ffd700,#ffb300); color:#0d1117; font-size:0.72rem; font-weight:900; padding:0.2rem 0.65rem; border-radius:20px; letter-spacing:0.3px; margin-bottom:0.5rem; }}
        .best-buy-banner {{ background:linear-gradient(135deg,rgba(255,215,0,0.12),rgba(255,179,0,0.06)); border:1px solid rgba(255,215,0,0.4); border-radius:8px; padding:0.8rem 1rem; margin-bottom:1.2rem; }}
        .adx-info {{ display:inline-block; font-size:0.66rem; font-weight:700; padding:0.08rem 0.4rem; border-radius:6px; margin-left:0.3rem; background:rgba(188,140,255,0.12); color:#bc8cff; border:1px solid rgba(188,140,255,0.3); }}
        @media (max-width: 768px) {{ .metric-card {{ padding: 1rem; }} .ticker {{ font-size: 1.4rem; }} .price-range {{ font-size: 1.5rem; }} .metric-card div[style*="grid-template-columns: 1fr 1fr 1fr"] {{ grid-template-columns: 1fr !important; }} }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

for key, default in [
    ('raw_market_data', {}), ('last_loaded_mode', None), ('scan_meta', {}),
    ('download_failures', {}), ('last_final_df', None), ('ihsg_data', None),
]:
    if key not in st.session_state: st.session_state[key] = default

def fmt_idr(val):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)): return "Rp 0"
        return f"Rp {int(val):,}".replace(",", ".")
    except: return "Rp 0"

def fmt_num(val) -> str:
    try: return f"{int(round(float(val))):,}".replace(",", ".")
    except: return "0"

def parse_tickers_from_df(df):
    ticker_col = None
    for col in df.columns:
        if col.strip().lower() in ("ticker", "kode", "symbol", "emiten", "code"): ticker_col = col; break
    if ticker_col is None: ticker_col = df.columns[0]
    return [t.upper() if t.upper().endswith(".JK") else f"{t.upper()}.JK" for t in df[ticker_col].dropna().astype(str).str.strip().tolist() if t.strip() and t.strip().lower() not in ("nan", "none", "")]

@st.cache_data(show_spinner=False)
def load_local_emiten_csv():
    try: base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError: base_dir = os.getcwd()
    if os.path.exists(os.path.join(base_dir, "emiten.csv")):
        try: return parse_tickers_from_df(pd.read_csv(os.path.join(base_dir, "emiten.csv")))
        except: return []
    return []

def tickers_from_text(text): return [t.upper() if t.upper().endswith(".JK") else f"{t.upper()}.JK" for t in re.split(r"[,\s\n]+", text.strip()) if t.strip()]

def calculate_atr(df, w=14):
    pc = df['Close'].shift(1)
    tr = pd.concat([df['High']-df['Low'], (df['High']-pc).abs(), (df['Low']-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/w, adjust=False).mean()

def calculate_cmf(df, w=20):
    if len(df) < w: return pd.Series(0.0, index=df.index)
    hl = (df['High']-df['Low']).replace(0, np.nan)
    mfm = ((df['Close']-df['Low']) - (df['High']-df['Close'])) / hl
    vs = df['Volume'].rolling(w).sum().replace(0, np.nan)
    return ((mfm.fillna(0)*df['Volume']).rolling(w).sum() / vs).fillna(0.0)

def calculate_rsi(df, w=14):
    d = df['Close'].diff()
    ag, al = d.clip(lower=0).ewm(alpha=1/w, adjust=False).mean(), (-d).clip(lower=0).ewm(alpha=1/w, adjust=False).mean()
    return (100 - (100 / (1 + ag / al.replace(0, 1e-10)))).fillna(50.0)

def calculate_bb_squeeze(df, bbw=20, bbs=2.0, kcm=1.5, aw=14):
    if len(df) < bbw: return pd.Series(False, index=df.index)
    b = df['Close'].rolling(bbw).mean()
    bb_u, bb_l = b + bbs * df['Close'].rolling(bbw).std(ddof=1), b - bbs * df['Close'].rolling(bbw).std(ddof=1)
    kc_u, kc_l = b + kcm * calculate_atr(df, aw), b - kcm * calculate_atr(df, aw)
    return ((bb_u < kc_u) & (bb_l > kc_l)).fillna(False)

def calculate_adx(df, w=14):
    if len(df) < w + 2: return {'adx': 0.0, 'di_plus': 0.0, 'di_minus': 0.0, 'bullish_dir': False, 'strength': 'weak'}
    h, l, c = df['High'].values.astype(float), df['Low'].values.astype(float), df['Close'].values.astype(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h-l, np.maximum(np.abs(h-pc), np.abs(l-pc)))
    up, dn = h-np.roll(h, 1), np.roll(l, 1)-l; up[0], dn[0] = 0.0, 0.0
    dmp = np.where((up>dn)&(up>0), up, 0.0); dmm = np.where((dn>up)&(dn>0), dn, 0.0)
    a = 1.0/w
    atrw = pd.Series(tr).ewm(alpha=a, adjust=False).mean().values
    dmpw = pd.Series(dmp).ewm(alpha=a, adjust=False).mean().values
    dmmw = pd.Series(dmm).ewm(alpha=a, adjust=False).mean().values
    dip, dim = 100.0*dmpw/np.maximum(atrw,1e-9), 100.0*dmmw/np.maximum(atrw,1e-9)
    dx = 100.0*np.abs(dip-dim)/np.maximum(dip+dim,1e-9)
    adx = pd.Series(dx).ewm(alpha=a, adjust=False).mean().values[-1]
    s = 'strong' if adx>=25 else ('moderate' if adx>=18 else 'weak')
    return {'adx': round(float(adx),1), 'di_plus': round(float(dip[-1]),1), 'di_minus': round(float(dim[-1]),1), 'bullish_dir': dip[-1]>dim[-1], 'strength': s}

def calculate_indicators(df):
    cl, vol = df['Close'], df['Volume']
    e200, e50, e20 = cl.ewm(span=200, adjust=False).mean(), cl.ewm(span=50, adjust=False).mean(), cl.ewm(span=20, adjust=False).mean()
    lc = float(cl.iloc[-1])
    e200_ok = len(cl) >= 200
    atr_s = calculate_atr(df); atr_v = float(atr_s.iloc[-1])
    cmf_s = calculate_cmf(df); rsi_s = calculate_rsi(df); sq_s = calculate_bb_squeeze(df)
    adx_d = calculate_adx(df)
    vol_ma15 = float(vol.rolling(15).mean().iloc[-1])
    summ = {
        'last_close': lc, 'ema200_available': e200_ok, 'above_ema200': lc>float(e200.iloc[-1]) if e200_ok else False,
        'above_ema50': lc>float(e50.iloc[-1]), 'above_ema20': lc>float(e20.iloc[-1]),
        'ema20_rising': float(e20.iloc[-1])>float(e20.iloc[-3]) if len(e20)>=3 else False,
        'atr_val': atr_v, 'atr_pct': atr_v/lc if lc>0 else 0, 'cmf_val': float(cmf_s.iloc[-1]), 'cmf_rising': float(cmf_s.iloc[-1])>float(cmf_s.iloc[-2]) if len(cmf_s)>1 else False,
        'rsi_val': float(rsi_s.iloc[-1]), 'rsi_rising': float(rsi_s.iloc[-1])>float(rsi_s.iloc[-2]) if len(rsi_s)>1 else False,
        'in_squeeze': bool(sq_s.iloc[-1]), 'squeeze_release': (not bool(sq_s.iloc[-1])) and bool(sq_s.iloc[-2]) if len(sq_s)>1 else False,
        'adx_val': adx_d['adx'], 'adx_di_plus': adx_d['di_plus'], 'adx_di_minus': adx_d['di_minus'], 'adx_bullish_dir': adx_d['bullish_dir'], 'adx_strength': adx_d['strength'],
        'vol_spike': float(vol.iloc[-1])/max(vol_ma15,1.0), 'adtv': float(vol.rolling(20).mean().iloc[-1])*lc
    }
    if not np.isfinite(atr_v) or atr_v <= 0: raise ValueError(f"ATR invalid: {atr_v}")
    return summ, {'close': cl, 'ema20': e20, 'ema50': e50, 'ema200': e200, 'atr': atr_s, 'cmf': cmf_s, 'rsi': rsi_s, 'squeeze': sq_s, 'volume': vol}

def is_tradeable_stock(df, lc):
    if len(df) < 10: return False, "data pendek"
    if (df['Volume'].tail(3) <= 0).all(): return False, "vol 0 (suspend)"
    if df['Close'].tail(5).nunique() == 1: return False, "stagnan"
    try:
        ld = df.index[-1]
        if hasattr(ld, 'to_pydatetime'): ld = ld.to_pydatetime()
        if getattr(ld, 'tzinfo', None) is not None: ld = ld.replace(tzinfo=None)
        if (datetime.now() - ld).days > 10: return False, "data basi"
    except: pass
    if ((df.tail(10)['High'] - df.tail(10)['Low']) <= 0).sum() >= 7: return False, "OHLC error"
    if not np.isfinite(lc) or lc <= 0: return False, "harga invalid"
    return True, ""

def analyse_volume_context(df):
    if len(df) < 5: return {'valid': False}
    r = df.iloc[-1]
    o, h, l, c, v = float(r['Open']), float(r['High']), float(r['Low']), float(r['Close']), float(r['Volume'])
    rng = h-l if h>l else 1e-9
    vr = v / max(float(df['Volume'].rolling(20).mean().iloc[-1]), 1.0)
    cd = "doji" if abs(c-o)/rng < 0.15 else ("bullish" if c>=o else "bearish")
    return {'valid': True, 'candle_dir': cd, 'body_pct': round(abs(c-o)/rng, 3), 'close_pos': round((c-l)/rng, 3), 'vol_ratio': round(vr, 2)}

def analyse_tape(df, ind_s):
    if len(df) < 10: return {'signals': [], 'dominant': None}
    t = df.tail(5)
    v5, h5, l5, o5, c5 = t['Volume'].values, t['High'].values, t['Low'].values, t['Open'].values, t['Close'].values
    vm = float(df['Volume'].rolling(20).mean().iloc[-1])
    a5 = float(ind_s['atr'].tail(20).iloc[-1])
    r5 = h5-l5; ar5 = np.mean(r5) if np.mean(r5)>0 else 1e-9
    sigs = []
    lvr, lr = v5[-1]/max(vm,1.0), r5[-1]
    lb, lcp = abs(c5[-1]-o5[-1]), (c5[-1]-l5[-1])/max(lr,1e-9)
    if lvr>2.5 and lb/max(lr,1e-9)>0.6 and c5[-1]>o5[-1] and lcp>0.7: sigs.append(('buying_climax', 'distrib', 'Buying Climax', 'BC', min(int(lvr/3*100),90)))
    if lvr>2.5 and lb/max(lr,1e-9)>0.6 and c5[-1]<o5[-1] and lcp<0.3: sigs.append(('selling_climax', 'accum', 'Selling Climax', 'SC', min(int(lvr/3*100),90)))
    if lvr>1.8 and lcp>0.55 and abs(c5[-1]-c5[-2])/max(a5,1e-9)<0.5: sigs.append(('absorption', 'accum', 'Absorption', 'ABS', min(int(lcp*lvr/2.5*100),85)))
    if lvr>1.8 and lr<ar5*0.6: sigs.append(('exhaustion', 'warn', 'Exhaustion', 'EXH', min(int((ar5/max(lr,1e-9))*20),80)))
    if all(v<vm*0.8 for v in v5) and (max(c5)-min(c5))/max(a5,1e-9)<1.5: sigs.append(('accum_quiet', 'accum', 'Akumulasi Senyap', 'AQ', 72))
    return {'signals': sigs, 'dominant': sigs[0] if sigs else None}

def _find_pivots(s, order=3):
    v, n = s.values, len(s); pl, ph = [], []
    for i in range(order, n-order):
        w = v[i-order:i+order+1]
        if v[i] <= w.min()+1e-6 and np.argmin(w)==order: pl.append(i)
        if v[i] >= w.max()-1e-6 and np.argmax(w)==order: ph.append(i)
    return pl, ph

def _detect_div(df, ind_s, name, lb=40, order=3):
    if len(df) < lb+order*2: return None
    tc = df['Close'].tail(lb).reset_index(drop=True)
    ti = ind_s.tail(lb).reset_index(drop=True)
    if ti.isna().any(): return None
    pll, plh = _find_pivots(tc, order)
    if len(pll)>=2 and tc[pll[-1]]<tc[pll[-2]] and ti[pll[-1]]>ti[pll[-2]]:
        c = min(int(abs(float(ti[pll[-1]])-float(ti[pll[-2]]))*3+55),88)
        return {'key': f'bullish_div_{name}', 'style': 'accum', 'label': f'Bullish Divergence ({name.upper()})', 'short': f'DIV+{name[:3].upper()}', 'conf_pct': c, 'conf': 'high' if c>=75 else 'med'}
    if len(plh)>=2 and tc[plh[-1]]>tc[plh[-2]] and ti[plh[-1]]<ti[plh[-2]]:
        c = min(int(abs(float(ti[plh[-1]])-float(ti[plh[-2]]))*3+55),88)
        return {'key': f'bearish_div_{name}', 'style': 'distrib', 'label': f'Bearish Divergence ({name.upper()})', 'short': f'DIV-{name[:3].upper()}', 'conf_pct': c, 'conf': 'high' if c>=75 else 'med'}
    return None

def _detect_trap(df, lb=20):
    if len(df) < lb+5: return None
    vm, cc = float(df['Volume'].rolling(20).mean().iloc[-1]), float(df['Close'].iloc[-1])
    for b in range(1,4):
        i = len(df)-1-b
        if i < lb: continue
        ph, bh, bv = float(df['High'].iloc[i-lb:i].max()), float(df['High'].iloc[i]), float(df['Volume'].iloc[i])
        if bh>ph and bv>vm*1.5 and cc<ph:
            c = min(int(50+((ph-cc)/ph*100)*5),85)
            return {'key': 'bull_trap', 'style': 'distrib', 'label': 'Bull Trap', 'short': 'TRAP', 'conf_pct': c, 'conf': 'high' if c>=75 else 'med'}
    return None

def analyse_bandar(df, ind_s):
    if len(df) < 20: return {'signals': [], 'dominant': None, 'narasi_tech': '', 'narasi_plain': ''}
    vm = float(df['Volume'].rolling(20).mean().iloc[-1])
    av = float(ind_s['atr'].tail(30).iloc[-1])
    c, h, l, o, v = df['Close'].values, df['High'].values, df['Low'].values, df['Open'].values, df['Volume'].values
    cp = lambda i: (c[i]-l[i])/max(h[i]-l[i],1e-9)
    vr = lambda i: v[i]/max(vm,1.0)
    cl = lambda p: 'high' if p>=75 else ('med' if p>=50 else 'low')
    sigs, n, last = [], len(df), len(df)-1
    for i in range(max(0,n-3), n):
        if c[i]<c[i-1] and cp(i)>0.55 and vr(i)>1.4:
            p = int(min((cp(i)-0.55)/0.45*50+(vr(i)-1.4)/1.6*50,95)); sigs.append({'key':'accum_signal','style':'accum','label':'Akumulasi','short':'ACCU','conf_pct':p,'conf':cl(p)}); break
    for i in range(max(0,n-3), n):
        if c[i]>c[i-1] and cp(i)<0.45 and vr(i)>1.8:
            p = int(min((1-cp(i)-0.55)/0.45*50+(vr(i)-1.8)/2.2*50,95)); sigs.append({'key':'distrib_signal','style':'distrib','label':'Distribusi','short':'DIST','conf_pct':p,'conf':cl(p)}); break
    if np.mean(v[-5:])>vm*1.05 and np.mean(v[-5:])<vm*1.5 and (max(c[-5:])-min(c[-5:]))/max(av,1e-9)<1.2: sigs.append({'key':'stealth_accum','style':'accum','label':'Akum. Senyap','short':'STL','conf_pct':68,'conf':'med'})
    if n>=7 and o[last]>c[-2]*1.005 and vr(last)>2.0 and (max(c[-7:-2])-min(c[-7:-2]))/max(av,1e-9)<2.0: sigs.append({'key':'markup','style':'purple','label':'Markup','short':'MRK','conf_pct':int(min(60+(vr(last)-2.0)/3.0*35,95)),'conf':'high'})
    if n>=3:
        pd_, tr = c[-2]-c[-3], c[-1]-c[-2]
        if pd_<0 and abs(pd_)/max(av,1e-9)>1.5 and tr>abs(pd_)*0.6 and vr(last-1)>1.5: sigs.append({'key':'shakeout','style':'warn','label':'Shakeout','short':'SKO','conf_pct':int(min(55+abs(pd_)/max(av,1e-9)*8,88)),'conf':'high'})
    if _detect_div(df, ind_s['rsi'], 'rsi'): sigs.append(_detect_div(df, ind_s['rsi'], 'rsi'))
    if _detect_div(df, ind_s['cmf'], 'cmf'): sigs.append(_detect_div(df, ind_s['cmf'], 'cmf'))
    if _detect_trap(df): sigs.append(_detect_trap(df))
    sigs.sort(key=lambda x: x['conf_pct'], reverse=True)
    return {'signals': sigs, 'dominant': sigs[0] if sigs else None, 'narasi_tech': '', 'narasi_plain': ''}

def score_trend(i):
    a50, a20 = i['above_ema50'], i['above_ema20']
    if a50 and a20: return min(16.0 + (2.0 if i.get('ema200_ok') and i.get('above_ema200') else 0.0) + (2.0 if i.get('ema20_rising') else 0.0), 20.0), "bull"
    elif a50: return 10.0, "bull"
    elif a20: return 4.0, "neut"
    else: return 0.0, "bear"

def score_rsi(i):
    r = i['rsi_val']
    if r>75: return 2.0, "bear"
    elif 40<=r<=65: return min(12.0+(r-40)/25*3+(3.0 if i['rsi_rising'] else 0), 18.0), "bull"
    elif 65<r<=75: return 9.0, "neut"
    elif 30<=r<40: return 7.0, "neut"
    else: return 3.0, "bear"

def score_cmf(i):
    c = i['cmf_val']
    if c>0: return min(20.0*min(c/0.25,1.0)+(1.5 if i['cmf_rising'] else 0), 20.0), "bull"
    elif c>-0.05: return 4.0, "neut"
    else: return 0.0, "bear"

def score_vol(i):
    s = i['vol_spike']
    if s>=2.5: return 12.0, "bull"
    elif s>=1.5: return min(6.0+6.0*((s-1.5)/1.0), 12.0), "bull"
    elif s>=1.2: return 4.0, "neut"
    else: return 0.0, "neut"

def score_sq(i):
    if i['squeeze_release']: return 10.0, "bull"
    elif i['in_squeeze']: return 6.0, "neut"
    else: return 2.0, "neut"

def score_adx(i):
    s, b = i.get('adx_strength','weak'), i.get('adx_bullish_dir',False)
    if s=='strong': return 20.0 if b else 4.0, "bull" if b else "bear"
    elif s=='moderate': return 13.0 if b else 7.0, "bull" if b else "neut"
    else: return 8.0, "neut"

def compute_total_score(i, regime=None):
    sts, stsig = score_trend(i); rss, rssig = score_rsi(i); cms, cmsig = score_cmf(i); vos, vosig = score_vol(i); sqs, sqsig = score_sq(i); axs, axsig = score_adx(i)
    tot = sts+rss+cms+vos+sqs+axs
    if not i['above_ema50'] and not i['above_ema20']: tot = min(tot, 40.0)
    bd = {'trend':(round(sts,1),stsig),'rsi':(round(rss,1),rssig),'cmf':(round(cms,1),cmsig),'volume':(round(vos,1),vosig),'squeeze':(round(sqs,1),sqsig),'adx':(round(axs,1),axsig)}
    if regime and regime.get('state') not in (None,'unknown','transisi'):
        adj = 0.0
        if regime['state']=='trending_bull':
            if sqsig=='bull': adj += sqs*0.15
            if axsig=='bull': adj += axs*0.10
        elif regime['state']=='choppy':
            if rssig=='bull': adj += rss*0.12
            if sqsig=='bull': adj -= sqs*0.10
        elif regime['state']=='trending_bear': adj -= 3.0
        tot += adj
    return round(max(min(tot,100),0), 1), bd

def compute_market_regime(ihsg):
    if ihsg is None or len(ihsg) < 60: return {'state':'unknown','label':'Data IHSG kurang','adx':0.0}
    try: ind, _ = calculate_indicators(ihsg)
    except: return {'state':'unknown','label':'Gagal hitung IHSG','adx':0.0}
    s, b, at = ind['adx_strength'], ind['adx_bullish_dir'], ind['above_ema50'] and ind['above_ema20']
    if s=='strong' and b and at: st, lb = 'trending_bull', '📈 Trending Bullish'
    elif s=='strong' and not b: st, lb = 'trending_bear', '📉 Trending Bearish'
    elif s=='weak': st, lb = 'choppy', '↔️ Choppy'
    else: st, lb = 'transisi', '🔄 Transisi'
    return {'state':st, 'label':lb, 'adx':ind['adx_val']}

def compute_rs_vs(ihsg, sdf, lb=20):
    if ihsg is None or len(ihsg) < lb+1 or len(sdf) < lb+1: return 50.0, 'N/A'
    comb = pd.DataFrame({'s':sdf['Close'], 'i':ihsg['Close']}).dropna()
    if len(comb) < lb+1: return 50.0, 'N/A'
    er = ((comb['s'].iloc[-1]/comb['s'].iloc[-lb-1]-1) - (comb['i'].iloc[-1]/comb['i'].iloc[-lb-1]-1))*100
    rs = clamp_prob(50+er*2.5, 5, 95)
    lb = "Outperform Kuat" if rs>=70 else ("Outperform" if rs>=55 else ("Sejalan" if rs>=45 else ("Underperform" if rs>=30 else "Underperform Kuat")))
    return round(rs,1), lb

INTRADAY_PARAMS = {'atr_sl_mult': 1.5, 'min_rr1': 1.5, 'min_rr2': 2.5, 'min_rr3': 4.0, 'ts_rule': "Trail 1× ATR; BEP di TP1", 'buy_zone_atr_mult': 0.35}
SWING_PARAMS = {'atr_sl_mult': 2.0, 'min_rr1': 2.0, 'min_rr2': 3.5, 'min_rr3': 5.5, 'ts_rule': "BEP di TP1; Trail 2× ATR", 'buy_zone_atr_mult': 0.5}

def idx_tick_of(p):
    p = float(p)
    if p<200: return 1
    if p<500: return 2
    if p<2000: return 5
    if p<5000: return 10
    return 25

def snap(p, d="floor"):
    t = idx_tick_of(p)
    return int(np.ceil(p/t)*t) if d=="ceil" else int(np.floor(p/t)*t)

def build_plan(lc, atr, mp):
    sl_d = max(atr * mp['atr_sl_mult'], lc * 0.015)
    sl = snap(lc - sl_d, "floor")
    sl_d_a = max(lc - sl, sl_d)
    tp1 = snap(lc + sl_d_a * mp['min_rr1'], "ceil")
    tp2 = snap(lc + sl_d_a * mp['min_rr2'], "ceil")
    tp3 = snap(lc + sl_d_a * mp['min_rr3'], "ceil")
    bmin = snap(lc - mp['buy_zone_atr_mult'] * atr, "floor")
    bmax = snap(lc, "ceil")
    if bmax >= tp1: bmax = snap(tp1 - idx_tick_of(tp1), "floor")
    if bmin <= sl: bmin = snap(sl + idx_tick_of(sl), "ceil")
    if bmax < bmin: bmax = bmin
    return {'stop_loss':float(sl),'tp1':float(tp1),'tp2':float(tp2),'tp3':float(tp3),'buy_min':float(bmin),'buy_max':float(bmax),'sl_dist':sl_d_a,'rr1':round((tp1-lc)/sl_d_a,2),'rr2':round((tp2-lc)/sl_d_a,2),'rr3':round((tp3-lc)/sl_d_a,2),'ts_rule':mp['ts_rule'],'partial_plan':"TP1: exit 40% → BEP | TP2: exit 40% | TP3/Trail: 20%"}

def compute_gap_risk(lc, sl):
    arb = 0.15; wc = snap(lc*(1-arb), "ceil")
    sld = max((lc-sl)/lc*100, 0.0); ua = max(arb*100-sld, 0.0)
    er = round(ua/(arb*100), 2) if arb>0 else 0.0
    rl, rc = ("Rawan Gap", "#f85149") if er>=0.7 else (("Waspada", "#e3b341") if er>=0.4 else ("Aman", "#3fb950"))
    return {'risk_label':rl, 'risk_color':rc}

def compute_liq_impact(pv, adtv):
    if adtv <= 0: return {'label':'N/A', 'color':'#8b949e'}
    ip = pv / adtv * 100
    l, c = ("Tinggi", "#f85149") if ip>=10 else (("Sedang", "#e3b341") if ip>=5 else ("Rendah", "#3fb950"))
    return {'label':l, 'color':c}

def compute_corr_matrix(ad, tjk, lb=60):
    ret = {}
    for t in tjk:
        df = ad.get(t)
        if df is None or len(df) < lb+1: continue
        r = df['Close'].tail(lb+1).pct_change().dropna()
        if len(r) >= lb//2: ret[t] = r.reset_index(drop=True)
    if len(ret) < 2: return pd.DataFrame()
    return pd.DataFrame(ret).corr()

def flag_corr_clusters(cm, th=0.7):
    if cm.empty: return []
    p = []
    for i in range(len(cm.columns)):
        for j in range(i+1, len(cm.columns)):
            c = cm.iloc[i,j]
            if pd.notna(c) and c >= th: p.append((cm.columns[i], cm.columns[j], round(float(c),2)))
    return sorted(p, key=lambda x: -x[2])

def download_chunk(tk, pdays, intv):
    sd = (datetime.now() - timedelta(days=pdays)).strftime('%Y-%m-%d')
    ed = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    res = {}
    def _ext(d, t):
        try:
            df = d[t].dropna(subset=['Close']); return df if not df.empty else None
        except: return None
    try:
        d = yf.download(" ".join(tk), start=sd, end=ed, interval=intv, group_by='ticker', auto_adjust=True, progress=False, threads=True, timeout=30)
        if d.empty: raise ValueError("Empty")
        is_m = isinstance(d.columns, pd.MultiIndex)
        if len(tk)==1:
            if not is_m and 'Close' in d.columns:
                df = d.dropna(subset=['Close'])
                if not df.empty: res[tk[0]] = df
            elif is_m:
                r = _ext(d, tk[0])
                if r is not None: res[tk[0]] = r
        else:
            if is_m:
                for t in tk:
                    if t in d.columns.get_level_values(0).unique():
                        r = _ext(d, t)
                        if r is not None: res[t] = r
    except:
        for t in tk:
            try:
                ds = yf.download(t, start=sd, end=ed, interval=intv, auto_adjust=True, progress=False, timeout=15)
                if not ds.empty and 'Close' in ds.columns:
                    dc = ds.dropna(subset=['Close'])
                    if not dc.empty: res[t] = dc
            except: pass
    return res

def _fetch_live(tk):
    try:
        p = yf.Ticker(tk).fast_info.get('last_price') or yf.Ticker(tk).fast_info.get('lastPrice')
        if p and float(p) > 0: return tk, float(p)
    except: pass
    return tk, None

def fetch_live_prices(tjk):
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        fs = {ex.submit(_fetch_live, t): t for t in tjk}
        dn, pn = concurrent.futures.wait(fs, timeout=30, return_when=concurrent.futures.ALL_COMPLETED)
        for f in pn: f.cancel()
        for f in dn:
            try:
                t, p = f.result()
                if p is not None: res[t] = p
            except: pass
    return res

@st.cache_data(ttl=20, show_spinner=False)
def _cached_live(tjk_tup): return fetch_live_prices(list(tjk_tup))

def quant_strategy_engine(ad, cfg, tm, ihsg=None, regime=None):
    mp = INTRADAY_PARAMS if tm == "Intraday (Fast Trade)" else SWING_PARAMS
    res, skip, all_bd = [], {}, []
    for t, df in ad.items():
        if len(df) < 60: skip[t] = "candle < 60"; continue
        df = df.copy()
        try: lc = float(df['Close'].iloc[-1])
        except: skip[t] = "harga error"; continue
        tr, rs = is_tradeable_stock(df, lc)
        if not tr: skip[t] = rs; continue
        try: ind, ind_s = calculate_indicators(df)
        except Exception as e: skip[t] = f"ind error: {e}"; continue
        lc = ind['last_close']
        if lc < cfg['min_price'] or lc > cfg['max_price']: skip[t] = "filter harga"; continue
        if ind['adtv'] < cfg['min_adtv']: skip[t] = "ADTV rendah"; continue
        tot, bd = compute_total_score(ind, regime)
        all_bd.append(bd)
        if tot < cfg['min_score_threshold']: skip[t] = "score rendah"; continue
        gr = "A" if tot >= 80 else ("B" if tot >= 65 else "C")
        vc = analyse_volume_context(df); tp = analyse_tape(df, ind_s); bd_ = analyse_bandar(df, ind_s)
        pl = build_plan(lc, ind['atr_val'], mp)
        gr_risk = compute_gap_risk(lc, pl['stop_loss'])
        rs_sc, rs_lb = compute_rs_vs(ihsg, df, 20)
        lps = float(pl['buy_max']) - pl['stop_loss']
        if lps <= 0: skip[t] = "lps <= 0"; continue
        rr = cfg['total_capital'] * (cfg['capital_risk_limit_pct'] / 100.0)
        lots = int(rr / lps / 100)
        max_a = cfg['total_capital'] * (cfg['max_capital_allocation_pct'] / 100.0)
        rc = lots * 100 * pl['buy_max']
        if rc > max_a: lots, rc = int(max_a / (100 * pl['buy_max'])), int(max_a / (100 * pl['buy_max'])) * 100 * pl['buy_max']
        if lots < 1: skip[t] = "modal kurang"; continue
        li = compute_liq_impact(rc, ind['adtv'])
        res.append({
            "Ticker": t.split('.')[0], "_tjk": t, "Score": tot, "Grade": gr, "Last Price": int(round(lc)),
            "Buy Min": pl['buy_min'], "Buy Max": pl['buy_max'], "TP1": int(pl['tp1']), "TP2": int(pl['tp2']), "TP3": int(pl['tp3']),
            "Stop Loss": int(pl['stop_loss']), "ATR": round(ind['atr_val'],1), "RSI": round(ind['rsi_val'],1), "CMF": round(ind['cmf_val'],3),
            "ADX": ind['adx_val'], "ADX Strength": ind['adx_strength'], "ADX Bullish": ind['adx_bullish_dir'],
            "TS Kriteria": pl['ts_rule'], "Partial Plan": pl['partial_plan'], "Lots": int(lots), "Alokasi (Rp)": rc,
            "RS Score": rs_sc, "RS Label": rs_lb, "Gap Risk": gr_risk['risk_label'], "Liq Impact": li['label'],
            "_ind": ind, "_vol_ctx": vc, "_tape": tp, "_bandar": bd_, "_gap_risk": gr_risk, "_liq_impact": li, "_breakdown": bd
        })
    
    if all_bd:
        bull_count = sum(1 for b in all_bd if b.get('trend', (0.0, 'neut'))[1] == 'bull')
        total_bd = len(all_bd)
        b_pct = round(bull_count / total_bd * 100, 1)
        if b_pct >= 65: b_lb = "Breadth Kuat (Bullish)"
        elif b_pct >= 45: b_lb = "Breadth Netral"
        else: b_lb = "Breadth Lemah (Bearish)"
        br = {'bullish_pct': b_pct, 'total': total_bd, 'label': b_lb}
    else:
        br = {'bullish_pct': 0.0, 'total': 0, 'label': 'Tidak ada data'}
        
    st.session_state['scan_meta'] = {'total_input': len(ad), 'lolos': len(res), 'difilter': len(skip), 'skipped': skip, 'breadth': br, 'regime': regime}
    if not res: return pd.DataFrame()
    
    lps = _cached_live(tuple(sorted([r["_tjk"] for r in res])))
    for r in res:
        lp = lps.get(r["_tjk"])
        if lp and np.isfinite(float(lp)) and float(lp) > 0: r["Live Price"], r["Live Src"] = int(round(float(lp))), "live"
        else: r["Live Price"], r["Live Src"] = int(r["Last Price"]), "delayed"
        lpf, slf = float(r["Live Price"]), float(r["Stop Loss"])
        if not (lpf <= slf * (1 - 0.015)):
            lrr = compute_live_rr(lpf, slf, float(r["TP1"]), float(r["TP2"]), float(r["TP3"]))
            r["Risk%"] = f"-{round(max(lrr['risk_pct'],0),1)}%"
            r["Upside TP1"] = f"{'+' if lrr['up1_pct']>=0 else ''}{round(lrr['up1_pct'],1)}%"
            r["R/R TP1"] = f"1:{round(lrr['rr1'],2)}"
            r["R/R TP2"] = f"1:{round(lrr['rr2'],2)}"
            r["R/R TP3"] = f"1:{round(lrr['rr3'],2)}"
        else:
            r["Risk%"] = f"-{round((float(r['Buy Max'])-slf)/float(r['Buy Max'])*100,1)}%"
            r["Upside TP1"] = f"+{round((float(r['TP1'])-float(r['Buy Max']))/float(r['Buy Max'])*100,1)}%"
            r["R/R TP1"] = f"1:{round((float(r['TP1'])-float(r['Buy Max']))/max(float(r['Buy Max'])-slf,1e-6),2)}"
            r["R/R TP2"] = f"1:{round((float(r['TP2'])-float(r['Buy Max']))/max(float(r['Buy Max'])-slf,1e-6),2)}"
            r["R/R TP3"] = f"1:{round((float(r['TP3'])-float(r['Buy Max']))/max(float(r['Buy Max'])-slf,1e-6),2)}"
        pr = estimate_prob(r["Score"], r["Grade"], lpf, float(r["Buy Min"]), float(r["Buy Max"]), slf, float(r["TP1"]), float(r["TP2"]), float(r["TP3"]), float(r["ATR"]), r["_ind"], r["_vol_ctx"], r["_tape"], r["_bandar"])
        r.update(pr)
        del r["_tjk"]
    df_o = pd.DataFrame(res)
    def _vr(row):
        v = _check_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
        return {"valid":0,"waiting":1,"expired":2}[v["status"]]
    df_o["_vr"] = df_o.apply(_vr, axis=1)
    return df_o.sort_values(by=["_vr","Prob Entry","Score"], ascending=[True,False,False]).drop(columns=["_vr"]).reset_index(drop=True)

def compute_indicator_history(df, n=10):
    if len(df) < 60+n: n = max(1, len(df)-60)
    if n <= 0: return pd.DataFrame()
    try: ind_f, ser_f = calculate_indicators(df)
    except: return pd.DataFrame()
    rows = []
    vma15 = df['Volume'].rolling(15).mean()
    for b in range(n, 0, -1):
        ei = len(df)-b
        if ei < 60: continue
        w = df.iloc[:ei]; adx = calculate_adx(w); lc = float(w['Close'].iloc[-1])
        slc = {
            'last_close': lc, 'ema200_available': len(w)>=200, 'above_ema200': lc>float(ser_f['ema200'].iloc[ei-1]) if len(w)>=200 else False,
            'above_ema50': lc>float(ser_f['ema50'].iloc[ei-1]), 'above_ema20': lc>float(ser_f['ema20'].iloc[ei-1]),
            'ema20_rising': float(ser_f['ema20'].iloc[ei-1])>float(ser_f['ema20'].iloc[ei-3]) if ei>=3 else False,
            'atr_val': float(ser_f['atr'].iloc[ei-1]), 'atr_pct': float(ser_f['atr'].iloc[ei-1])/lc if lc>0 else 0,
            'cmf_val': float(ser_f['cmf'].iloc[ei-1]), 'cmf_rising': float(ser_f['cmf'].iloc[ei-1])>float(ser_f['cmf'].iloc[ei-2]),
            'rsi_val': float(ser_f['rsi'].iloc[ei-1]), 'rsi_rising': float(ser_f['rsi'].iloc[ei-1])>float(ser_f['rsi'].iloc[ei-2]),
            'in_squeeze': bool(ser_f['squeeze'].iloc[ei-1]), 'squeeze_release': (not bool(ser_f['squeeze'].iloc[ei-1])) and bool(ser_f['squeeze'].iloc[ei-2]) if ei>=2 else False,
            'adx_val': adx['adx'], 'adx_di_plus': adx['di_plus'], 'adx_di_minus': adx['di_minus'], 'adx_bullish_dir': adx['bullish_dir'], 'adx_strength': adx['strength'],
            'vol_spike': float(df['Volume'].iloc[ei-1])/max(float(vma15.iloc[ei-1]),1.0), 'adtv': 0.0
        }
        sc, _ = compute_total_score(slc)
        rows.append({'date': df.index[ei-1], 'close': lc, 'score': sc, 'rsi': slc['rsi_val'], 'cmf': slc['cmf_val'], 'adx': slc['adx_val']})
    rows.append({'date': df.index[-1], 'close': ind_f['last_close'], 'score': compute_total_score(ind_f)[0], 'rsi': ind_f['rsi_val'], 'cmf': ind_f['cmf_val'], 'adx': ind_f['adx_val']})
    return pd.DataFrame(rows)

JOURNAL_COLS = ['tanggal_sinyal','ticker','mode','harga_saat_sinyal','buy_min','buy_max','stop_loss','tp1','tp2','tp3','score','grade','status','tanggal_resolusi','hari_berjalan']

def _jpath():
    try: return os.path.join(os.path.dirname(os.path.abspath(__file__)), "jurnal_sinyal.csv")
    except: return os.path.join(os.getcwd(), "jurnal_sinyal.csv")

def load_journal():
    p = _jpath()
    if not os.path.exists(p): return pd.DataFrame(columns=JOURNAL_COLS)
    try:
        j = pd.read_csv(p)
        for c in JOURNAL_COLS:
            if c not in j.columns: j[c] = np.nan
        return j[JOURNAL_COLS]
    except: return pd.DataFrame(columns=JOURNAL_COLS)

def append_journal(fdf, tm):
    p, ex = _jpath(), load_journal()
    ts = datetime.now().strftime('%Y-%m-%d')
    ek = set(zip(ex['tanggal_sinyal'].astype(str), ex['ticker'].astype(str), ex['mode'].astype(str))) if not ex.empty else set()
    nr = []
    for _, r in fdf.iterrows():
        k = (ts, r['Ticker'], tm)
        if k in ek: continue
        nr.append({'tanggal_sinyal':ts,'ticker':r['Ticker'],'mode':tm,'harga_saat_sinyal':r['Live Price'],'buy_min':r['Buy Min'],'buy_max':r['Buy Max'],'stop_loss':r['Stop Loss'],'tp1':r['TP1'],'tp2':r['TP2'],'tp3':r['TP3'],'score':r['Score'],'grade':r['Grade'],'status':'Open','tanggal_resolusi':'','hari_berjalan':0})
    if not nr: return 0
    try: pd.concat([ex, pd.DataFrame(nr)]).to_csv(p, index=False)
    except: return 0
    return len(nr)

def eval_journal(jdf):
    if jdf.empty: return jdf
    j = jdf.copy()
    om = j['status'].astype(str) == 'Open'
    if not om.any(): return j
    for i in j[om].index:
        r = j.loc[i]
        tjk = r['ticker'] if str(r['ticker']).upper().endswith(".JK") else f"{r['ticker']}.JK"
        try:
            sd = pd.to_datetime(r['tanggal_sinyal'])
            ds = max((datetime.now()-sd.to_pydatetime()).days+2, 3)
            df = download_chunk([tjk], ds, "1d").get(tjk)
            if df is None or df.empty: continue
            df = df[df.index >= sd]
            if df.empty: continue
            st_, res_i = 'Open', None
            for idx, row in df.iterrows():
                if row['Low'] <= float(r['stop_loss']): st_, res_i = 'SL', idx; break
                if row['High'] >= float(r['tp3']): st_, res_i = 'TP3', idx; break
                if row['High'] >= float(r['tp2']): st_, res_i = 'TP2', idx; break
                if row['High'] >= float(r['tp1']): st_, res_i = 'TP1', idx; break
            j.at[i, 'hari_berjalan'] = (datetime.now()-sd.to_pydatetime()).days
            if st_ != 'Open':
                j.at[i, 'status'] = st_
                j.at[i, 'tanggal_resolusi'] = str(res_i.date()) if res_i is not None else ''
        except: continue
    try: j.to_csv(_jpath(), index=False)
    except: pass
    return j

def _check_validity(lp, sl, bmin, bmax):
    if lp <= sl * (1 - 0.015):
        return {'status':'expired','title':'⚠️ Sinyal Tidak Valid','detail':f'Harga ({fmt_num(lp)}) breakdown SL ({fmt_num(sl)}).','action':'Skip.','card_cls':'signal-expired','banner_cls':'expired-banner','title_color':'#f85149'}
    elif lp < bmin:
        return {'status':'waiting','title':'⏳ Di Bawah Zona','detail':f'Harga ({fmt_num(lp)}) di bawah zona ({fmt_num(bmin)}–{fmt_num(bmax)}).','action':'Tunggu masuk zona.','card_cls':'signal-waiting','banner_cls':'waiting-banner','title_color':'#e3b341'}
    elif lp > bmax:
        return {'status':'waiting','title':'⏳ Di Atas Zona','detail':f'Harga ({fmt_num(lp)}) di atas zona ({fmt_num(bmin)}–{fmt_num(bmax)}).','action':'Tunggu pullback.','card_cls':'signal-waiting','banner_cls':'waiting-banner','title_color':'#e3b341'}
    else: return {'status':'valid','title':'','detail':'','action':'','card_cls':'','banner_cls':'','title_color':''}

def compute_live_rr(lp, sl, tp1, tp2, tp3):
    rps, lps = max(lp-sl, 1e-6), max(lp, 1e-6)
    return {'rr1':(tp1-lp)/rps,'rr2':(tp2-lp)/rps,'rr3':(tp3-lp)/rps,'risk_pct':(lp-sl)/lps*100,'up1_pct':(tp1-lp)/lps*100,'up2_pct':(tp2-lp)/lps*100,'up3_pct':(tp3-lp)/lps*100}

def estimate_prob(score, grade, lp, bmin, bmax, sl, tp1, tp2, tp3, atr, ind, vc, tape, bandar):
    base = float(score) * 0.65
    gb = {"A":8.0,"B":4.0,"C":0.0}.get(grade, 0.0)
    sa = -35.0 if (sl and lp <= sl) else (12.0 if bmin <= lp <= bmax else (-4.0 if lp < bmin else -8.0 - min(((lp-bmax)/max(bmax,1.0))*80.0, 18.0)))
    ta = (3.0 if ind.get("above_ema20") else 0) + (4.0 if ind.get("above_ema50") else 0) + (3.0 if ind.get("above_ema200") else 0) + (3.0 if ind.get("ema20_rising") else 0)
    rsi = ind.get("rsi_val", 50.0)
    ma = (5.0 if 45<=rsi<=65 else (-2.0 if 65<rsi<=75 else (-8.0 if rsi>75 else -5.0)))
    cmf = ind.get("cmf_val", 0.0)
    ma += 4.0 if cmf > 0.05 else (-5.0 if cmf < -0.05 else 0.0)
    va = 0.0
    if vc.get("valid"):
        vr, cd = vc.get("vol_ratio",0), vc.get("candle_dir")
        if cd=="bullish" and vr>=1.3: va += 6.0
        elif vr>=1.5: va += 3.0
        elif cd=="bearish" and vr>=1.3: va -= 6.0
    ta_ = 0.0
    for s in tape.get("signals",[]):
        if isinstance(s,(tuple,list)) and len(s)>=2:
            if s[1]=="accum": ta_ += 5.0
            elif s[1]=="distrib": ta_ -= 6.0
            elif s[1]=="warn": ta_ -= 3.0
    ba_, dom = 0.0, bandar.get("dominant")
    if dom:
        cw = {"high":7.0,"med":4.0,"low":2.0}.get(dom.get("conf"),2.0)
        if dom.get("style")=="accum": ba_ += cw
        elif dom.get("style")=="distrib": ba_ -= cw
    aa = 0.0
    if ind.get("adx_strength")=="strong": aa += 5.0 if ind.get("adx_bullish_dir") else -6.0
    elif ind.get("adx_strength")=="moderate": aa += 2.0 if ind.get("adx_bullish_dir") else -2.0
    ap = atr/max(lp,1.0)
    va_ = -8.0 if ap>0.08 else (-4.0 if ap>0.05 else (3.0 if 0.015<=ap<=0.04 else 0.0))
    pe = clamp_prob(base+gb+sa+ta+ma+va+ta_+ba_+aa+va_)
    if lp <= sl: pe = min(pe, 15.0)
    lrr = compute_live_rr(lp, sl, tp1, tp2, tp3)
    rb1, rb2, rb3 = min(max((lrr['rr1']-1.2)*6.0,-8.0),10.0), min(max((lrr['rr2']-2.0)*4.0,-10.0),8.0), min(max((lrr['rr3']-3.0)*3.0,-12.0),6.0)
    pt1 = clamp_prob(pe+rb1-ap*35.0)
    pt2 = clamp_prob(pe-12.0+rb2-ap*45.0)
    pt3 = clamp_prob(pe-24.0+rb3-ap*55.0)
    psl = 95.0 if lp<=sl else clamp_prob(100.0-pt1+ap*45.0, 5.0, 90.0)
    return {"Prob Entry":pe, "Prob TP1":pt1, "Prob TP2":min(pt2,pt1), "Prob TP3":min(pt3,pt2), "Prob SL":psl, "Confidence":prob_label(pe)}

def clamp_prob(x, lo=5.0, hi=95.0):
    try: return round(max(lo, min(hi, float(x))), 1)
    except: return lo

def prob_label(p):
    if p>=75: return "Tinggi"
    if p>=60: return "Sedang"
    if p>=45: return "Spekulatif"
    return "Rendah"

def compute_best_buy_ev(row):
    reasons, tot = [], 0.0
    v = _check_validity(row["Live Price"], row["Stop Loss"], row["Buy Min"], row["Buy Max"])
    if v['status']=='valid': tot += 30; reasons.append("✅ Zona beli")
    elif v['status']=='waiting':
        if row["Live Price"] > row["Buy Max"]: tot += 4; reasons.append("⏳ Di atas zona")
        else: tot += 10; reasons.append("⏳ Di bawah zona")
    else: return -99.0, 0.0, []
    tot += (row["Score"]/100.0)*25; reasons.append(f"📊 Score {row['Score']}")
    tot += {"A":10,"B":6,"C":2}.get(row.get("Grade","C"),2)
    dom = row.get("_bandar",{}).get("dominant")
    if dom:
        cp = {"high":15,"med":8,"low":3}.get(dom.get("conf"),3)
        if dom.get("style")=="distrib": tot -= cp
        else: tot += cp; reasons.append(f"🔍 Bandar: {dom.get('label','')}")
    if [s for s in row.get("_tape",{}).get("signals",[]) if s[1]=="accum"]: tot += 10
    vc = row.get("_vol_ctx",{})
    if vc.get("valid") and vc.get("vol_ratio",0)>=1.3 and vc.get("candle_dir")=="bullish": tot += 10
    if row.get("RS Label","N/A") != "N/A":
        ra = round((row.get("RS Score",50.0)-50.0)/45.0*7.0, 1); tot += ra
    try:
        r1 = float(str(row["R/R TP1"]).split(":")[1])
        r2 = float(str(row["R/R TP2"]).split(":")[1])
        r3 = float(str(row["R/R TP3"]).split(":")[1])
    except: r1, r2, r3 = 1.5, 2.5, 4.0
    p1, p2, p3, ps = row["Prob TP1"]/100, row["Prob TP2"]/100, row["Prob TP3"]/100, row["Prob SL"]/100
    ev = (0.4*p1*r1) + (0.4*p2*r2) + (0.2*p3*r3) - (ps*1.0)
    return round(ev,2), round(max(min(tot,100),0),1), reasons

def pick_best_buy(df):
    if df.empty: return None, 0.0, [], False
    bt, be, br = None, -99.0, []
    for _, r in df.iterrows():
        if r["Live Price"] > r["Buy Max"]: continue
        ev, add_sc, reas = compute_best_buy_ev(r)
        if ev > 0 and ev > be: be, br, bt = ev, reas, r["Ticker"]
    if bt is None: return None, 0.0, [], False
    return bt, be, br, True

def get_calibrated_probs(journal_df):
    if journal_df.empty: return {}
    resolved = journal_df[journal_df['status'].isin(['TP1','TP2','TP3','SL'])]
    if len(resolved) < 20: return {}
    bins = [(50, 60), (60, 70), (70, 80), (80, 90), (90, 100)]
    cal = {}
    for lo, hi in bins:
        mask = (resolved['score'] >= lo) & (resolved['score'] < hi)
        bin_data = resolved[mask]
        if len(bin_data) > 0:
            wins = bin_data[bin_data['status'].isin(['TP1','TP2','TP3'])]
            cal[(lo, hi)] = round(len(wins) / len(bin_data) * 100, 1)
    return cal

def _pill(l, s): return f'<span class="ind-pill ind-{s}">{l}</span>'
def _tpill(s, st, c): return f'<span class="tape-pill tape-{st}">{s} {c}%</span>'
def _gb(g): return f'<span class="grade-{g}">Grade {g}</span>'
def _adx_b(v, s, b): return f'<span class="adx-info">ADX {v:.0f} {"▲" if b else "▼"} {s}</span>'

def _html_vc(vc):
    if not vc.get('valid'): return ''
    dc = {'bullish':'#3fb950','bearish':'#f85149','doji':'#8b949e'}.get(vc['candle_dir'],'#8b949e')
    di, dl = {'bullish':'▲','bearish':'▼','doji':'—'}.get(vc['candle_dir'],'—'), {'bullish':'Bullish','bearish':'Bearish','doji':'Doji'}.get(vc['candle_dir'],'—')
    vr = vc['vol_ratio']
    bc, vl = ('#3fb950', f'{vr:.1f}× spike') if vr>=2.0 else (('#e3b341', f'{vr:.1f}× atas rata') if vr>=1.3 else (('#8b949e', f'{vr:.1f}× normal') if vr>=0.7 else ('#f85149', f'{vr:.1f}× sepi')))
    return f'<div class="vol-ctx"><div style="display:flex;justify-content:space-between;"><span style="font-size:0.68rem;color:#8b949e;">VOLUME KONTEKS</span><span style="font-size:0.72rem;font-weight:700;color:{dc};">{di} {dl}</span></div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.3rem;margin-top:0.25rem;"><div><div style="font-size:0.6rem;color:#8b949e;">Vol vs MA</div><div style="font-size:0.7rem;font-weight:700;color:{bc};">{vl}</div></div><div><div style="font-size:0.6rem;color:#8b949e;">Body</div><div style="font-size:0.7rem;font-weight:700;color:#c9d1d9;">{int(vc["body_pct"]*100)}%</div></div><div><div style="font-size:0.6rem;color:#8b949e;">Close Pos</div><div style="font-size:0.7rem;font-weight:700;color:#c9d1d9;">{int(vc["close_pos"]*100)}%</div></div></div><div class="vol-bar-track"><div class="vol-bar-fill" style="width:{min(int(vr/3*100),100)}%;background:{bc};"></div></div></div>'

def _html_tb(tape, bandar):
    p = []
    if tape.get('signals'): p.append(f'<div style="margin-bottom:0.25rem;"><span style="font-size:0.6rem;color:#8b949e;">TAPE</span> {"".join(_tpill(s[3],s[1],s[4]) for s in tape["signals"][:3])}</div>')
    if bandar.get('signals'): p.append(f'<div style="margin-bottom:0.25rem;"><span style="font-size:0.6rem;color:#8b949e;">BANDAR</span> {"".join(_tpill(s["short"],s["style"],s["conf_pct"]) for s in bandar["signals"][:3])}</div>')
    return f'<div class="section-divider"></div><div>{" ".join(p)}</div>' if p else ''

def _html_ps(lp, rc, bmin, bmax, ls):
    if bmin <= lp <= bmax: c, i, l = "#3fb950", "●", "Dalam Zona"
    elif lp < bmin: c, i, l = "#58a6ff", "↓", "Di Bawah Zona"
    else: c, i, l = "#e3b341", "↑", "Di Atas Zona"
    sl, sc = "Live" if ls=="live" else "Delayed", "#3fb950" if ls=="live" else "#8b949e"
    rn = ""
    if rc != lp:
        d = lp-rc; s = "+" if d>=0 else ""
        rcol = "#3fb950" if d>=0 else "#f85149"
        rn = f'<span style="font-size:0.68rem;color:{rcol};margin-left:0.3rem;">{s}{d/rc*100:.1f}%</span>'
    return f'<div style="display:flex;justify-content:space-between;margin-bottom:0.4rem;padding:0.35rem 0.6rem;background:rgba(255,255,255,0.04);border-radius:6px;border-left:3px solid {c};"><div><span style="font-size:1.3rem;font-weight:800;color:{c};">{fmt_num(lp)}</span>{rn}</div><div style="text-align:right;"><div style="font-size:0.65rem;color:{sc};font-weight:700;">{sl}</div><div style="font-size:0.65rem;color:{c};font-weight:600;">{i} {l}</div></div></div>'

def render_cards(df, max_c=6, bt=None, cal_probs={}):
    if df.empty: st.info("ℹ️ Tidak ada saham yang lolos filter."); return
    cs = df.head(max_c)
    for i in range(0, len(cs), 3):
        batch, cols = cs.iloc[i:i+3], st.columns(len(cs.iloc[i:i+3]))
        for j, (_, r) in enumerate(batch.iterrows()):
            with cols[j]:
                bd = r.get("_breakdown",{})
                ph = "".join(_pill(f"{l} {bd[k][0]:.0f}", bd[k][1]) for k,l in [("trend","EMA"),("rsi","RSI"),("cmf","CMF"),("volume","VOL"),("squeeze","SQZ"),("adx","ADX")] if k in bd)
                v = _check_validity(r["Live Price"], r["Stop Loss"], r["Buy Min"], r["Buy Max"])
                is_best = r["Ticker"] == bt
                cls = "best-buy-card" if is_best else v['card_cls']
                ch = '<div><span class="best-buy-crown">👑 Best Buy</span></div>' if is_best else ''
                bh = f'<div class="{v["banner_cls"]}"><div style="font-size:0.78rem;font-weight:800;color:{v["title_color"]};">{v["title"]}</div><div style="font-size:0.68rem;color:#c9d1d9;">{v["detail"]}</div></div>' if v['status'] in ['expired','waiting'] else ''
                do, dc_ = '<div class="dimmed">' if v['status']=='expired' else '<div>', '</div>'
                cal_html = ""
                if cal_probs:
                    for lo, hi in cal_probs:
                        if lo <= r["Score"] < hi:
                            actual = cal_probs[(lo,hi)]
                            cal_html = f'<span style="font-size:0.6rem;color:#8b949e;">(Hist: {actual}%)</span>'
                            break
                html = f'<div class="metric-card {cls}">{ch}<div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span class="ticker">{r["Ticker"]}</span><div style="display:flex;gap:0.4rem;align-items:center;">{_gb(r["Grade"])}<span class="score-badge">Score {r["Score"]}</span></div></div><div style="margin-bottom:0.5rem;">{ph}</div>{_html_vc(r["_vol_ctx"])}{bh}{_html_ps(r["Live Price"], r["Last Price"], r["Buy Min"], r["Buy Max"], r.get("Live Src","delayed"))}{do}<div class="price-range">{fmt_num(r["Buy Min"])} – {fmt_num(r["Buy Max"])}</div><div class="label" style="margin-bottom:0.6rem;">Area Buy · ATR {r["ATR"]} {_adx_b(r["ADX"], r.get("ADX Strength","weak"), r.get("ADX Bullish",False))}</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.4rem;margin-bottom:0.6rem;border-top:1px solid #30363d;padding-top:0.4rem;"><div><div class="label">TP1 <span class="rr-badge">({r["R/R TP1"]})</span></div><div class="tp">{fmt_num(r["TP1"])} <span style="font-size:0.68rem;">{r.get("Upside TP1","")}</span></div></div><div><div class="label">TP2</div><div class="tp">{fmt_num(r["TP2"])}</div></div><div><div class="label">TP3</div><div class="tp" style="color:#bc8cff;">{fmt_num(r["TP3"])}</div></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin-bottom:0.4rem;"><div><div class="label">Stop Loss</div><div class="sl">{fmt_num(r["Stop Loss"])} <span style="font-size:0.68rem;">{r["Risk%"]}</span></div></div><div><div class="label">Trailing</div><div class="ts-rule" style="font-size:0.78rem;">{r["TS Kriteria"]}</div></div></div><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.35rem;margin-bottom:0.5rem;background:rgba(88,166,255,0.05);border:1px solid rgba(88,166,255,0.18);border-radius:6px;padding:0.45rem 0.5rem;"><div><div class="label">Prob Entry {cal_html}</div><div style="color:#58a6ff;font-weight:800;">{r["Prob Entry"]}%</div></div><div><div class="label">Prob TP1</div><div style="color:#3fb950;font-weight:800;">{r["Prob TP1"]}%</div></div><div><div class="label">Prob SL</div><div style="color:#f85149;font-weight:800;">{r["Prob SL"]}%</div></div></div><div style="border-top:1px solid #30363d;padding-top:0.4rem;display:grid;grid-template-columns:1fr 1fr;gap:0.3rem;font-size:0.75rem;"><div><div class="label">Lots</div><div style="color:#fff;font-weight:600">{int(r["Lots"])} Lot</div></div><div><div class="label">Alokasi</div><div style="color:#58a6ff;font-weight:600">{fmt_idr(r["Alokasi (Rp)"])}</div></div></div>{dc_}{_html_tb(r["_tape"], r["_bandar"])}</div>'
                st.markdown(html, unsafe_allow_html=True)

def _render_chart(df, plan, ticker):
    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#3fb950', decreasing_line_color='#f85149'))
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=['#3fb950' if c>=o else '#f85149' for c,o in zip(df['Close'],df['Open'])], yaxis='y2', opacity=0.3))
        for v, c, n in [(plan['tp3'],'#bc8cff','TP3'),(plan['tp2'],'#3fb950','TP2'),(plan['tp1'],'#3fb950','TP1'),(plan['buy_max'],'#e3b341','Buy Max'),(plan['buy_min'],'#e3b341','Buy Min'),(plan['stop_loss'],'#f85149','SL')]:
            fig.add_hline(y=v, line_dash="dash", line_color=c, annotation_text=f"{n}: {fmt_num(v)}", annotation_position="top left", annotation_font_size=10, annotation_font_color=c)
        fig.update_layout(title=f'{ticker} - Price & Plan', template='plotly_dark', height=500, yaxis=dict(title='Harga', side='left'), yaxis2=dict(title='Volume', overlaying='y', side='right', showgrid=False), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Altair Fallback
        chart_df = df.reset_index().rename(columns={df.index.name or 'index': 'Tanggal'})
        price_line = alt.Chart(chart_df).mark_line(color='#58a6ff').encode(x='Tanggal:T', y='Close:Q')
        layers = [price_line]
        for v, c, n in [(plan['tp3'],'#bc8cff','TP3'),(plan['tp2'],'#3fb950','TP2'),(plan['tp1'],'#3fb950','TP1'),(plan['buy_max'],'#e3b341','Buy Max'),(plan['buy_min'],'#e3b341','Buy Min'),(plan['stop_loss'],'#f85149','SL')]:
            rule = alt.Chart(pd.DataFrame({'y': [v]})).mark_rule(color=c, strokeDash=[4,3]).encode(y='y:Q')
            layers.append(rule)
        st.altair_chart(alt.layer(*layers).properties(height=400).configure_axis(labelColor='#8b949e', titleColor='#c9d1d9', gridColor='#21262d'), use_container_width=True)

def render_deep_dive(cfg, tm, cal_probs):
    st.markdown("### 🔬 Deep Dive")
    lf = st.session_state.get('last_final_df')
    st_tk = list(lf['Ticker']) if lf is not None and not lf.empty else []
    
    c1, c2 = st.columns([2,2])
    pk = "--"
    with c1:
        if st_tk:
            pk = st.selectbox("Dari scan:", ["--"]+st_tk)
        else:
            st.caption("Belum ada hasil scan. Ketik manual di kanan.")
    with c2:
        mt = st.text_input("Manual:", placeholder="ADRO")
        
    tr = mt.strip() if mt.strip() else (pk if pk != "--" else "")
    if not tr: 
        st.info("👆 Pilih atau ketik satu kode saham untuk memulai analisa.")
        return
        
    tjk = tr.upper() if tr.upper().endswith(".JK") else f"{tr.upper()}.JK"
    if not st.button("🔬 Analisa", type="primary"): return
    pd_, iv = (30,"60m") if tm=="Intraday (Fast Trade)" else (400,"1d")
    with st.spinner(f"Analisa {tjk}…"): df = download_chunk([tjk], pd_, iv).get(tjk)
    if df is None or df.empty or len(df) < 60: st.error("Data tidak cukup."); return
    try: ind, ind_s = calculate_indicators(df)
    except Exception as e: st.error(f"Error indikator: {e}"); return
    mp = INTRADAY_PARAMS if tm == "Intraday (Fast Trade)" else SWING_PARAMS
    sc, bd = compute_total_score(ind); pl = build_plan(ind['last_close'], ind['atr_val'], mp)
    vc, tp, bd_ = analyse_volume_context(df), analyse_tape(df, ind_s), analyse_bandar(df, ind_s)
    lp = _cached_live((tjk,)).get(tjk); lp = float(lp) if lp and float(lp)>0 else ind['last_close']
    st.markdown(f"### {tr.upper()} | Score: {sc} | {_gb('A' if sc>=80 else 'B' if sc>=65 else 'C')}")
    _render_chart(df, pl, tr.upper())
    cA, cB = st.columns(2)
    with cA:
        st.markdown("**Trading Plan**")
        st.markdown(f"- Buy: {fmt_num(pl['buy_min'])} – {fmt_num(pl['buy_max'])}\n- SL: {fmt_num(pl['stop_loss'])}\n- TP1: {fmt_num(pl['tp1'])}\n- TP2: {fmt_num(pl['tp2'])}\n- TP3: {fmt_num(pl['tp3'])}")
    with cB:
        st.markdown("**Sinyal Bandar**")
        if bd_.get('signals'):
            for s in bd_['signals'][:3]: st.markdown(f"- {_tpill(s['short'],s['style'],s['conf_pct'])} {s['label']}", unsafe_allow_html=True)
        else: st.write("Tidak ada.")

def render_compare():
    st.markdown("### ⚖️ Bandingkan")
    lf = st.session_state.get('last_final_df')
    if lf is None or lf.empty: st.info("Jalankan scan dulu."); return
    pk = st.multiselect("Pilih 2-4:", list(lf['Ticker']))
    if len(pk)<2: return
    r = [{"Metrik":m, **{t:f(lf[lf['Ticker']==t].iloc[0]) for t in pk}} for m,f in [("Score",lambda r:r['Score']),("Harga",lambda r:fmt_num(r['Live Price'])),("TP1",lambda r:fmt_num(r['TP1'])),("SL",lambda r:fmt_num(r['Stop Loss']))]]
    st.dataframe(pd.DataFrame(r), use_container_width=True, hide_index=True)

def render_journal():
    st.markdown("### 📓 Jurnal")
    j = load_journal()
    if j.empty: st.info("Jurnal kosong."); return
    if st.button("🔄 Cek Status"):
        with st.spinner("Cek harga..."): j = eval_journal(j)
        st.success("Update selesai.")
    res = j[j['status']!='Open']; w = res[res['status'].isin(['TP1','TP2','TP3'])]
    wr = len(w)/len(res)*100 if len(res)>0 else 0
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Total", len(j))
    with c2: st.metric("Win Rate", f"{wr:.0f}%")
    with c3: st.metric("Open", len(j)-len(res))
    st.dataframe(j.sort_values('tanggal_sinyal',ascending=False), use_container_width=True, hide_index=True)

def render_backtest():
    st.markdown("### 📊 Strategy Backtest")
    j = load_journal()
    res = j[j['status'].isin(['TP1','TP2','TP3','SL'])]
    if len(res) < 10:
        st.warning("Data jurnal selesai minimal 10 untuk backtest. Jalankan strategi & update status berkala.")
        return
    cap = 50_000_000; risk = 0.02; eq = [cap]; wins, losses = 0, 0
    for _, r in res.iterrows():
        ra = eq[-1] * risk
        if r['status'] == 'SL': eq.append(eq[-1] - ra); losses += 1
        else:
            mult = {'TP1': 1.5, 'TP2': 3.0, 'TP3': 5.0}[r['status']]
            eq.append(eq[-1] + ra * mult); wins += 1
    eq_s = pd.Series(eq)
    ret = (eq[-1]/cap - 1)*100
    pf = (sum(eq_s.diff().clip(lower=0)) / abs(sum(eq_s.diff().clip(upper=0)))) * 100 if losses>0 else 100
    mdd = ((eq_s / eq_s.cummax() - 1).min()) * 100
    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Total Return", f"{ret:.1f}%")
    with c2: st.metric("Win Rate", f"{wins/(wins+losses)*100:.0f}%")
    with c3: st.metric("Profit Factor", f"{pf:.2f}")
    with c4: st.metric("Max Drawdown", f"{mdd:.1f}%")
    
    if PLOTLY_AVAILABLE:
        fig = go.Figure(go.Scatter(x=eq_s.index, y=eq_s.values, fill='tozeroy', line_color='#58a6ff'))
        fig.update_layout(title='Equity Curve (Risk 2% per trade)', template='plotly_dark', height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
    else:
        eq_df = pd.DataFrame({'Trade': eq_s.index, 'Equity': eq_s.values})
        fig = alt.Chart(eq_df).mark_area(line={'color':'#58a6ff'}, color='#58a6ff').encode(x='Trade', y='Equity')
        st.altair_chart(fig.properties(height=400), use_container_width=True)

def render_bb_banner(t, ev, r):
    v = _check_validity(r["Live Price"], r["Stop Loss"], r["Buy Min"], r["Buy Max"])
    sl = "🟢 Siap entry" if v['status']=='valid' else "🟡 Pantau"
    st.markdown(f'<div class="best-buy-banner"><div style="display:flex;justify-content:space-between;"><div><span class="best-buy-crown">👑 BEST BUY</span><span style="font-size:1.5rem;font-weight:900;color:#ffd700;margin-left:0.5rem;">{t}</span><span style="font-size:0.8rem;color:#e3b341;margin-left:0.6rem;">{sl}</span></div><div style="text-align:right;"><div style="font-size:0.65rem;color:#8b949e;">EXPECTED VALUE</div><div style="font-size:1.4rem;font-weight:900;color:#ffd700;">+{ev}R</div></div></div></div>', unsafe_allow_html=True)
    try:
        with open("alerts.log", "a") as f: f.write(f"{datetime.now()}: BEST BUY {t} EV={ev}R\n")
    except: pass

def render_no_bb():
    st.markdown('<div style="background:rgba(88,166,255,0.1);border:1px solid rgba(88,166,255,0.3);border-radius:8px;padding:0.7rem 1rem;margin-bottom:1.2rem;color:#58a6ff;">ℹ️ Tidak ada saham dengan EV positif & skor > 45 hari ini.</div>', unsafe_allow_html=True)

def render_regime_banner(reg, br):
    if not reg or reg.get('state') in (None,'unknown'): return
    c = {'trending_bull':'#3fb950','trending_bear':'#f85149','choppy':'#e3b341','transisi':'#8b949e'}.get(reg['state'],'#8b949e')
    st.markdown(f'<div style="display:flex;gap:0.8rem;align-items:center;background:rgba(255,255,255,0.03);border:1px solid #21262d;border-radius:8px;padding:0.6rem 1rem;margin-bottom:1rem;"><div><span style="font-size:0.65rem;color:#8b949e;">IHSG</span><br><span style="font-size:0.9rem;font-weight:800;color:{c};">{reg["label"]}</span></div><div style="border-left:1px solid #30363d;height:2.2rem;margin:0 0.2rem;"></div><div><span style="font-size:0.65rem;color:#8b949e;">Breadth</span><br><span style="font-size:0.9rem;font-weight:800;color:#c9d1d9;">{br.get("label","N/A")}</span></div></div>', unsafe_allow_html=True)

def render_sector_warning(df):
    top = df.head(5)
    secs = [SECTOR_MAP.get(t, 'Lainnya') for t in top['Ticker']]
    if secs.count(secs[0]) >= 3:
        st.markdown(f'<div style="background:rgba(248,81,73,0.06);border:1px solid rgba(248,81,73,0.25);border-radius:8px;padding:0.7rem 1rem;margin:1rem 0;color:#f85149;">⚠️ <b>Konsentrasi Sektor:</b> 3 dari 5 saham teratas berasal dari sektor <b>{secs[0]}</b>. Pertimbangkan diversifikasi.</div>', unsafe_allow_html=True)

def _hash_d(d):
    if d is None: return "none"
    if isinstance(d, pd.DataFrame):
        try: return hashlib.md5(f"df:{len(d)}:{d['Close'].iloc[-1]:.2f}".encode()).hexdigest()
        except: return "df_err"
    if isinstance(d, dict):
        if not d: return "e"
        s = []
        for t, df in sorted(d.items()):
            try: s.append(f"{t}:{len(df)}:{df['Close'].iloc[-1]:.2f}")
            except: s.append(f"{t}:err")
        return hashlib.md5("|".join(s).encode()).hexdigest()
    return "unknown"

@st.cache_data(ttl=300, show_spinner=False, max_entries=5)
def _cached_engine(ds, cs, tm, is_, rs_, _ad, _cfg, _ihsg, _reg):
    return quant_strategy_engine(_ad, _cfg, tm, _ihsg, _reg)

st.sidebar.header("⚙️ Parameter")
theme_toggle = st.sidebar.radio("Tema", ["Dark", "Light"], index=0 if st.session_state['theme']=='dark' else 1, horizontal=True)
if (theme_toggle.lower() != st.session_state['theme']):
    st.session_state['theme'] = theme_toggle.lower()
    st.rerun()

cap = st.sidebar.number_input("Modal (Rp)", value=50_000_000, step=5_000_000, min_value=1_000_000)
rl = st.sidebar.slider("Risiko / Trade (%)", 0.5, 5.0, 2.0, 0.5)
al = st.sidebar.slider("Maks Alokasi (%)", 10, 50, 25, 5)
st.sidebar.markdown("---")
min_adtv = st.sidebar.number_input("Min ADTV (Rp)", value=500_000_000, step=100_000_000, min_value=0)
min_px = st.sidebar.number_input("Harga Min", value=100, step=50, min_value=1)
max_px = st.sidebar.number_input("Harga Max", value=25_000, step=500, min_value=1)
min_sc = st.sidebar.slider("Min Score", 50, 85, 60, 5)
cfg = {'total_capital':cap, 'capital_risk_limit_pct':rl, 'max_capital_allocation_pct':al, 'min_adtv':min_adtv, 'min_price':min_px, 'max_price':max_px, 'min_score_threshold':float(min_sc)}

st.markdown("## 🧭 IDX Screener v9.4")
app_mode = st.radio("Mode", ["🔍 Screener", "🔬 Deep Dive", "⚖️ Bandingkan", "📓 Jurnal", "📊 Backtest"], horizontal=True)
st.markdown("---")
tm = st.radio("Gaya Trading", ["Swing Trading", "Intraday (Fast Trade)"], horizontal=True)

j_df = load_journal()
cal_probs = get_calibrated_probs(j_df)

if app_mode == "🔬 Deep Dive": render_deep_dive(cfg, tm, cal_probs); st.stop()
elif app_mode == "⚖️ Bandingkan": render_compare(); st.stop()
elif app_mode == "📓 Jurnal": render_journal(); st.stop()
elif app_mode == "📊 Backtest": render_backtest(); st.stop()

st.markdown("### 📋 Daftar Saham")
lt = load_local_emiten_csv()
so = ["✏️ Manual", "📂 CSV"] + ([f"📋 Tersimpan ({len(lt)})"] if lt else [])
sm = st.radio("Sumber:", so, horizontal=True)
tk = []
if sm == "✏️ Manual": tk = tickers_from_text(st.text_area("Kode:", value="BBRI, BBCA, BMRI", height=100))
elif sm == "📂 CSV":
    up = st.file_uploader("Upload:", type=["csv"])
    if up: tk = parse_tickers_from_df(pd.read_csv(up))
else: tk = lt

if tk: st.markdown(f"✅ **{len(tk)} saham siap.**")
st.markdown("---")

bc1, bc2 = st.columns([1,4])
with bc1: exe = st.button("🚀 Jalankan", type="primary", use_container_width=True)
with bc2:
    if st.button("🗑️ Reset"): st.cache_data.clear(); st.session_state.clear(); st.rerun()

if exe:
    if not tk: st.error("Kosong."); st.stop()
    pd_, iv = (30,"60m") if tm=="Intraday (Fast Trade)" else (400,"1d")
    sz = 15 if tm=="Intraday (Fast Trade)" else 40
    stk = sorted(set(tk)); ck = [stk[i:i+sz] for i in range(0,len(stk),sz)]
    buf = {}; ph, pb = st.empty(), st.progress(0)
    for i, c in enumerate(ck):
        ph.markdown(f"⏳ Batch {i+1}/{len(ck)}…"); pb.progress((i+1)/len(ck))
        buf.update(download_chunk(c, pd_, iv))
    ph.markdown("⏳ IHSG…"); ihsg = download_chunk(["^JKSE"], pd_, iv).get("^JKSE")
    ph.empty(); pb.empty()
    if not buf: st.error("Gagal download."); st.stop()
    st.session_state['raw_market_data'] = buf; st.session_state['ihsg_data'] = ihsg; st.session_state['last_loaded_mode'] = tm
    st.success(f"✅ {len(buf)}/{len(stk)} sukses.")

if st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] == tm:
    ihsg = st.session_state.get('ihsg_data')
    reg = compute_market_regime(ihsg)
    ds, cs, is_, rs_ = _hash_d(st.session_state['raw_market_data']), str(sorted(cfg.items())), _hash_d(ihsg), str(sorted(reg.items()))
    fdf = _cached_engine(ds, cs, tm, is_, rs_, st.session_state['raw_market_data'], cfg, ihsg, reg)
    st.session_state['last_final_df'] = fdf
    if not fdf.empty: append_journal(fdf, tm)
    st.markdown(f"### 📈 Hasil [{tm}]")
    render_regime_banner(reg, st.session_state.get('scan_meta',{}).get('breadth',{}))
    bt, be, _, has = pick_best_buy(fdf)
    if bt: render_bb_banner(bt, be, fdf[fdf["Ticker"]==bt].iloc[0])
    elif not fdf.empty: render_no_bb()
    render_cards(fdf, max_c=6, bt=bt, cal_probs=cal_probs)
    if not fdf.empty: render_sector_warning(fdf)
    if not fdf.empty:
        st.markdown("---")
        st.download_button("📥 Export CSV", fdf.drop(columns=[c for c in fdf.columns if c.startswith('_')]).to_csv(index=False).encode('utf-8'), f"scan_{datetime.now():%Y%m%d}.csv", "text/csv")
        st.dataframe(fdf.drop(columns=[c for c in fdf.columns if c.startswith('_')]), use_container_width=True, hide_index=True)
elif st.session_state['raw_market_data'] and st.session_state['last_loaded_mode'] != tm:
    st.warning("⚠️ Mode berubah. Jalankan ulang.")
else:
    st.info("👋 Isi daftar saham, lalu klik Jalankan.")
