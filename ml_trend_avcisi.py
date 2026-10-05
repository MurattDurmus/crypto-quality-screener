import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Makine Öğrenmesi ile Trend Avı", page_icon="🤖", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }
    .metric-kutu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }
    .metric-baslik { font-size: 0.9rem; color: #8b949e; font-weight: bold; margin-bottom: 5px; }
    .metric-deger { font-size: 1.5rem; font-weight: 800; color: #ffffff; }
    .metric-pozitif { color: #3fb950; }
    .metric-negatif { color: #f85149; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# 1. TEKNİK İNDİKATÖR MOTORU (Makinenin Duyuları)
# -------------------------------------------------------------
def wma(seri, periyot):
    weights = np.arange(1, periyot + 1)
    return seri.rolling(periyot).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True)


def hma(seri, periyot=20):
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    return wma((2 * wma(seri, half_length) - wma(seri, periyot)), sqrt_length)


def rsi_hesapla(seri, periyot=14):
    delta = seri.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# -------------------------------------------------------------
# 2. VERİ VE ÖZELLİK MÜHENDİSLİĞİ (Feature Engineering)
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def ml_verisi_hazirla(sembol, yil_sayisi):
    try:
        df = yf.Ticker(sembol).history(period=f"{yil_sayisi}y")
        if df.empty: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)

        # Makinenin öğreneceği "Özellikler" (Features)
        df['HMA_20'] = hma(df['Close'], 20)
        df['HMA_50'] = hma(df['Close'], 50)
        df['RSI_14'] = rsi_hesapla(df['Close'], 14)

        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # Volatilite ve Fiyat Değişimleri
        df['Volatilite'] = df['Close'].rolling(10).std()
        df['Gunluk_Getiri'] = df['Close'].pct_change()

        # Hedef (Target): 3 Gün Sonra Fiyat Şu Ankinden Yüksek mi Olacak? (1: Evet, 0: Hayır)
        df['Gelecek_3_Gun'] = df['Close'].shift(-3)
        df['Hedef'] = np.where(df['Gelecek_3_Gun'] > df['Close'], 1, 0)

        # Gelecek sütununu düş ve NaN'ları temizle
        df = df.dropna().drop(columns=['Gelecek_3_Gun', 'Dividends', 'Stock Splits'])
        return df
    except:
        return None


# -------------------------------------------------------------
# 3. MAKİNE ÖĞRENMESİ MODELİ (Random Forest)
# -------------------------------------------------------------
def ml_modeli_egit_ve_test_et(df, agac_sayisi, baslangic_kasa):
    # Veriyi ayır: %80 Eğitim (Geçmiş), %20 Test (Gelecek - Hiç Görmediği Veri)
    bolme_indeksi = int(len(df) * 0.8)

    # Modele verilecek özellikler
    ozellikler = ['Open', 'High', 'Low', 'Close', 'Volume', 'HMA_20', 'HMA_50', 'RSI_14', 'MACD', 'MACD_Signal',
                  'Volatilite', 'Gunluk_Getiri']

    X = df[ozellikler]
    y = df['Hedef']

    X_train, X_test = X.iloc[:bolme_indeksi], X.iloc[bolme_indeksi:]
    y_train, y_test = y.iloc[:bolme_indeksi], y.iloc[bolme_indeksi:]

    # Random Forest (Rastgele Orman) Karar Mekanizması Kurulumu
    model = RandomForestClassifier(n_estimators=agac_sayisi, max_depth=10, random_state=42)

    # Modeli Eğit (Geçmiş 4 yılın ilk %80'lik kısmıyla)
    model.fit(X_train, y_train)

    # Hiç görmediği son %20'lik kısımdaki günleri tahmin et
    tahminler = model.predict(X_test)
    isabet_orani = accuracy_score(y_test, tahminler) * 100

    # --- ML BACKTEST SİMÜLASYONU (Sadece Test Verisinde) ---
    test_df = df.iloc[bolme_indeksi:].copy()
    test_df['Tahmin'] = tahminler

    kasa = baslangic_kasa
    pozisyonda_mi = False
    giris_fiyati = 0.0

    kasa_gecmisi = []
    islem_loglari = []

    for i in range(len(test_df)):
        bugun = test_df.iloc[i]
        tarih = test_df.index[i]
        fiyat = bugun['Close']
        sinyal = bugun['Tahmin']  # 1 (Yükselecek) veya 0 (Düşecek/Yatay)

        guncel_deger = kasa if not pozisyonda_mi else (kasa / giris_fiyati) * fiyat
        kasa_gecmisi.append(guncel_deger)

        if not pozisyonda_mi and sinyal == 1:
            pozisyonda_mi = True
            giris_fiyati = fiyat
            islem_loglari.append({'Tarih': tarih, 'Tip': 'AL', 'Fiyat': fiyat})

        elif pozisyonda_mi and sinyal == 0:
            pozisyonda_mi = False
            kasa = (kasa / giris_fiyati) * fiyat
            islem_loglari.append({'Tarih': tarih, 'Tip': 'SAT', 'Fiyat': fiyat})

    # Eğer periyot sonunda hala maldaysa, son günkü fiyattan çıkmış say
    if pozisyonda_mi:
        kasa = (kasa / giris_fiyati) * test_df.iloc[-1]['Close']

    test_df['Kasa_Degeri'] = kasa_gecmisi

    return test_df, pd.DataFrame(islem_loglari), kasa, isabet_orani, model.feature_importances_, ozellikler


# =============================================================
# ARAYÜZ
# =============================================================
st.title("🤖 ML Trend Avcısı (Random Forest)")
st.markdown(
    "Bu laboratuvar; klasik kuralları çöpe atar. Yüzlerce ağaçtan oluşan bir Yapay Zeka ormanı kurar, RSI, MACD ve HMA verilerine bakarak **önümüzdeki 3 günün yönünü tahmin eder**. Sistemi kandırmamak için model sadece geçmiş veriyle eğitilir ve **hiç görmediği güncel piyasada (Test Verisi)** ticarete sokulur.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Yapay Zeka Ayarları")
    sembol = st.text_input("Varlık (Örn: BTC-USD)", value="BTC-USD")
    yil = st.slider("Geçmiş Veri Derinliği (Yıl)", 2, 8, 5)
    agac_sayisi = st.slider("Karar Ağacı Sayısı (Estimators)", 50, 300, 100,
                            help="Sayı arttıkça yapay zeka daha detaylı düşünür ama işlem süresi uzar.")
    kasa = st.number_input("Başlangıç Kasası ($)", value=10000, step=1000)
    st.markdown("---")
    baslat = st.button("🧠 Modeli Eğit ve Canlı Test Et", use_container_width=True)

with col2:
    if baslat:
        with st.spinner(f"Veriler çekiliyor, makine öğrenmesi modeli {agac_sayisi} karar ağacıyla eğitiliyor..."):
            df = ml_verisi_hazirla(sembol, yil)

            if df is None or len(df) < 500:
                st.error("Yeterli eğitim verisi bulunamadı. Lütfen yıl sayısını artırın.")
            else:
                test_df, islemler, son_kasa, isabet, agirliklar, ozellikler = ml_modeli_egit_ve_test_et(df, agac_sayisi,
                                                                                                        kasa)

                getiri = ((son_kasa - kasa) / kasa) * 100
                buy_hold_kasa = (kasa / test_df.iloc[0]['Close']) * test_df.iloc[-1]['Close']
                bh_getiri = ((buy_hold_kasa - kasa) / kasa) * 100

                st.subheader("📊 Yapay Zeka Test Sonuçları (Sadece Son %20'lik Veri)")
                m1, m2, m3, m4 = st.columns(4)

                renk = "metric-pozitif" if getiri >= 0 else "metric-negatif"
                m1.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>YZ Net Getirisi</div><div class='metric-deger {renk}'>% {getiri:.1f}</div></div>",
                    unsafe_allow_html=True)
                m2.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Al & Tut Getirisi</div><div class='metric-deger'>% {bh_getiri:.1f}</div></div>",
                    unsafe_allow_html=True)
                m3.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Karar İsabet Oranı</div><div class='metric-deger'>% {isabet:.1f}</div></div>",
                    unsafe_allow_html=True)
                m4.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Test Edilen Gün</div><div class='metric-deger'>{len(test_df)}</div></div>",
                    unsafe_allow_html=True)

                # --- GRAFİKLER ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

                fig.add_trace(
                    go.Scatter(x=test_df.index, y=test_df['Close'], name='Fiyat', line=dict(color='#8b949e', width=1)),
                    row=1, col=1)

                if not islemler.empty:
                    alimlar = islemler[islemler['Tip'] == 'AL']
                    satimlar = islemler[islemler['Tip'] == 'SAT']
                    fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='YZ - AL',
                                             marker=dict(color='#00c087', size=8, symbol='triangle-up')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=satimlar['Tarih'], y=satimlar['Fiyat'], mode='markers', name='YZ - SAT',
                                             marker=dict(color='#ff4b4b', size=8, symbol='triangle-down')), row=1,
                                  col=1)

                fig.add_trace(
                    go.Scatter(x=test_df.index, y=test_df['Kasa_Degeri'], fill='tozeroy', name='YZ Kasası ($)',
                               line=dict(color='#58a6ff', width=2), fillcolor='rgba(88, 166, 255, 0.1)'), row=2, col=1)

                fig.update_layout(height=600, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0),
                                  hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                # --- YZ NEYE GÖRE KARAR VERDİ? ---
                st.markdown("### 🧠 Yapay Zeka Karar Verirken Neye Baktı?")
                st.caption(
                    "Modelin al/sat kararı verirken hangi indikatörleri daha çok önemsediğinin (Feature Importance) ağırlık tablosu:")

                agirlik_df = pd.DataFrame({'İndikatör': ozellikler, 'Önem Oranı (%)': agirliklar * 100})
                agirlik_df = agirlik_df.sort_values(by='Önem Oranı (%)', ascending=False).reset_index(drop=True)

                # Progress bar tarzı şık bir gösterim
                for idx, row in agirlik_df.iterrows():
                    st.write(f"**{row['İndikatör']}**")
                    st.progress(int(row['Önem Oranı (%)']))