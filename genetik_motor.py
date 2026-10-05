import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import random
import plotly.graph_objects as go
import time

st.set_page_config(page_title="Genetik Optimizasyon Motoru", page_icon="🧬", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }
    .gen-kutu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; border-bottom: 3px solid #58a6ff;}
    .gen-baslik { font-size: 0.9rem; color: #8b949e; font-weight: bold; margin-bottom: 5px; text-transform: uppercase;}
    .gen-deger { font-size: 1.8rem; font-weight: 800; color: #ffffff; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# 1. HIZLANDIRILMIŞ TEKNİK GÖSTERGELER (Numpy ile)
# -------------------------------------------------------------
def wma(seri, periyot):
    weights = np.arange(1, periyot + 1)
    return seri.rolling(periyot).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True)


def hma_hesapla(seri, periyot):
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    wma_half = wma(seri, half_length)
    wma_full = wma(seri, periyot)
    return wma((2 * wma_half - wma_full), sqrt_length)


# -------------------------------------------------------------
# 2. VERİ HAZIRLIĞI (HMA Periyodu Dinamik Değişeceği İçin Ayrıldı)
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def ham_veriyi_getir(sembol, yil_sayisi):
    try:
        ticker = yf.Ticker(sembol)
        df = ticker.history(period=f"{yil_sayisi}y")
        if df.empty: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        return df[['Open', 'High', 'Low', 'Close']].dropna()
    except:
        return None


def veriye_genleri_uygula(df_ham, hma_periyot):
    df = df_ham.copy()
    # Farklı zaman dilimleri için HMA hesapla
    df_w = df.resample('W').last()
    df_m = df.resample('ME').last()

    df['HMA'] = hma_hesapla(df['Close'], hma_periyot)
    df_w['HMA_W'] = hma_hesapla(df_w['Close'], hma_periyot)
    df_m['HMA_M'] = hma_hesapla(df_m['Close'], hma_periyot)

    df['Trend_D'] = df['HMA'].diff()
    df_w['Trend_W_Shift'] = df_w['HMA_W'].diff().shift(1)
    df_m['Trend_M_Shift'] = df_m['HMA_M'].diff().shift(1)

    df = df.join(df_w[['Trend_W_Shift']], how='left').ffill()
    df = df.join(df_m[['Trend_M_Shift']], how='left').ffill()
    return df.dropna()


# -------------------------------------------------------------
# 3. HIZLI BACKTEST MOTORU (Sadece Sonuç Döndürür)
# -------------------------------------------------------------
def hizli_backtest(df, stop_loss, take_profit):
    # Veri setini hızlı iterasyon için Numpy dizilerine çeviriyoruz
    kapanislar = df['Close'].values
    dusukler = df['Low'].values
    yuksekler = df['High'].values
    trend_d = df['Trend_D'].values
    trend_w = df['Trend_W_Shift'].values
    trend_m = df['Trend_M_Shift'].values

    pozisyonda_mi = False
    giris_fiyati = 0.0
    kasa = 10000.0

    for i in range(1, len(df)):
        if not pozisyonda_mi:
            # Alım Şartı
            if trend_m[i] > 0 and trend_w[i] > 0 and trend_d[i] > 0 and trend_d[i - 1] <= 0:
                pozisyonda_mi = True
                giris_fiyati = kapanislar[i]
                stop_fiyati = giris_fiyati * (1 - stop_loss / 100)
                hedef_fiyat = giris_fiyati * (1 + take_profit / 100)
        else:
            # Satım Şartları
            if dusukler[i] <= stop_fiyati:
                kasa *= (1 + ((stop_fiyati - giris_fiyati) / giris_fiyati))
                pozisyonda_mi = False
            elif yuksekler[i] >= hedef_fiyat:
                kasa *= (1 + ((hedef_fiyat - giris_fiyati) / giris_fiyati))
                pozisyonda_mi = False
            elif trend_w[i] <= 0:
                kasa *= (1 + ((kapanislar[i] - giris_fiyati) / giris_fiyati))
                pozisyonda_mi = False

    return ((kasa - 10000.0) / 10000.0) * 100  # Net Getiri %


# -------------------------------------------------------------
# 4. GENETİK ALGORİTMA MOTORU
# -------------------------------------------------------------
def genetik_optimizasyon(df_ham, jenerasyon_sayisi, populasyon_sayisi, ilerleme_cubugu, metin_kutusu):
    # Gen Sınırları: [SL (2-20), TP (10-100), HMA_Periyot (10-50)]
    populasyon = []
    for _ in range(populasyon_sayisi):
        birey = {
            'sl': random.randint(3, 15),
            'tp': random.randint(15, 80),
            'hma': random.randint(12, 40)
        }
        populasyon.append(birey)

    en_iyi_bireyler = []
    evrim_gecmisi = []  # Grafik için

    for jenerasyon in range(jenerasyon_sayisi):
        metin_kutusu.text(f"🧬 Jenerasyon {jenerasyon + 1}/{jenerasyon_sayisi} evrimleşiyor...")

        # 1. Uygunluk (Fitness) Testi (Tüm popülasyonu savaştır)
        fitness_skorlari = []
        for birey in populasyon:
            df_islenmis = veriye_genleri_uygula(df_ham, birey['hma'])
            skor = hizli_backtest(df_islenmis, birey['sl'], birey['tp'])
            fitness_skorlari.append((skor, birey))

        # Skorlara göre büyükten küçüğe sırala (En güçlüler hayatta kalır)
        fitness_skorlari.sort(key=lambda x: x[0], reverse=True)

        en_iyi_skor = fitness_skorlari[0][0]
        en_iyi_genler = fitness_skorlari[0][1]
        evrim_gecmisi.append(en_iyi_skor)

        # 2. Doğal Seçilim (En kötü %50'yi öldür, en iyi %50 kalsın)
        hayatta_kalanlar = [x[1] for x in fitness_skorlari[:int(populasyon_sayisi / 2)]]

        # 3. Çaprazlama (Crossover) ve Mutasyon
        yeni_nesil = []
        # Elitizmi koru (En iyi 2 bireyi aynen yeni nesle aktar)
        yeni_nesil.extend(hayatta_kalanlar[:2])

        while len(yeni_nesil) < populasyon_sayisi:
            anne = random.choice(hayatta_kalanlar)
            baba = random.choice(hayatta_kalanlar)

            # Genleri karıştır
            cocuk = {
                'sl': anne['sl'] if random.random() > 0.5 else baba['sl'],
                'tp': anne['tp'] if random.random() > 0.5 else baba['tp'],
                'hma': anne['hma'] if random.random() > 0.5 else baba['hma']
            }

            # Radyasyon (Mutasyon) -> Çocuğun %20 ihtimalle rastgele bir geni değişir (Yeni keşifler için)
            if random.random() < 0.20:
                mutasyon_geni = random.choice(['sl', 'tp', 'hma'])
                if mutasyon_geni == 'sl':
                    cocuk['sl'] = random.randint(3, 15)
                elif mutasyon_geni == 'tp':
                    cocuk['tp'] = random.randint(15, 80)
                elif mutasyon_geni == 'hma':
                    cocuk['hma'] = random.randint(12, 40)

            yeni_nesil.append(cocuk)

        populasyon = yeni_nesil
        ilerleme_cubugu.progress((jenerasyon + 1) / jenerasyon_sayisi)

    metin_kutusu.text("✅ Evrim Tamamlandı! Kutsal Kâse Bulundu.")
    return en_iyi_skor, en_iyi_genler, evrim_gecmisi


# =============================================================
# ARAYÜZ OLUŞTURMA
# =============================================================
st.title("🧬 Genetik Optimizasyon Motoru")
st.markdown(
    "Yapay zeka; belirlediğiniz varlık üzerinde yüzlerce farklı sanal robot (gen) yaratır, onları geçmiş yıllarda savaştırır ve **'En Yüksek Kârı'** getiren Stop-Loss, Take-Profit ve HMA ayarlarını evrim yoluyla keşfeder.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🧪 Deney Tüpü Ayarları")
    sembol = st.text_input("Evrimleşecek Varlık (Örn: BTC-USD, THYAO.IS)", value="BTC-USD")
    yil_sayisi = st.slider("Geçmiş Veri (Yıl)", 1, 5, 4)
    st.markdown("---")
    populasyon_sayisi = st.slider("Popülasyon Büyüklüğü", 10, 50, 20,
                                  help="Her jenerasyonda kaç farklı robot (ihtimal) savaşsın?")
    jenerasyon_sayisi = st.slider("Jenerasyon (Nesil) Sayısı", 5, 30, 10,
                                  help="Evrim kaç tur devam etsin? Sayı arttıkça daha mükemmel sonuç bulunur ama süre uzar.")

    st.info(f"💡 Algoritma toplamda **{populasyon_sayisi * jenerasyon_sayisi} farklı backtest** çalıştıracak.")
    baslat_btn = st.button("🚀 Evrimi Başlat", use_container_width=True)

with col2:
    st.subheader("🔬 Evrim Sonuçları")
    ilerleme_cubugu = st.progress(0)
    metin_kutusu = st.empty()

    if baslat_btn:
        df_ham = ham_veriyi_getir(sembol, yil_sayisi)
        if df_ham is None:
            st.error("Veri çekilemedi. Varlık sembolünü kontrol edin.")
        else:
            baslangic_zamani = time.time()
            en_iyi_kâr, en_iyi_genler, evrim_gecmisi = genetik_optimizasyon(df_ham, jenerasyon_sayisi,
                                                                            populasyon_sayisi, ilerleme_cubugu,
                                                                            metin_kutusu)
            bitis_zamani = time.time()

            st.success(
                f"Evrim {bitis_zamani - baslangic_zamani:.1f} saniyede tamamlandı. İşte {sembol} için Kutsal Kâse Ayarları:")

            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(
                f"<div class='gen-kutu'><div class='gen-baslik'>🛑 İdeal Stop-Loss</div><div class='gen-deger'>%{en_iyi_genler['sl']}</div></div>",
                unsafe_allow_html=True)
            m2.markdown(
                f"<div class='gen-kutu'><div class='gen-baslik'>🎯 İdeal Kâr Al</div><div class='gen-deger'>%{en_iyi_genler['tp']}</div></div>",
                unsafe_allow_html=True)
            m3.markdown(
                f"<div class='gen-kutu'><div class='gen-baslik'>📈 İdeal HMA Periyot</div><div class='gen-deger'>{en_iyi_genler['hma']}</div></div>",
                unsafe_allow_html=True)
            m4.markdown(
                f"<div class='gen-kutu'><div class='gen-baslik'>💰 Maksimum Kâr</div><div class='gen-deger' style='color:#3fb950;'>%{en_iyi_kâr:.1f}</div></div>",
                unsafe_allow_html=True)

            st.markdown("### 📈 Nesiller Boyu Evrim Gelişimi")
            st.caption(
                "Aşağıdaki grafik, algoritmanın her yeni nesilde kârlılığı nasıl artırdığını (öğrendiğini) gösterir.")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(1, jenerasyon_sayisi + 1)),
                y=evrim_gecmisi,
                mode='lines+markers',
                line=dict(color='#38bdf8', width=3),
                marker=dict(size=10, color='#f59e0b')
            ))
            fig.update_layout(
                xaxis_title="Jenerasyon (Nesil)",
                yaxis_title="Maksimum Net Getiri (%)",
                template="plotly_dark",
                height=400,
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

            st.warning(
                "⚠️ **Geliştirici Notu:** Makine, geçmişte çalışan mükemmel genleri bulur (Optimizasyon). Ancak bulduğu bu 'Kutsal Kâse', geleceğin de tıpkı geçmiş gibi olacağını varsayar (Overfitting tehlikesi). Bu genleri Backtest Laboratuvarı'na girip işlemleri mantık süzgecinden geçirmeyi unutmayın.")