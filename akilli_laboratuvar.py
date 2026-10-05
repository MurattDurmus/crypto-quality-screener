import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import random
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Otonom MTF Laboratuvarı", page_icon="🧬", layout="wide")

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


# =============================================================
# 1. ORTAK MATEMATİK VE İNDİKATÖR MOTORU
# =============================================================
def wma(seri, periyot):
    weights = np.arange(1, periyot + 1)
    return seri.rolling(periyot).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True)


def hma_hesapla(seri, periyot):
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    wma_half = wma(seri, half_length)
    wma_full = wma(seri, periyot)
    return wma((2 * wma_half - wma_full), sqrt_length)


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


# =============================================================
# 2. HIZLI GENETİK OPTİMİZASYON MOTORU
# =============================================================
def veriye_genleri_uygula(df_ham, hma_periyot):
    df = df_ham.copy()
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


def hizli_backtest(df, stop_loss, take_profit):
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
            if trend_m[i] > 0 and trend_w[i] > 0 and trend_d[i] > 0 and trend_d[i - 1] <= 0:
                pozisyonda_mi = True
                giris_fiyati = kapanislar[i]
                stop_fiyati = giris_fiyati * (1 - stop_loss / 100)
                hedef_fiyat = giris_fiyati * (1 + take_profit / 100)
        else:
            if dusukler[i] <= stop_fiyati:
                kasa *= (1 + ((stop_fiyati - giris_fiyati) / giris_fiyati))
                pozisyonda_mi = False
            elif yuksekler[i] >= hedef_fiyat:
                kasa *= (1 + ((hedef_fiyat - giris_fiyati) / giris_fiyati))
                pozisyonda_mi = False
            elif trend_w[i] <= 0:
                kasa *= (1 + ((kapanislar[i] - giris_fiyati) / giris_fiyati))
                pozisyonda_mi = False

    return ((kasa - 10000.0) / 10000.0) * 100


def genetik_bulucu(df_ham, pop_sayisi, gen_sayisi, st_progress, st_text):
    populasyon = [{'sl': random.randint(3, 15), 'tp': random.randint(15, 80), 'hma': random.randint(12, 40)} for _ in
                  range(pop_sayisi)]

    for jenerasyon in range(gen_sayisi):
        st_text.text(f"🧬 Yapay Zeka Düşünüyor: Jenerasyon {jenerasyon + 1}/{gen_sayisi}...")
        fitness = []
        for birey in populasyon:
            df_is = veriye_genleri_uygula(df_ham, birey['hma'])
            skor = hizli_backtest(df_is, birey['sl'], birey['tp'])
            fitness.append((skor, birey))

        fitness.sort(key=lambda x: x[0], reverse=True)
        en_iyi = fitness[0]

        hayatta_kalanlar = [x[1] for x in fitness[:int(pop_sayisi / 2)]]
        yeni_nesil = []
        yeni_nesil.extend(hayatta_kalanlar[:2])  # Elitizm

        while len(yeni_nesil) < pop_sayisi:
            anne = random.choice(hayatta_kalanlar)
            baba = random.choice(hayatta_kalanlar)
            cocuk = {
                'sl': anne['sl'] if random.random() > 0.5 else baba['sl'],
                'tp': anne['tp'] if random.random() > 0.5 else baba['tp'],
                'hma': anne['hma'] if random.random() > 0.5 else baba['hma']
            }
            if random.random() < 0.20:  # Mutasyon
                mut_gen = random.choice(['sl', 'tp', 'hma'])
                if mut_gen == 'sl':
                    cocuk['sl'] = random.randint(3, 15)
                elif mut_gen == 'tp':
                    cocuk['tp'] = random.randint(15, 80)
                elif mut_gen == 'hma':
                    cocuk['hma'] = random.randint(12, 40)
            yeni_nesil.append(cocuk)

        populasyon = yeni_nesil
        st_progress.progress((jenerasyon + 1) / gen_sayisi)

    st_text.text("✅ Optimizasyon Tamamlandı!")
    return en_iyi[1]


