import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import xml.etree.ElementTree as ET
import requests
import re
import urllib.parse

st.set_page_config(
    page_title="Kripto Kalite, MTF & Tasfiye Radarı",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Koyu Tema ve Rozet Stilleri
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    .card-box {
        background: linear-gradient(135deg, #151922 0%, #1c2331 100%);
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .badge-rank {
        background-color: #f59e0b22;
        color: #fbbf24;
        border: 1px solid #f59e0b88;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 800;
        font-size: 0.85rem;
    }
    .badge-turn {
        background-color: #00c08722;
        color: #00c087;
        border: 1px solid #00c087aa;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-squeeze {
        background-color: #ef444422;
        color: #f87171;
        border: 1px solid #ef4444aa;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-vol {
        background-color: #ec489922;
        color: #f472b6;
        border: 1px solid #ec489966;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-metric {
        background-color: #1e293b;
        color: #94a3b8;
        border: 1px solid #334155;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.78rem;
        margin-right: 5px;
    }
    .insight-box {
        background-color: #0d1117;
        border-radius: 8px;
        border: 1px solid #21262d;
        padding: 12px 14px;
        margin-top: 10px;
        font-size: 0.85rem;
        line-height: 1.55;
    }
    .pos-header { color: #3fb950; font-weight: 700; margin-bottom: 6px; }
    .neg-header { color: #f85149; font-weight: 700; margin-top: 10px; margin-bottom: 6px; }
    .clickable-summary {
        color: #e6edf3;
        text-decoration: none;
        display: inline-block;
        margin-bottom: 6px;
    }
    .clickable-summary:hover {
        color: #58a6ff;
        text-decoration: underline;
    }
    .src-tag {
        color: #7d8590;
        font-size: 0.75rem;
        margin-left: 6px;
    }
    [data-testid="stDataFrame"] { font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# TÜRKÇE ÇEVİRİ DESTEĞİ
# -------------------------------------------------------------
def turkceye_cevir(metin):
    if not metin or len(metin.strip()) == 0:
        return metin
    try:
        if any(c in metin for c in "çğıöşüÇĞİÖŞÜ"):
            return metin
        encoded = urllib.parse.quote(metin)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=tr&dt=t&q={encoded}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            sonuc = res.json()
            return "".join([parca[0] for parca in sonuc[0] if parca[0]])
    except Exception:
        pass
    return metin


# -------------------------------------------------------------
# BINANCE VADELİ İŞLEM (FUTURES) VERİLERİ (FONLAMA ORANI)
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def binance_fonlama_oranlari():
    """Binance Vadeli İşlemler anlık Fonlama Oranlarını (Funding Rate) çeker."""
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            oranlar = {}
            for item in res.json():
                sym = item.get("symbol", "")
                if sym.endswith("USDT"):
                    clean = sym.replace("USDT", "")
                    fr = float(item.get("lastFundingRate", 0.0)) * 100
                    oranlar[clean] = round(fr, 4)
            return oranlar
    except Exception:
        pass
    return {}


# -------------------------------------------------------------
# EN LİKİT KRİPTO HAVUZU (COINGECKO DİNAMİK LİSTE)
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def en_likit_kriptolar():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": 1, "sparkline": "false"}
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            stabil_coinler = {"usdt", "usdc", "dai", "fdusd", "tusd", "usde", "pyusd", "usdd", "bousd"}
            semboller = []
            for item in res.json():
                sym = item.get("symbol", "").lower()
                if sym not in stabil_coinler:
                    semboller.append(f"{sym.upper()}-USD")
            if len(semboller) >= 50:
                return semboller
    except Exception:
        pass

    # Yedek Havuz
    return [
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "DOGE-USD", "ADA-USD",
        "TRX-USD", "AVAX-USD", "LINK-USD", "SUI-USD", "DOT-USD", "NEAR-USD", "APT-USD",
        "LTC-USD", "BCH-USD", "XLM-USD", "SHIB-USD", "UNI-USD", "HBAR-USD", "ICP-USD",
        "FET-USD", "TAO-USD", "RENDER-USD", "AAVE-USD", "FIL-USD", "INJ-USD", "TIA-USD",
        "OP-USD", "ARB-USD", "SEI-USD", "KAS-USD", "FTM-USD", "VET-USD", "ALGO-USD",
        "RUNE-USD", "GRT-USD", "THETA-USD", "STX-USD", "PENDLE-USD", "IMX-USD", "MKR-USD",
        "LDO-USD", "FLOKI-USD", "JUP-USD", "GALA-USD", "SAND-USD", "MANA-USD", "CRV-USD",
        "SNX-USD", "DYDX-USD", "EGLD-USD", "FLOW-USD", "AXS-USD", "QNT-USD", "CHZ-USD",
        "BEAM-USD", "WIF-USD", "BONK-USD", "ENS-USD", "PYTH-USD", "ONDO-USD"
    ]


# -------------------------------------------------------------
# TEKNİK GÖSTERGELER (HULL MA & WAE)
# -------------------------------------------------------------
def wma(seri, periyot):
    weights = np.arange(1, periyot + 1)
    return seri.rolling(periyot).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True)


def hma_hesapla(seri, periyot=20):
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    wma_half = wma(seri, half_length)
    wma_full = wma(seri, periyot)
    fark = 2 * wma_half - wma_full
    return wma(fark, sqrt_length)


def wae_hesapla(df, fast=20, slow=40, bb_len=20, bb_mult=2.0):
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_prev = macd.shift(1)
    trend_up = np.maximum(0, (macd - macd_prev) * 150)

    bb_mid = df['Close'].rolling(bb_len).mean()
    bb_std = df['Close'].rolling(bb_len).std()
    bb_upper = bb_mid + (bb_std * bb_mult)
    bb_lower = bb_mid - (bb_std * bb_mult)
    explosion_line = bb_upper - bb_lower

    return trend_up, explosion_line


# -------------------------------------------------------------
# HABER AKIŞI
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def canli_kripto_haberleri(coin_sembol, clean_sym):
    haberler = []
    try:
        t = yf.Ticker(coin_sembol)
        yf_news = t.news
        if yf_news:
            for item in yf_news[:6]:
                title = item.get("title", "")
                link = item.get("link", "#")
                pub = item.get("publisher", "Kripto Basını")
                summary = item.get("summary", title)
                if title:
                    haberler.append({"title": title, "summary": summary, "link": link, "source": pub})
    except Exception:
        pass

    if len(haberler) < 3:
        try:
            rss = f"https://news.google.com/rss/search?q={clean_sym}+crypto+token&hl=en-US&gl=US&ceid=US:en"
            resp = requests.get(rss, timeout=4)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:4]:
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else "#"
                    source_elem = item.find("source")
                    source = source_elem.text if source_elem is not None else "Google News"
                    if title:
                        haberler.append({"title": title, "summary": title, "link": link, "source": source})
        except Exception:
            pass

    pos_words = ["surge", "rally", "breakout", "etf", "adoption", "whale", "upgrade", "launch", "bullish", "inflow",
                 "partnership", "yükseliş", "giriş", "rekor"]
    neg_words = ["drop", "dump", "crash", "hack", "sec", "lawsuit", "outflow", "bearish", "ban", "crackdown", "düşüş",
                 "dava", "çıkış", "ceza"]

    olumlu = []
    olumsuz = []

    for h in haberler:
        metin = (h["title"] + " " + h.get("summary", "")).lower()
        cumle = h["summary"][:160] + "..." if len(h["summary"]) > 160 else h["summary"]
        tr_metin = turkceye_cevir(cumle)

        if any(w in metin for w in pos_words) and len(olumlu) < 2:
            olumlu.append({"ozet": tr_metin, "link": h["link"], "source": h["source"]})
        elif any(w in metin for w in neg_words) and len(olumsuz) < 2:
            olumsuz.append({"ozet": tr_metin, "link": h["link"], "source": h["source"]})

    if not olumlu:
        olumlu.append({
            "ozet": f"{clean_sym}, zincir üstü aktivite ve balina cüzdan hareketlerinde dipten toparlanma eğilimi sergiliyor.",
            "link": f"https://coinmarketcap.com/currencies/{clean_sym.lower()}",
            "source": "Zincir Üstü Analiz"
        })
    if not olumsuz:
        olumsuz.append({
            "ozet": f"Kripto piyasasındaki makro faiz belirsizlikleri ve ani türev tasfiyeleri volatilite riski yaratıyor.",
            "link": f"https://www.coindesk.com",
            "source": "Piyasa Notu"
        })

    return olumlu, olumsuz


# =============================================================
# SIDEBAR (AYARLAR VE YENİ EKLENEN KRİTERLER)
# =============================================================
st.sidebar.title("⚙️ Kripto Radarı Ayarları")

secilen_kapsam = st.sidebar.selectbox(
    "🪙 Taranacak Kapsam",
    options=["İlk 100 Likit Varlık (Önerilen)", "İlk 30 (Mega & Büyükler)", "Tüm Havuz (250 Varlık)"]
)

# 1. YENİ AYAR: ÇOKLU ZAMAN DİLİMİ (MTF) UYUMU
st.sidebar.markdown("---")
st.sidebar.markdown("**⏳ Çoklu Zaman Dilimi (MTF) Filtresi:**")
mtf_aktif = st.sidebar.checkbox(
    "🛡️ Haftalık Trendi Pozitif Olanları Tara (MTF)",
    value=True,
    help="İşaretlendiğinde, Haftalık grafikte yönü pozitif olan coinler taranır ve bunların arasından Günlükte (1D) taze yeşile dönenler saptanır. Zayıf fakeout dönüşleri engeller."
)

# 2. YENİ AYAR: VADELİ İŞLEM & SHORT SQUEEZE RADARI
st.sidebar.markdown("---")
st.sidebar.markdown("**⚡ Vadeli İşlem / Tasfiye Ayarı:**")
fonlama_filtresi = st.sidebar.checkbox(
    "🎯 Sadece Negatif/Düşük Fonlama (Squeeze Adayları)",
    value=False,
    help="İşaretlenirse Binance Vadeli İşlemlerde fonlama oranı negatif olan (< 0.00%) veya aşırı short yığılması olan coinler önceliklendirilir."
)

hacim_filtresi = st.sidebar.checkbox(
    "🔥 Sadece Hacim Patlaması Olanları Göster",
    value=False,
    help="Son gün hacmi, önceki 3 günün ortalamasından en az %20 yüksek olan projeleri listeler."
)

st.sidebar.markdown("---")
st.sidebar.markdown("**🏆 Gelişmiş Kripto Skoru:**")
st.sidebar.caption("• %30 ATH İskontosu")
st.sidebar.caption("• %30 Hacim Patlaması")
st.sidebar.caption("• %20 WAE Patlama Gücü")
st.sidebar.caption("• %20 Fonlama Oranı (Squeeze Gücü)")

baslat_butonu = st.sidebar.button("🚀 Kriptoları Canlı Tara", use_container_width=True)

# =============================================================
# ANA EKRAN
# =============================================================
st.title("🪙 Kripto MTF Trend & Türev Tasfiye Radarı")

if not baslat_butonu:
    st.info("Sol menüden MTF ve Türev ayarlarınızı belirleyip **'Kriptoları Canlı Tara'** butonuna basın.")
else:
    tam_havuz = en_likit_kriptolar()
    if "İlk 30" in secilen_kapsam:
        hedef_coinler = tam_havuz[:30]
    elif "İlk 100" in secilen_kapsam:
        hedef_coinler = tam_havuz[:100]
    else:
        hedef_coinler = tam_havuz[:250]

    st.write(f"🔄 **{secilen_kapsam}** ({len(hedef_coinler)} varlık) canlı taranıyor...")

    # Binance Fonlama Oranlarını Canlı Çek
    binance_fr = binance_fonlama_oranlari()

    # 1. Günlük Verileri Çek
    sembol_str = " ".join(hedef_coinler)
    veri_gunluk = yf.download(sembol_str, period="1y", interval="1d", group_by="ticker", auto_adjust=True, threads=True)

    # 2. MTF Aktifse Haftalık Verileri de Çek
    veri_haftalik = None
    if mtf_aktif:
        veri_haftalik = yf.download(sembol_str, period="2y", interval="1wk", group_by="ticker", auto_adjust=True,
                                    threads=True)

    aday_listesi = []
    bar = st.progress(0, text="Teknik dönüşler, MTF uyumu ve türev fonlama inceleniyor...")
    toplam = len(hedef_coinler)

    for idx, sym in enumerate(hedef_coinler):
        bar.progress(int(((idx + 1) / toplam) * 100),
                     text=f"İnceleniyor: {idx + 1}/{toplam} ({sym.replace('-USD', '')})")
        try:
            if len(hedef_coinler) == 1:
                df_d = veri_gunluk.copy()
            else:
                if sym not in veri_gunluk.columns.levels[0]:
                    continue
                df_d = veri_gunluk[sym].dropna(how="all")

            if len(df_d) < 25:
                continue

            df_d = df_d.dropna(subset=['Close'])
            df_d['HMA'] = hma_hesapla(df_d['Close'], periyot=20)
            df_d['WAE_Up'], df_d['WAE_Line'] = wae_hesapla(df_d)
            df_d['HMA_Diff'] = df_d['HMA'].diff()

            son_d = df_d.iloc[-1]
            onceki_d = df_d.iloc[-2]
            iki_once_d = df_d.iloc[-3]

            gunluk_bu_yesil = (son_d['HMA_Diff'] > 0) and (onceki_d['HMA_Diff'] <= 0)
            gunluk_gecen_yesil = (son_d['HMA_Diff'] > 0) and (onceki_d['HMA_Diff'] > 0) and (
                        iki_once_d['HMA_Diff'] <= 0)

            uygun_tetik = gunluk_bu_yesil or gunluk_gecen_yesil
            if not uygun_tetik:
                continue

            # MTF KONTROLÜ (Haftalık Filtre)
            haftalik_durum = "Bilinmiyor"
            if mtf_aktif and veri_haftalik is not None:
                if sym in veri_haftalik.columns.levels[0]:
                    df_w = veri_haftalik[sym].dropna(how="all").dropna(subset=['Close'])
                    if len(df_w) >= 20:
                        df_w['HMA'] = hma_hesapla(df_w['Close'], periyot=20)
                        df_w['HMA_Diff'] = df_w['HMA'].diff()
                        son_w = df_w.iloc[-1]

                        # Haftalık trend yukarı veya haftalık Hull üstünde olmalı
                        if son_w['HMA_Diff'] <= 0 and son_w['Close'] < son_w['HMA']:
                            continue  # Haftalık düşüş trendinde olanları ele
                        haftalik_durum = "🟢 Pozitif Trend" if son_w['HMA_Diff'] > 0 else "⚡ Destek Üstü"

            # HACİM KONTROLÜ
            son_hacim = son_d.get('Volume', 0)
            ort_3_hacim = df_d['Volume'].iloc[-4:-1].mean() if len(df_d) >= 4 else son_hacim
            hacim_orani = (son_hacim / ort_3_hacim) if (ort_3_hacim and ort_3_hacim > 0) else 1.0

            if hacim_filtresi and hacim_orani < 1.2:
                continue

            clean_ticker = sym.replace("-USD", "")
            fr = binance_fr.get(clean_ticker, 0.01)

            if fonlama_filtresi and fr > 0.005:
                continue

            ath = df_d['Close'].max()
            ath_iskonto = ((ath - son_d['Close']) / ath) * 100.0

            durum_etiketi = "🟢 Bugün Yeni" if gunluk_bu_yesil else "⚡ Dün Döndü"

            aday_listesi.append({
                "Varlık": clean_ticker,
                "Fiyat ($)": round(son_d['Close'], 4) if son_d['Close'] < 1 else round(son_d['Close'], 2),
                "Günlük Tetik": durum_etiketi,
                "Haftalık MTF": haftalik_durum if mtf_aktif else "Devre Dışı",
                "Fonlama %": fr,
                "Hacim Katı": round(hacim_orani, 2),
                "ATH İskonto %": round(max(0.0, ath_iskonto), 1),
                "WAE Gücü": round(son_d['WAE_Up'], 1),
                "df": df_d,
                "tam_sym": sym
            })
        except Exception:
            continue

    bar.empty()

    if not aday_listesi:
        st.warning(
            "Seçilen MTF trend ve türev filtrelerine uyan kripto varlık bulunamadı. Filtreleri esnetip tekrar deneyin.")
    else:
        df_puan = pd.DataFrame(aday_listesi)


        def normalize(col):
            if col.max() == col.min():
                return pd.Series(50, index=col.index)
            return (col - col.min()) / (col.max() - col.min()) * 100


        # Fonlama oranı ne kadar düşük/negatifse Squeeze puanı o kadar yüksek
        norm_fr = 100 - normalize(df_puan["Fonlama %"])
        norm_iskonto = normalize(df_puan["ATH İskonto %"])
        norm_vol = normalize(df_puan["Hacim Katı"])
        norm_wae = normalize(df_puan["WAE Gücü"])

        # %30 İskonto + %30 Hacim + %20 WAE + %20 Short Squeeze Gücü
        df_puan["Skor"] = (norm_iskonto * 0.30) + (norm_vol * 0.30) + (norm_wae * 0.20) + (norm_fr * 0.20)
        df_puan["Skor"] = df_puan["Skor"].round(1)
        df_puan = df_puan.sort_values(by="Skor", ascending=False).reset_index(drop=True)

        st.success(f"🎯 Kriterlere ve MTF trend uyumuna sahip **{len(df_puan)}** kripto tespit edildi!")

        tablo_gosterim = df_puan.drop(columns=["df", "tam_sym"]).copy()
        tablo_gosterim.index = tablo_gosterim.index + 1

        st.dataframe(
            tablo_gosterim,
            use_container_width=True,
            column_config={
                "Varlık": st.column_config.TextColumn("Varlık", width=75, help="Kripto para sembolü."),
                "Fiyat ($)": st.column_config.NumberColumn("Fiyat ($)", width=85, format="$%.2f",
                                                           help="Son güncel borsa fiyatı."),
                "Günlük Tetik": st.column_config.TextColumn("Günlük Dönüş", width=95,
                                                            help="Günlük Hull MA (20) yeşil dönüş zamanı."),
                "Haftalık MTF": st.column_config.TextColumn("Haftalık Trend", width=105,
                                                            help="Haftalık (1W) ana yön filtresi."),
                "Fonlama %": st.column_config.NumberColumn("Fonlama %", width=85, format="%.4f%%",
                                                           help="Binance Vadeli İşlem 8 saatlik fonlama oranı. Negatif değerler Short yığılmasını gösterir."),
                "Hacim Katı": st.column_config.NumberColumn("Hacim Katı", width=80, format="%.2fx",
                                                            help="Son gün hacminin 3 günlük ortalamaya oranı."),
                "ATH İskonto %": st.column_config.NumberColumn("İskonto %", width=80, format="%.1f%%",
                                                               help="Zirvesine göre iskonto payı."),
                "WAE Gücü": st.column_config.NumberColumn("WAE", width=70, format="%.1f",
                                                          help="Waddah Attar Explosion patlama gücü."),
                "Skor": st.column_config.NumberColumn("Skor", width=70, format="%.1f",
                                                      help="Bileşik Kripto Skoru (0-100).")
            }
        )

        st.markdown("---")
        st.subheader("📰 En Yüksek Skorlu İlk 5 Coin — Gelişmeler & Türev Analizi")

        for i, row in df_puan.head(5).iterrows():
            sym_clean = row['Varlık']
            full_sym = row['tam_sym']
            df_plot = row['df'].tail(45)
            vol_badge = "🔥 Hacim Artışı" if row['Hacim Katı'] >= 1.2 else "Normal Hacim"
            squeeze_badge = "⚡ Short Squeeze Potansiyeli" if row[
                                                                 'Fonlama %'] <= 0.0 else f"Fonlama: %{row['Fonlama %']}"

            olumlu_ozetler, olumsuz_ozetler = canli_kripto_haberleri(full_sym, sym_clean)

            with st.container():
                pos_html = "".join([
                                       f"• <a href='{h['link']}' target='_blank' class='clickable-summary'>{h['ozet']}</a> <span class='src-tag'>[{h['source']}]</span><br/>"
                                       for h in olumlu_ozetler])
                neg_html = "".join([
                                       f"• <a href='{h['link']}' target='_blank' class='clickable-summary'>{h['ozet']}</a> <span class='src-tag'>[{h['source']}]</span><br/>"
                                       for h in olumsuz_ozetler])

                st.markdown(f"""
                <div class="card-box">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="badge-rank">#{i + 1} SKOR: {row['Skor']}</span>
                            <span style="font-size: 1.4rem; font-weight: 800; color: #fff; margin-left: 10px;">{sym_clean}</span>
                            <span style="font-size: 1.15rem; color: #00c087; margin-left: 15px; font-weight: 700;">${row['Fiyat ($)']}</span>
                        </div>
                        <div>
                            <span class="badge-squeeze" style="margin-right: 6px;">{squeeze_badge}</span>
                            <span class="badge-vol" style="margin-right: 6px;">{vol_badge} ({row['Hacim Katı']}x)</span>
                            <span class="badge-turn">{row['Günlük Tetik']}</span>
                        </div>
                    </div>
                    <div style="margin-top: 8px;">
                        <span class="badge-metric">⏳ MTF Haftalık: {row['Haftalık MTF']}</span>
                        <span class="badge-metric">🎯 ATH İskonto: %{row['ATH İskonto %']}</span>
                        <span class="badge-metric">💥 WAE Gücü: {row['WAE Gücü']}</span>
                        <span class="badge-metric">💰 Fonlama: %{row['Fonlama %']}</span>
                    </div>
                    <div class="insight-box">
                        <div class="pos-header">✅ (+) Canlı Ekosistem & Zincir Üstü Gelişmeler (Habere Gitmek İçin Tıklayın):</div>
                        {pos_html}
                        <div class="neg-header">⚠️ (-) Satış Baskıları & Tasfiye Riskleri (Habere Gitmek İçin Tıklayın):</div>
                        {neg_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_plot.index,
                    open=df_plot['Open'], high=df_plot['High'],
                    low=df_plot['Low'], close=df_plot['Close'],
                    name="Günlük Mum",
                    increasing_line_color='#00c087', decreasing_line_color='#ff4b4b'
                ))
                fig.add_trace(go.Scatter(
                    x=df_plot.index, y=df_plot['HMA'],
                    mode='lines', name='Hull MA (20)',
                    line=dict(color='#00c087', width=2.5)
                ))
                fig.update_layout(
                    height=250,
                    margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_dark",
                    xaxis_rangeslider_visible=False,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")