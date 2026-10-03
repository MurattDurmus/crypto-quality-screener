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
    page_title="Küresel & BIST Kalite / Dip Dönüş Radarı",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        background-color: #eab30822;
        color: #facc15;
        border: 1px solid #eab30888;
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
    .badge-vol {
        background-color: #ff6b4a22;
        color: #ff7b5a;
        border: 1px solid #ff6b4a66;
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
        transition: color 0.15s ease;
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
# ANLIK TÜRKÇEYE ÇEVİRİ FONKSİYONU
# -------------------------------------------------------------
def turkceye_cevir(metin):
    """Gelen İngilizce başlık/özeti doğrudan akıcı Türkçeye çevirir."""
    if not metin or len(metin.strip()) == 0:
        return metin
    try:
        # Metin zaten Türkçe karakterler içeriyorsa çevirmeden dön
        if any(c in metin for c in "çğıöşüÇĞİÖŞÜ"):
            return metin

        encoded = urllib.parse.quote(metin)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=tr&dt=t&q={encoded}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            sonuc = res.json()
            cevrilmis = "".join([parca[0] for parca in sonuc[0] if parca[0]])
            return cevrilmis
    except Exception:
        pass
    return metin


# -------------------------------------------------------------
# CANLI GÜNCELLENEN ENDEKS LİSTELERİ
# -------------------------------------------------------------
def sp500_canli_liste():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception:
        url2 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        return pd.read_html(url2)[0]['Symbol'].str.replace('.', '-', regex=False).tolist()


def bist30_canli_liste():
    return [
        "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", "EKGYO.IS", "ENKAI.IS",
        "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS",
        "KONTR.IS", "KOZAL.IS", "KRDMD.IS", "MGROS.IS", "OYAKC.IS", "PETKM.IS", "PGSUS.IS",
        "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TOASO.IS", "TUPRS.IS",
        "ULKER.IS", "YKBNK.IS"
    ]


def bist50_canli_liste():
    liste30 = bist30_canli_liste()
    ek_50 = [
        "ALARK.IS", "ANSGR.IS", "BRSAN.IS", "CIMSA.IS", "DOAS.IS", "DOHOL.IS", "EGEEN.IS",
        "ENJSA.IS", "GENIL.IS", "GESAN.IS", "ISGYO.IS", "KAYSE.IS", "KCAER.IS", "KORDS.IS",
        "MAVI.IS", "ODAS.IS", "OTKAR.IS", "SOKM.IS", "TABGD.IS", "TTKOM.IS"
    ]
    return list(dict.fromkeys(liste30 + ek_50))


def bist100_canli_liste():
    try:
        url = "https://tr.wikipedia.org/wiki/BIST_100"
        tablolar = pd.read_html(url)
        for t in tablolar:
            for col in t.columns:
                if any(x in str(col).lower() for x in ["kod", "sembol", "ticker"]):
                    semboller = [f"{str(x).strip().upper()}.IS" for x in t[col] if str(x).strip().isalpha()]
                    if len(semboller) >= 70:
                        return list(dict.fromkeys(semboller))
    except Exception:
        pass

    liste50 = bist50_canli_liste()
    ek_100 = [
        "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKFGY.IS", "AKFYE.IS", "AKSA.IS", "AKSEN.IS",
        "ALFAS.IS", "ASGYO.IS", "BERA.IS", "BOBET.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS",
        "CCOLA.IS", "CWENE.IS", "ECILC.IS", "ECZYT.IS", "EUPWR.IS", "GOLTS.IS", "GWIND.IS",
        "HALKB.IS", "IPEKE.IS", "ISDMR.IS", "ISFIN.IS", "ISMEN.IS", "KLSER.IS", "KMPUR.IS",
        "KONKA.IS", "KOZAA.IS", "MIATK.IS", "QUAGR.IS", "REEDR.IS", "SDTTR.IS", "SMRTG.IS",
        "TATEN.IS", "TKFEN.IS", "TMSN.IS", "TSKB.IS", "TURSG.IS", "VAKBN.IS", "VESBE.IS",
        "VESTL.IS", "YEOTK.IS", "YYLGD.IS", "ZOREN.IS", "PENTA.IS", "KONYA.IS", "BAGFS.IS"
    ]
    return list(dict.fromkeys(liste50 + ek_100))


def msci_turkey_canli_liste():
    return [
        "THYAO.IS", "BIMAS.IS", "AKBNK.IS", "KCHOL.IS", "TUPRS.IS", "GARAN.IS",
        "ISCTR.IS", "ASELS.IS", "YKBNK.IS", "SAHOL.IS", "FROTO.IS", "SISE.IS",
        "EREGL.IS", "TCELL.IS", "PGSUS.IS"
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
# TEMEL VERİLER
# -------------------------------------------------------------
def hisse_temel_bilgileri(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info

        ocf = info.get("operatingCashflow", 0)
        if ocf is None or ocf <= 0:
            cf = t.cashflow
            if cf is not None and not cf.empty:
                for row in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                    if row in cf.index:
                        ocf = cf.loc[row].iloc[0]
                        break

        fcf = info.get("freeCashflow", 0)
        mcap = info.get("marketCap", 1)
        fcf_yield = (fcf / mcap * 100) if (fcf and mcap) else 0.0

        roe = info.get("returnOnEquity", 0)
        roe_yuzde = (roe * 100) if roe else 0.0

        sirket_adi = info.get("shortName") or info.get("longName") or ticker.replace(".IS", "")
        sektor = info.get("sector", "Genel")

        return {
            "sirket_adi": sirket_adi,
            "sektor": sektor,
            "ocf": ocf if ocf else 0,
            "fcf_yield": max(0.0, fcf_yield),
            "roe": max(0.0, roe_yuzde)
        }
    except Exception:
        return {
            "sirket_adi": ticker.replace(".IS", ""), "sektor": "Genel",
            "ocf": 0, "fcf_yield": 0.0, "roe": 0.0
        }


# -------------------------------------------------------------
# TÜRKÇE HAP ÖZET HABER MOTORU
# -------------------------------------------------------------
def turkce_ozet_hazirla(title, summary):
    raw = (summary if summary and len(summary) > 30 else title).strip()
    raw = re.sub('<[^<]+?>', '', raw)

    cumleler = re.split(r'(?<=[.!?])\s+', raw)
    secilen = f"{cumleler[0]} {cumleler[1]}" if len(cumleler) >= 2 else cumleler[0]

    if len(secilen) > 175:
        secilen = secilen[:172].rstrip() + "..."

    return turkceye_cevir(secilen)


@st.cache_data(ttl=7200)
def canli_haber_ozetleri(ticker, sirket_adi):
    haberler = []
    try:
        t = yf.Ticker(ticker)
        yf_news = t.news
        if yf_news:
            for item in yf_news[:10]:
                title = item.get("title", "")
                link = item.get("link", "#")
                pub = item.get("publisher", "Kaynak")
                summary = item.get("summary", "")
                if title:
                    haberler.append({"title": title, "summary": summary, "link": link, "source": pub})
    except Exception:
        pass

    if len(haberler) < 4:
        try:
            arama = ticker.replace(".IS", "") if ".IS" in ticker else f"{ticker} stock"
            rss = f"https://news.google.com/rss/search?q={arama}&hl=tr&gl=TR&ceid=TR:tr" if ".IS" in ticker else f"https://news.google.com/rss/search?q={arama}&hl=en-US&gl=US&ceid=US:en"
            resp = requests.get(rss, timeout=4)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:6]:
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else "#"
                    source_elem = item.find("source")
                    source = source_elem.text if source_elem is not None else "Haber Portalı"
                    if title and not any(h['title'] == title for h in haberler):
                        haberler.append({"title": title, "summary": title, "link": link, "source": source})
        except Exception:
            pass

    pos_words = ["growth", "record", "profit", "surge", "beats", "buy", "deal", "contract", "invest", "expansion",
                 "dividend", "yükseliş", "rekor", "kâr", "anlaşma", "büyüme", "ihale", "yatırım", "temettü", "onay",
                 "ortaklık"]
    neg_words = ["slump", "fall", "decline", "drop", "probe", "lawsuit", "debt", "loss", "risk", "downgrade", "fine",
                 "cut", "inflation", "düşüş", "zarar", "soruşturma", "baskı", "borç", "ceza", "dava", "kayıp", "uyarı",
                 "iptal"]

    olumlu = []
    olumsuz = []

    for h in haberler:
        metin = (h["title"] + " " + h.get("summary", "")).lower()
        if any(w in metin for w in pos_words) and len(olumlu) < 2:
            tr_cumle = turkce_ozet_hazirla(h["title"], h.get("summary", ""))
            olumlu.append({"ozet": tr_cumle, "link": h["link"], "source": h["source"]})
        elif any(w in metin for w in neg_words) and len(olumsuz) < 2:
            tr_cumle = turkce_ozet_hazirla(h["title"], h.get("summary", ""))
            olumsuz.append({"ozet": tr_cumle, "link": h["link"], "source": h["source"]})

    if not olumlu:
        olumlu.append({
            "ozet": f"{sirket_adi}, güçlü operasyonel nakit üretimi ve stratejik pazar büyümesiyle faaliyet tabanını koruyor.",
            "link": f"https://www.google.com/search?q={ticker}+yatırım+büyüme",
            "source": "Sektörel Değerlendirme"
        })
    if not olumsuz:
        olumsuz.append({
            "ozet": f"Sektörel girdi maliyetleri ve küresel talep dalgalanmaları operasyonel kâr marjları üzerinde kısa vadeli baskı yaratabilir.",
            "link": f"https://www.google.com/search?q={ticker}+risk+maliyet",
            "source": "Piyasa Notu"
        })

    return olumlu, olumsuz


# =============================================================
# SIDEBAR
# =============================================================
st.sidebar.title("⚙️ Tarayıcı Ayarları")

secilen_endeks = st.sidebar.selectbox(
    "🏛️ Taranacak Piyasa",
    options=["S&P 500 (ABD)", "BIST 30", "BIST 50", "BIST 100", "Türkiye MSCI"]
)

tarama_penceresi = st.sidebar.radio(
    "Hull Yeşil Dönüş Zamanı",
    options=["Sadece Bu Ay Yeşile Dönenler (En Taze)", "Son 1-2 Ay İçinde Yeşile Dönenler"],
    index=1
)

hacim_filtresi = st.sidebar.checkbox(
    "🔥 Sadece Hacim Patlaması Olanları Göster",
    value=False,
    help="İşaretlenirse sadece bu ayki hacmi son 3 ay ortalamasından en az %20 yüksek olan hisseler listelenir."
)

if secilen_endeks == "S&P 500 (ABD)":
    tarama_adeti = st.sidebar.select_slider(
        "Taranacak Şirket Sayısı",
        options=[50, 100, 250, "Tüm Liste"],
        value=100
    )
else:
    tarama_adeti = "Tüm Liste"
    st.sidebar.caption(f"ℹ️ {secilen_endeks} bileşenlerinin tamamı taranacaktır.")

st.sidebar.markdown("---")
st.sidebar.markdown("**🏆 Skorlama Modeli:**")
st.sidebar.caption("• %35 FCF Verimi")
st.sidebar.caption("• %25 ROE Kârlılık")
st.sidebar.caption("• %25 Zirveden İskonto")
st.sidebar.caption("• %15 Hacim Patlaması")

baslat_butonu = st.sidebar.button("🚀 Listeyi Güncelle ve Tara", use_container_width=True)

# =============================================================
# ANA EKRAN
# =============================================================
para_birimi = "$" if secilen_endeks == "S&P 500 (ABD)" else "₺"
st.title(f"🏆 {secilen_endeks} Kalite ve Dip Dönüş Radarı")

if not baslat_butonu:
    st.info(f"Sol menüden piyasa ve kriterleri belirleyip **'Listeyi Güncelle ve Tara'** butonuna tıklayın.")
else:
    with st.spinner("Güncel hisse listesi çekiliyor..."):
        if secilen_endeks == "S&P 500 (ABD)":
            tam_liste = sp500_canli_liste()
        elif secilen_endeks == "BIST 30":
            tam_liste = bist30_canli_liste()
        elif secilen_endeks == "BIST 50":
            tam_liste = bist50_canli_liste()
        elif secilen_endeks == "BIST 100":
            tam_liste = bist100_canli_liste()
        else:
            tam_liste = msci_turkey_canli_liste()

    hedef_hisseler = tam_liste if tarama_adeti == "Tüm Liste" else tam_liste[:int(tarama_adeti)]
    st.write(f"🔄 **{secilen_endeks}** kapsamında **{len(hedef_hisseler)}** şirket taranıyor...")

    sembol_str = " ".join(hedef_hisseler)
    veri = yf.download(
        sembol_str,
        period="5y",
        interval="1mo",
        group_by="ticker",
        auto_adjust=True,
        threads=True
    )

    aday_listesi = []
    bar = st.progress(0, text="Teknik dönüşler ve hacimler inceleniyor...")
    toplam = len(hedef_hisseler)

    for idx, sym in enumerate(hedef_hisseler):
        bar.progress(int(((idx + 1) / toplam) * 100), text=f"Taranıyor: {idx + 1}/{toplam} ({sym})")
        try:
            if len(hedef_hisseler) == 1:
                df = veri.copy()
            else:
                if sym not in veri.columns.levels[0]:
                    continue
                df = veri[sym].dropna(how="all")

            if len(df) < 25:
                continue

            df = df.dropna(subset=['Close'])
            df['HMA'] = hma_hesapla(df['Close'], periyot=20)
            df['WAE_Up'], df['WAE_Line'] = wae_hesapla(df)
            df['HMA_Diff'] = df['HMA'].diff()

            son = df.iloc[-1]
            onceki = df.iloc[-2]
            iki_once = df.iloc[-3]

            bu_ay_yesil = (son['HMA_Diff'] > 0) and (onceki['HMA_Diff'] <= 0)
            gecen_ay_yesil = (son['HMA_Diff'] > 0) and (onceki['HMA_Diff'] > 0) and (iki_once['HMA_Diff'] <= 0)

            uygun_teknik = False
            durum_etiketi = ""

            if tarama_penceresi == "Sadece Bu Ay Yeşile Dönenler (En Taze)":
                if bu_ay_yesil:
                    uygun_teknik = True
                    durum_etiketi = "🟢 Bu Ay"
            else:
                if bu_ay_yesil:
                    uygun_teknik = True
                    durum_etiketi = "🟢 Bu Ay"
                elif gecen_ay_yesil:
                    uygun_teknik = True
                    durum_etiketi = "⚡ Geçen Ay"

            if uygun_teknik and (son['Close'] >= son['HMA'] * 0.96):
                son_hacim = son.get('Volume', 0)
                ort_3ay_hacim = df['Volume'].iloc[-4:-1].mean() if len(df) >= 4 else son_hacim
                hacim_orani = (son_hacim / ort_3ay_hacim) if (ort_3ay_hacim and ort_3ay_hacim > 0) else 1.0

                if hacim_filtresi and hacim_orani < 1.2:
                    continue

                temel = hisse_temel_bilgileri(sym)

                if temel["ocf"] > 0:
                    zirve_5y = df['Close'].max()
                    iskonto = ((zirve_5y - son['Close']) / zirve_5y) * 100.0

                    temiz_ticker = sym.replace(".IS", "")
                    aday_listesi.append({
                        "Kod": temiz_ticker,
                        "Şirket": temel["sirket_adi"][:18],
                        "Sektör": temel["sektor"][:14],
                        "Fiyat": round(son['Close'], 2),
                        "Dönüş": durum_etiketi,
                        "Hacim Patlaması": round(hacim_orani, 2),
                        "FCF %": round(temel["fcf_yield"], 1),
                        "ROE %": round(temel["roe"], 1),
                        "İskonto %": round(max(0.0, iskonto), 1),
                        "df": df,
                        "tam_sym": sym
                    })
        except Exception:
            continue

    bar.empty()

    if not aday_listesi:
        st.warning(f"{secilen_endeks} içinde filtrelere uyan hisse bulunamadı.")
    else:
        df_puan = pd.DataFrame(aday_listesi)


        def normalize(col):
            if col.max() == col.min():
                return pd.Series(50, index=col.index)
            return (col - col.min()) / (col.max() - col.min()) * 100


        norm_fcf = normalize(df_puan["FCF %"])
        norm_roe = normalize(df_puan["ROE %"])
        norm_iskonto = normalize(df_puan["İskonto %"])
        norm_vol = normalize(df_puan["Hacim Patlaması"])

        df_puan["Skor"] = (norm_fcf * 0.35) + (norm_roe * 0.25) + (norm_iskonto * 0.25) + (norm_vol * 0.15)
        df_puan["Skor"] = df_puan["Skor"].round(1)
        df_puan = df_puan.sort_values(by="Skor", ascending=False).reset_index(drop=True)

        st.success(f"🎯 Kriterlere uyan **{len(df_puan)}** hisse bulundu!")

        tablo_gosterim = df_puan.drop(columns=["df", "tam_sym"]).copy()
        tablo_gosterim.index = tablo_gosterim.index + 1

        st.dataframe(
            tablo_gosterim,
            use_container_width=True,
            column_config={
                "Kod": st.column_config.TextColumn("Kod", width=70, help="Hisse kodu."),
                "Şirket": st.column_config.TextColumn("Şirket", width=135, help="Şirket unvanı."),
                "Sektör": st.column_config.TextColumn("Sektör", width=105, help="Sektör."),
                "Fiyat": st.column_config.NumberColumn(f"Fiyat ({para_birimi})", width=80, format=f"{para_birimi}%.2f",
                                                       help="Son kapanış fiyatı."),
                "Dönüş": st.column_config.TextColumn("Dönüş", width=90, help="Hull yeşil dönüş zamanı."),
                "Hacim Patlaması": st.column_config.NumberColumn("Hacim Katı", width=85, format="%.2fx",
                                                                 help="Son ay / 3 aylık ortalama hacim."),
                "FCF %": st.column_config.NumberColumn("FCF %", width=75, format="%.1f%%",
                                                       help="Serbest Nakit Akışı Verimi."),
                "ROE %": st.column_config.NumberColumn("ROE %", width=75, format="%.1f%%", help="Özsermaye Kârlılığı."),
                "İskonto %": st.column_config.NumberColumn("İskonto %", width=80, format="%.1f%%",
                                                           help="Zirveden iskonto payı."),
                "Skor": st.column_config.NumberColumn("Skor", width=70, format="%.1f", help="Kalite Skoru (0-100).")
            }
        )

        st.markdown("---")
        st.subheader("📰 En Yüksek Skorlu İlk 5 Hisse — Türkçe Gelişme & Haber Özetleri")

        for i, row in df_puan.head(5).iterrows():
            sym_clean = row['Kod']
            full_sym = row['tam_sym']
            df_plot = row['df'].tail(36)
            vol_badge = "🔥 Güçlü Hacim" if row['Hacim Patlaması'] >= 1.2 else "Normal Hacim"

            # Türkçe haber özetleri
            olumlu_ozetler, olumsuz_ozetler = canli_haber_ozetleri(full_sym, row['Şirket'])

            with st.container():
                pos_html = ""
                for h in olumlu_ozetler:
                    pos_html += f"• <a href='{h['link']}' target='_blank' class='clickable-summary'>{h['ozet']}</a> <span class='src-tag'>[{h['source']}]</span><br/>"

                neg_html = ""
                for h in olumsuz_ozetler:
                    neg_html += f"• <a href='{h['link']}' target='_blank' class='clickable-summary'>{h['ozet']}</a> <span class='src-tag'>[{h['source']}]</span><br/>"

                st.markdown(f"""
                <div class="card-box">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="badge-rank">#{i + 1} SKOR: {row['Skor']}</span>
                            <span style="font-size: 1.4rem; font-weight: 800; color: #fff; margin-left: 10px;">{sym_clean}</span>
                            <span style="font-size: 1.0rem; color: #94a3b8; margin-left: 8px;">{row['Şirket']} ({row['Sektör']})</span>
                            <span style="font-size: 1.1rem; color: #00c087; margin-left: 12px; font-weight: 700;">{row['Fiyat']} {para_birimi}</span>
                        </div>
                        <div>
                            <span class="badge-vol" style="margin-right: 6px;">{vol_badge} ({row['Hacim Patlaması']}x)</span>
                            <span class="badge-turn">{row['Dönüş']}</span>
                        </div>
                    </div>
                    <div style="margin-top: 8px;">
                        <span class="badge-metric">💵 FCF: %{row['FCF %']}</span>
                        <span class="badge-metric">📈 ROE: %{row['ROE %']}</span>
                        <span class="badge-metric">🎯 İskonto: %{row['İskonto %']}</span>
                    </div>
                    <div class="insight-box">
                        <div class="pos-header">✅ (+) Olumlu Gelişmeler & Fırsatlar (Detay İçin Cümleye Tıklayın):</div>
                        {pos_html}
                        <div class="neg-header">⚠️ (-) Riskler & Maliyet Baskıları (Detay İçin Cümleye Tıklayın):</div>
                        {neg_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_plot.index,
                    open=df_plot['Open'], high=df_plot['High'],
                    low=df_plot['Low'], close=df_plot['Close'],
                    name="Aylık Mum",
                    increasing_line_color='#00c087', decreasing_line_color='#ff4b4b'
                ))
                fig.add_trace(go.Scatter(
                    x=df_plot.index, y=df_plot['HMA'],
                    mode='lines', name='Hull MA (20)',
                    line=dict(color='#00c087', width=2.5)
                ))
                fig.update_layout(
                    height=240,
                    margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_dark",
                    xaxis_rangeslider_visible=False,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")