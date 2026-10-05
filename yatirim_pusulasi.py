import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Küçük Birikim Pusulası", page_icon="🧭", layout="wide")

# Modern CSS Stilleri
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }

    .kutu-yesil { background: linear-gradient(135deg, #052e16 0%, #064e3b 100%); border-left: 5px solid #10b981; padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}
    .kutu-kirmizi { background: linear-gradient(135deg, #450a0a 0%, #7f1d1d 100%); border-left: 5px solid #ef4444; padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}
    .kutu-sari { background: linear-gradient(135deg, #422006 0%, #78350f 100%); border-left: 5px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}

    .macro-card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; text-align: center; }
    .macro-title { font-size: 0.85rem; color: #8b949e; font-weight: 600; margin-bottom: 5px;}
    .macro-val { font-size: 1.3rem; font-weight: 700; color: #c9d1d9; }
    .macro-pos { color: #3fb950; font-weight: 600; font-size: 0.9rem;}
    .macro-neg { color: #f85149; font-weight: 600; font-size: 0.9rem;}

    .news-card { background-color: #161b22; border-left: 4px solid #38bdf8; padding: 15px; margin-bottom: 15px; border-radius: 6px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
    .news-title { font-size: 1.05rem; font-weight: bold; margin-bottom: 10px; line-height: 1.4; }
    .news-title a { color: #f0f6fc; text-decoration: none; transition: color 0.2s; }
    .news-title a:hover { color: #58a6ff; }

    .impact-box { background-color: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 12px; font-size: 0.9rem; }
    .impact-header { color: #8b949e; font-size: 0.8rem; font-weight: bold; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px; }
    .impact-item { margin-bottom: 4px; display: flex; align-items: center; }
    .impact-pos { color: #3fb950; font-weight: bold; width: 100px; }
    .impact-neg { color: #f85149; font-weight: bold; width: 100px; }
    .impact-neu { color: #8b949e; font-weight: bold; width: 100px; }
    .impact-desc { color: #c9d1d9; margin-left: 10px; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# TEKNİK FONKSİYONLAR
# -------------------------------------------------------------
def rsi_hesapla(seri, periyot=14):
    delta = seri.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


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


# -------------------------------------------------------------
# MAKRO EKONOMİK GÖSTERGELER
# -------------------------------------------------------------
@st.cache_data(ttl=600)
def makro_verileri_getir():
    gostergeler = {
        "DXY (Küresel Dolar)": "DX-Y.NYB",
        "ABD 10 Yıllık Faiz": "^TNX",
        "VIX (Korku Endeksi)": "^VIX",
        "Brent Petrol": "BZ=F",
        "Ons Altın": "GC=F",
        "Dolar/TL": "TRY=X"
    }

    semboller = list(gostergeler.values())
    veri = yf.download(semboller, period="5d", interval="1d", progress=False)['Close']

    if isinstance(veri, pd.Series):
        veri = veri.to_frame()

    sonuclar = {}
    for isim, sembol in gostergeler.items():
        try:
            sutun = veri[sembol].dropna()
            if len(sutun) >= 2:
                son = sutun.iloc[-1]
                onceki = sutun.iloc[-2]
                degisim = ((son - onceki) / onceki) * 100
                sonuclar[isim] = {"fiyat": son, "degisim": degisim}
        except:
            sonuclar[isim] = {"fiyat": 0.0, "degisim": 0.0}

    return sonuclar


# -------------------------------------------------------------
# KRİPTO FIRSAT RADARI (Screener Entegrasyonu)
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def kripto_firsatlari_bul():
    # Güvenilir, organik, teknolojik tabanlı kilit projeler
    hedef_kriptolar = ["ETH-USD", "SOL-USD", "STRK-USD", "MINA-USD", "RENDER-USD", "LINK-USD", "AAVE-USD", "INJ-USD",
                       "FET-USD"]
    firsatlar = []

    try:
        veri = yf.download(hedef_kriptolar, period="1y", interval="1d", progress=False)['Close']
        if isinstance(veri, pd.Series): veri = veri.to_frame()

        for sym in hedef_kriptolar:
            try:
                df = pd.DataFrame({'Close': veri[sym]}).dropna()
                if len(df) < 30: continue

                df['HMA'] = hma_hesapla(df['Close'], 20)
                df['HMA_Diff'] = df['HMA'].diff()

                son = df.iloc[-1]
                onceki = df.iloc[-2]

                # Zirveden iskonto hesabı
                ath = df['Close'].max()
                iskonto = ((ath - son['Close']) / ath) * 100

                # Sadece Hull MA günlük trendi yeşil olanları listeye al
                if son['HMA_Diff'] > 0:
                    durum = "📈 Pozitif Trend"
                    gerekce = f"Zirvesinden %{iskonto:.0f} iskontolu. Günlük yükseliş eğilimini koruyor."
                    skor = iskonto

                    # Eğer bugün veya dün taze yeşile döndüyse önceliklendir (Screener Tetiği)
                    if onceki['HMA_Diff'] <= 0:
                        durum = "⚡ Taze Dip Dönüşü"
                        gerekce = f"Zirvesinden %{iskonto:.0f} iskontolu. Hull MA grafiği tam bugün yeşile döndü!"
                        skor = iskonto + 50  # Taze dönüşe devasa puan avantajı

                    firsatlar.append({
                        "coin": sym.replace("-USD", ""),
                        "fiyat": son['Close'],
                        "durum": durum,
                        "gerekce": gerekce,
                        "skor": skor
                    })
            except:
                continue
    except:
        pass

    # En yüksek skora sahip (Taze dönüşlü ve ucuzlamış) ilk 3 projeyi gönder
    firsatlar = sorted(firsatlar, key=lambda x: x['skor'], reverse=True)
    return firsatlar[:3]


# -------------------------------------------------------------
# TREND PUSULASI (ABD BORSALARI EKLENDİ)
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def trendleri_analiz_et():
    varliklar = {
        "ABD Borsaları (S&P 500)": "^GSPC",
        "Borsa İstanbul (BIST 100)": "XU100.IS",
        "Gram Altın (ONS Bazlı Trend)": "GC=F",
        "Kripto Para (Bitcoin)": "BTC-USD"
    }

    sonuclar = {}
    for isim, sembol in varliklar.items():
        try:
            df = yf.download(sembol, period="1y", interval="1d", progress=False, auto_adjust=True)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)

            df = df.dropna(subset=['Close'])
            df['SMA_50'] = df['Close'].rolling(50).mean()
            df['SMA_200'] = df['Close'].rolling(200).mean()
            df['RSI'] = rsi_hesapla(df['Close'])

            son = df.iloc[-1]
            fiyat = son['Close']
            sma50 = son['SMA_50']
            sma200 = son['SMA_200']
            rsi = son['RSI']

            if fiyat > sma200 and sma50 > sma200:
                durum, renk, tavsiye = "GÜÇLÜ YÜKSELİŞ TRENDİ", "yesil", "Rüzgar arkanızda. Yatırımda kalınabilir, kurumsal para içeride."
            elif fiyat > sma200 and sma50 <= sma200:
                durum, renk, tavsiye = "DİPTEN TOPARLANMA", "sari", "Ana trende (200G) tutundu. Yeni bir yükseliş denemesi yapıyor."
            elif fiyat < sma200 and fiyat > sma50:
                durum, renk, tavsiye = "TEPKİ YÜKSELİŞİ (RİSKLİ)", "sari", "Kısa vadeli tepki var ama büyük resim hala tehlikeli. Güvenli değil."
            else:
                durum, renk, tavsiye = "DÜŞÜŞ TRENDİ (AYI PİYASASI)", "kirmizi", "Düşen bıçak tutulmaz. Nakitte veya başka varlıklarda beklemek mantıklıdır."

            rsi_uyari = ""
            if rsi > 70:
                rsi_uyari = "⚠️ DİKKAT: Fiyat kısa sürede çok şişmiş. Tepeden almamak için düzeltme beklenebilir."
            elif rsi < 30:
                rsi_uyari = "💡 FIRSAT: Aşırı satım var. Dip tepkisi gelebilir."

            sonuclar[isim] = {"fiyat": fiyat, "durum": durum, "renk": renk, "tavsiye": tavsiye, "rsi_uyari": rsi_uyari}
        except:
            continue
    return sonuclar


# -------------------------------------------------------------
# HABER ETKİ MOTORU
# -------------------------------------------------------------
def haberin_etkisini_hesapla(metin):
    metin = metin.lower()
    etkiler = []

    if any(x in metin for x in ["faiz indirim", "faizi indir", "faizleri düş", "teşvik", "parasal genişleme"]):
        etkiler.append(
            ('<span class="impact-pos">▲ KRİPTO & ALTIN</span>', 'Faiz düşüşü parayı riskli varlıklara yönlendirir.'))
        etkiler.append(
            ('<span class="impact-neg">▼ KÜRESEL DOLAR</span>', 'Doların getirisi azalacağından değer kaybeder.'))
    elif any(x in metin for x in ["faiz art", "faizi art", "faizleri yüksel", "sıkılaş", "faiz sabit"]):
        etkiler.append(('<span class="impact-neg">▼ BORSA & KRİPTO</span>', 'Para risksiz getiriye (faize) kaçar.'))
        etkiler.append(('<span class="impact-pos">▲ KÜRESEL DOLAR</span>', 'Dolar değer kazanır.'))
    elif any(x in metin for x in ["savaş", "gerilim", "füze", "çatışma", "yaptırım", "saldırı", "vurdu", "patlama"]):
        etkiler.append(('<span class="impact-pos">▲ ALTIN & PETROL</span>',
                        'Savaş riskinde güvenli limana kaçış başlar, petrol arzı tehdit altındadır.'))
        etkiler.append(
            ('<span class="impact-neg">▼ BORSA</span>', 'Piyasalar belirsizliği sevmez, panik satışı gelir.'))
    elif any(x in metin for x in ["enflasyon açıklandı", "tüfe açıklandı", "enflasyon arttı", "beklentiyi aştı"]):
        etkiler.append(('<span class="impact-neg">▼ BİST / BORSA</span>',
                        'Yüksek enflasyon faiz indirimlerini geciktirir, borsa baskılanır.'))
        etkiler.append(
            ('<span class="impact-pos">▲ ALTIN</span>', 'Uzun vadede paranın erimesine karşı kalkan görevi görür.'))
    elif any(x in metin for x in
             ["tcmb", "merkez bankası karar", "mehmet şimşek", "tüik açıklandı", "vergi", "kısıtlama"]):
        etkiler.append(('<span class="impact-neu">🔘 BIST 100</span>',
                        'Yerel ekonomi kararları. Beklentinin üzerinde/altında olmasına göre sert yön çizer.'))

    if not etkiler:
        etkiler.append(('<span class="impact-neu">🔘 GENEL PİYASA</span>',
                        'Bu gelişmenin doğrudan yön değiştirici devasa bir etkisi beklenmiyor.'))

    html_cikti = ""
    for etki in etkiler:
        html_cikti += f'<div class="impact-item">{etki[0]}<div class="impact-desc">{etki[1]}</div></div>'
    return html_cikti


@st.cache_data(ttl=1800)
def ekonomi_haberlerini_cek():
    haberler = []
    query = "(açıklandı OR kararı OR indirdi OR artırdı OR vurdu OR sıçradı OR düştü OR rekor) (faiz OR enflasyon OR piyasa OR borsa OR fed OR tcmb OR dolar OR altın)"
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=tr&gl=TR&ceid=TR:tr"

    cop_kelimeler = [
        "ne zaman", "saat kaçta", "ne kadar", "canlı", "son durum", "uzman", "beklentisi",
        "açıklanacak", "bekleniyor", "tahmini", "işte", "mi", "mu", "ne oldu", "bugün",
        "portakal", "kelebek", "festival", "film", "sinema", "ödül", "gala", "konser",
        "dizi", "oyuncu", "şarkı", "magazin", "spor", "futbol", "kupa", "galatasaray",
        "fenerbahçe", "beşiktaş", "trabzonspor"
    ]

    try:
        res = requests.get(url, timeout=5)
        root = ET.fromstring(res.content)
        for item in root.findall(".//item"):
            baslik = item.find("title").text
            link = item.find("link").text
            if any(cop in baslik.lower() for cop in cop_kelimeler):
                continue

            etki_notu = haberin_etkisini_hesapla(baslik)
            haberler.append({"baslik": baslik, "link": link, "etki": etki_notu})
            if len(haberler) >= 5: break
    except:
        pass
    return haberler


# =============================================================
# ARAYÜZ OLUŞTURMA
# =============================================================
st.title("🧭 Yatırım Pusulası & Makro Ekonomi Paneli")
st.markdown(
    "Piyasaya yön veren büyük güçleri, varlıklarınızın ana trendini ve gerçekleşen son dakika haberlerinin cebinize olan net etkisini okuyun.")
st.markdown("---")

st.subheader("📊 Küresel Ekonomi Göstergeleri (Mahşerin Atlıları)")
makro_veri = makro_verileri_getir()

if makro_veri:
    cols = st.columns(6)
    for col, (isim, veri) in zip(cols, makro_veri.items()):
        degisim_sinifi = "macro-pos" if veri['degisim'] >= 0 else "macro-neg"
        ok = "▲" if veri['degisim'] >= 0 else "▼"
        fiyat_format = f"{veri['fiyat']:.2f}"
        if isim == "Dolar/TL":
            fiyat_format = f"₺{veri['fiyat']:.2f}"
        elif isim == "Ons Altın":
            fiyat_format = f"${veri['fiyat']:.1f}"

        col.markdown(f"""
        <div class="macro-card">
            <div class="macro-title">{isim}</div>
            <div class="macro-val">{fiyat_format}</div>
            <div class="{degisim_sinifi}">{ok} %{abs(veri['degisim']):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

col_sol, col_sag = st.columns([1.1, 1])

with col_sol:
    st.subheader("🚦 Varlık Trend Pusulası (200 Günlük İzleme)")
    trendler = trendleri_analiz_et()

    if trendler:
        for isim, veri in trendler.items():
            kutu_sinifi = f"kutu-{veri['renk']}"
            ikon = "🟢" if veri['renk'] == 'yesil' else ("🟡" if veri['renk'] == 'sari' else "🔴")
            renk_kodu = "#10b981" if veri['renk'] == 'yesil' else ("#f59e0b" if veri['renk'] == 'sari' else "#ef4444")

            html_kart = f"""
            <div class="{kutu_sinifi}">
                <div style="font-size: 1.1rem; font-weight: bold; color: #ffffff;">{isim}</div>
                <div style="margin-top: 6px; font-weight: bold; color: {renk_kodu}; font-size: 1.05rem;">{ikon} {veri['durum']}</div>
                <div style="font-size: 0.9rem; line-height: 1.4; color: #9ca3af; margin-top: 5px;">{veri['tavsiye']}</div>
            """
            if veri['rsi_uyari']:
                html_kart += f'<div style="font-size: 0.85rem; font-weight: bold; margin-top: 8px; color: #60a5fa;">{veri["rsi_uyari"]}</div>'

            # Kripto piyasası yeşilse Screener Asistanını devreye sok
            if "Kripto" in isim and veri['renk'] == 'yesil':
                kripto_tavsiyeleri = kripto_firsatlari_bul()
                if kripto_tavsiyeleri:
                    html_kart += f"""
                    <div style="margin-top: 15px; padding: 12px; background-color: rgba(0,0,0,0.4); border-radius: 6px; border-left: 3px solid #38bdf8;">
                        <div style="font-size: 0.85rem; font-weight: bold; color: #38bdf8; margin-bottom: 8px; text-transform: uppercase;">
                            🤖 Radar Destekli Altcoin Fırsatları
                        </div>
                    """
                    for k in kripto_tavsiyeleri:
                        html_kart += f"""
                        <div style="margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 6px;">
                            <span style="color: #e6edf3; font-weight: bold; font-size: 1.05rem;">{k['coin']}</span> 
                            <span style="color: #10b981; font-size: 0.9rem; margin-left: 5px;">(${k['fiyat']:.2f})</span>
                            <span style="font-size: 0.8rem; color: #fbbf24; margin-left: 8px; background: rgba(245, 158, 11, 0.1); padding: 2px 6px; border-radius: 4px;">{k['durum']}</span><br>
                            <span style="font-size: 0.85rem; color: #8b949e;">{k['gerekce']}</span>
                        </div>
                        """
                    html_kart += "</div>"

            html_kart += "</div>"
            st.markdown(html_kart, unsafe_allow_html=True)

with col_sag:
    st.subheader("📰 Gerçekleşen Gelişmeler ve Kesin Etkisi")
    st.caption("Sadece 'açıklandı, onaylandı, karar verildi' gibi kesin sonuç bildiren olaylar listelenir.")
    haberler = ekonomi_haberlerini_cek()

    if haberler:
        for h in haberler:
            st.markdown(f"""
            <div class="news-card">
                <div class="news-title">
                    <a href="{h['link']}" target="_blank">{h['baslik']}</a>
                </div>
                <div class="impact-box">
                    <div class="impact-header">⚡ PİYASA ETKİ ANALİZİ</div>
                    {h['etki']}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Şu an için filtreyi geçen kesinleşmiş güncel makro olay bulunmuyor.")