# =============================================================
# 3. DETAYLI BACKTEST VE GÖRSELLEŞTİRME MOTORU
# =============================================================
def gorsel_backtest_calistir(df, baslangic_kasa, stop_loss_yuzde, take_profit_yuzde):
    kasa = baslangic_kasa
    pozisyonda_mi = False
    giris_fiyati = 0
    islem_gecmisi = []
    kasa_egrisi = []

    for i in range(1, len(df)):
        bugun = df.iloc[i]
        dun = df.iloc[i - 1]
        tarih = df.index[i]

        guncel_portfoy_degeri = kasa if not pozisyonda_mi else (kasa / giris_fiyati) * bugun['Close']
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy_degeri})

        if not pozisyonda_mi:
            if bugun['Trend_M_Shift'] > 0 and bugun['Trend_W_Shift'] > 0:
                if bugun['Trend_D'] > 0 and dun['Trend_D'] <= 0:
                    pozisyonda_mi = True
                    giris_fiyati = bugun['Close']
                    stop_fiyati = giris_fiyati * (1 - stop_loss_yuzde / 100)
                    hedef_fiyat = giris_fiyati * (1 + take_profit_yuzde / 100)
                    islem_gecmisi.append({'Tarih': tarih, 'Tip': 'AL', 'Fiyat': giris_fiyati, 'Neden': '3x MTF Dönüş'})
        else:
            satis_nedeni = ""
            if bugun['Low'] <= stop_fiyati:
                satis_nedeni = f"🛑 Stop-Loss (-%{stop_loss_yuzde})"
            elif bugun['High'] >= hedef_fiyat:
                satis_nedeni = f"🎯 Kâr Al (+%{take_profit_yuzde})"
            elif bugun['Trend_W_Shift'] <= 0:
                satis_nedeni = "⚠️ Trend Bozuldu"

            if satis_nedeni != "":
                pozisyonda_mi = False
                satis_fiyati = stop_fiyati if "Stop" in satis_nedeni else (
                    hedef_fiyat if "Kâr" in satis_nedeni else bugun['Close'])
                getiri_orani = (satis_fiyati - giris_fiyati) / giris_fiyati
                kasa *= (1 + getiri_orani)
                islem_gecmisi.append({'Tarih': tarih, 'Tip': 'SAT', 'Fiyat': satis_fiyati, 'Neden': satis_nedeni,
                                      'Kâr/Zarar %': round(getiri_orani * 100, 2)})

    return pd.DataFrame(kasa_egrisi).set_index('Tarih'), pd.DataFrame(islem_gecmisi), kasa


def sonuclari_ciz(sembol, df_ana, df_kasa, df_islemler, son_kasa, baslangic_kasa):
    toplam_getiri = ((son_kasa - baslangic_kasa) / baslangic_kasa) * 100
    buy_hold_getiri = ((df_ana.iloc[-1]['Close'] - df_ana.iloc[0]['Close']) / df_ana.iloc[0]['Close']) * 100

    win_rate, toplam_islem = 0, 0
    if not df_islemler.empty:
        satislar = df_islemler[df_islemler['Tip'] == 'SAT']
        toplam_islem = len(satislar)
        win_rate = (len(satislar[satislar['Kâr/Zarar %'] > 0]) / toplam_islem) * 100 if toplam_islem > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    renk = "metric-pozitif" if toplam_getiri >= 0 else "metric-negatif"
    m1.markdown(
        f"<div class='metric-kutu'><div class='metric-baslik'>Net Getiri</div><div class='metric-deger {renk}'>% {toplam_getiri:.1f}</div></div>",
        unsafe_allow_html=True)
    m2.markdown(
        f"<div class='metric-kutu'><div class='metric-baslik'>Son Kasa Değeri</div><div class='metric-deger'>${son_kasa:,.0f}</div></div>",
        unsafe_allow_html=True)
    m3.markdown(
        f"<div class='metric-kutu'><div class='metric-baslik'>Kazanma Oranı</div><div class='metric-deger'>% {win_rate:.1f}</div></div>",
        unsafe_allow_html=True)
    m4.markdown(
        f"<div class='metric-kutu'><div class='metric-baslik'>İşlem Sayısı</div><div class='metric-deger'>{toplam_islem}</div></div>",
        unsafe_allow_html=True)
    st.caption(f"*Not: {sembol} varlığını alıp hiç satmasaydınız getiri **%{buy_hold_getiri:.1f}** olacaktı.*")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
    fig.add_trace(go.Scatter(x=df_ana.index, y=df_ana['Close'], name='Fiyat', line=dict(color='#8b949e', width=1)),
                  row=1, col=1)

    if not df_islemler.empty:
        alimlar = df_islemler[df_islemler['Tip'] == 'AL']
        satimlar = df_islemler[df_islemler['Tip'] == 'SAT']
        fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='AL',
                                 marker=dict(color='#00c087', size=10, symbol='triangle-up')), row=1, col=1)
        fig.add_trace(go.Scatter(x=satimlar['Tarih'], y=satimlar['Fiyat'], mode='markers', name='SAT',
                                 marker=dict(color='#ff4b4b', size=10, symbol='triangle-down')), row=1, col=1)

    fig.add_trace(go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], fill='tozeroy', name='Kasa ($)',
                             line=dict(color='#58a6ff', width=2)), row=2, col=1)
    fig.update_layout(height=600, template="plotly_dark", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)


# =============================================================
# ARAYÜZ (Ana Kontrol Paneli)
# =============================================================
st.title("🧪 Otonom MTF Laboratuvarı")
st.markdown("Genetik motoru kullanarak en kârlı ayarları keşfedin ve doğrudan görselleştirin.")

col_ayar, col_grafik = st.columns([1, 3])

with col_ayar:
    st.subheader("1. Temel Ayarlar")
    sembol = st.text_input("Varlık Sembolü", value="BTC-USD")
    yil = st.slider("Geçmiş Veri (Yıl)", 1, 5, 4)
    kasa = st.number_input("Başlangıç Kasası ($)", value=10000, step=1000)

    st.markdown("---")
    st.subheader("2. Simülasyon Yöntemi")
    mod = st.radio("Çalışma Modu Seçin:", ["🤖 Yapay Zeka (Otopilot)", "⚙️ Manuel Ayarlar"])

    if mod == "⚙️ Manuel Ayarlar":
        m_sl = st.number_input("Stop-Loss %", value=8)
        m_tp = st.number_input("Take-Profit %", value=73)
        m_hma = st.number_input("HMA Periyodu", value=19)
        baslat_manuel = st.button("▶️ Testi Başlat", use_container_width=True)
    else:
        pop = st.slider("Genetik Popülasyon", 10, 50, 20)
        nesil = st.slider("Jenerasyon (Öğrenme Turu)", 5, 20, 10)
        baslat_oto = st.button("🧬 Keşfet ve Test Et", use_container_width=True)

with col_grafik:
    if mod == "⚙️ Manuel Ayarlar" and baslat_manuel:
        with st.spinner("Manuel simülasyon çalıştırılıyor..."):
            df_ham = ham_veriyi_getir(sembol, yil)
            if df_ham is not None:
                df_islenmis = veriye_genleri_uygula(df_ham, m_hma)
                df_kasa, df_isl, son_kasa = gorsel_backtest_calistir(df_islenmis, kasa, m_sl, m_tp)
                sonuclari_ciz(sembol, df_islenmis, df_kasa, df_isl, son_kasa, kasa)

    elif mod == "🤖 Yapay Zeka (Otopilot)" and baslat_oto:
        df_ham = ham_veriyi_getir(sembol, yil)
        if df_ham is not None:
            # 1. Genetik Optimizasyon Aşaması
            st_prog = st.progress(0)
            st_txt = st.empty()
            en_iyi = genetik_bulucu(df_ham, pop, nesil, st_prog, st_txt)

            st.success(
                f"Yapay Zeka Mükemmel Genleri Buldu: **Stop-Loss: %{en_iyi['sl']} | Kâr Al: %{en_iyi['tp']} | HMA Periyot: {en_iyi['hma']}**")

            # 2. Bulunan Genlerle Test Aşaması
            df_islenmis = veriye_genleri_uygula(df_ham, en_iyi['hma'])
            df_kasa, df_isl, son_kasa = gorsel_backtest_calistir(df_islenmis, kasa, en_iyi['sl'], en_iyi['tp'])
            sonuclari_ciz(sembol, df_islenmis, df_kasa, df_isl, son_kasa, kasa)
        else:
            st.error("Veri çekilemedi.")