import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import random
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Evrimsel Crossover Laboratuvarı", page_icon="🧬", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }
    .metric-kutu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; border-bottom: 3px solid #f59e0b;}
    .metric-baslik { font-size: 0.9rem; color: #8b949e; font-weight: bold; margin-bottom: 5px; }
    .metric-deger { font-size: 1.5rem; font-weight: 800; color: #ffffff; }
    .metric-pozitif { color: #3fb950; }
    .metric-negatif { color: #f85149; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# 1. TEKNİK FONKSİYONLAR
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


@st.cache_data(ttl=3600)
def ham_veriyi_getir(sembol, yil_sayisi):
    try:
        ticker = yf.Ticker(sembol)
        isizma_payli_yil = yil_sayisi + 3
        df_d = ticker.history(period=f"{isizma_payli_yil}y")
        if df_d.empty: return None
        if df_d.index.tz is not None: df_d.index = df_d.index.tz_localize(None)
        return df_d[['Open', 'High', 'Low', 'Close']].dropna()
    except:
        return None


def veriyi_ve_indikatorleri_hazirla(df_ham, hma_periyot, yil_sayisi):
    df = df_ham.copy()
    df_w = df.resample('W').last()
    df_m = df.resample('ME').last()

    df['HMA_1D'] = hma_hesapla(df['Close'], hma_periyot)
    df_w['HMA_1W'] = hma_hesapla(df_w['Close'], hma_periyot)
    df_m['HMA_1M'] = hma_hesapla(df_m['Close'], hma_periyot)

    df['Trend_1D'] = df['HMA_1D'].diff()
    df_w['Trend_1W'] = df_w['HMA_1W'].diff()
    df_m['Trend_1M'] = df_m['HMA_1M'].diff()

    df_w['HMA_1W_Shifted'] = df_w['HMA_1W'].shift(1)
    df_w['Trend_1W_Shifted'] = df_w['Trend_1W'].shift(1)
    df_m['Trend_1M_Shifted'] = df_m['Trend_1M'].shift(1)

    df_w['Close_W'] = df_w['Close']
    df_w['Close_W_Shifted'] = df_w['Close_W'].shift(1)
    df_w['HMA_1W_Shifted_Prev'] = df_w['HMA_1W_Shifted'].shift(1)

    df = df.join(df_w[['HMA_1W_Shifted', 'Trend_1W_Shifted', 'Close_W', 'Close_W_Shifted', 'HMA_1W_Shifted_Prev']],
                 how='left').ffill()
    df = df.join(df_m[['Trend_1M_Shifted']], how='left').ffill()

    df = df.dropna()
    hedef_baslangic = df.index[-1] - pd.DateOffset(years=yil_sayisi)
    df = df[df.index >= hedef_baslangic]
    return df


# -------------------------------------------------------------
# 2. HIZLI BACKTEST MOTORU (Optimizasyon İçin)
# -------------------------------------------------------------
def hizli_crossover_backtest(df, baslangic_kasa, islem_tutari):
    kasa_nakit = baslangic_kasa
    portfoy_varlik_miktari = 0.0
    toplam_yatirilan = 0.0

    closes = df['Close'].values
    hma_1d = df['HMA_1D'].values
    trend_1m = df['Trend_1M_Shifted'].values
    trend_1w = df['Trend_1W_Shifted'].values
    hma_1w_shift = df['HMA_1W_Shifted'].values
    close_w = df['Close_W'].values
    close_w_prev = df['Close_W_Shifted'].values
    hma_1w_prev = df['HMA_1W_Shifted_Prev'].values

    for i in range(1, len(df)):
        fiyat = closes[i]

        # Satım Kuralı
        if portfoy_varlik_miktari > 0:
            if fiyat < hma_1w_shift[i]:
                satis_tutari = portfoy_varlik_miktari * fiyat
                kasa_nakit += satis_tutari
                portfoy_varlik_miktari = 0.0
                toplam_yatirilan = 0.0

        # Alım Kuralı
        haftalik_tekrar_kesis = (close_w[i] > hma_1w_shift[i]) and (close_w_prev[i] <= hma_1w_prev[i])
        haftalik_uygun = (trend_1w[i] > 0) or haftalik_tekrar_kesis

        if trend_1m[i] > 0 and haftalik_uygun:
            if fiyat > hma_1d[i] and closes[i - 1] <= hma_1d[i - 1]:
                if kasa_nakit >= islem_tutari:
                    portfoy_varlik_miktari += (islem_tutari / fiyat)
                    kasa_nakit -= islem_tutari
                    toplam_yatirilan += islem_tutari

    son_deger = kasa_nakit + (portfoy_varlik_miktari * closes[-1])
    return ((son_deger - baslangic_kasa) / baslangic_kasa) * 100


# -------------------------------------------------------------
# 3. GENETİK ALGORİTMA MOTORU
# -------------------------------------------------------------
def genetik_optimizasyon(df_ham, yil_sayisi, pop_sayisi, nesil_sayisi, st_prog, st_txt):
    # Genler: {'hma': [10-40], 'tutar': [500-2000]}
    populasyon = []
    for _ in range(pop_sayisi):
        populasyon.append({
            'hma': random.randint(10, 35),
            'tutar': random.choice([500, 750, 1000, 1500, 2000])
        })

    en_iyi_skor = -99999
    en_iyi_gen = populasyon[0]

    for nesil in range(nesil_sayisi):
        st_txt.text(f"🧬 Evrim Aşamasındayız: Jenerasyon {nesil + 1}/{nesil_sayisi} işleniyor...")
        fitness_skorlari = []

        for birey in populasyon:
            df_test = veriyi_ve_indikatorleri_hazirla(df_ham, birey['hma'], yil_sayisi)
            if df_test is None or len(df_test) < 30:
                skor = -999
            else:
                skor = hizli_crossover_backtest(df_test, 10000, birey['tutar'])
            fitness_skorlari.append((skor, birey))

        fitness_skorlari.sort(key=lambda x: x[0], reverse=True)

        if fitness_skorlari[0][0] > en_iyi_skor:
            en_iyi_skor = fitness_skorlari[0][0]
            en_iyi_gen = fitness_skorlari[0][1]

        hayatta_kalanlar = [x[1] for x in fitness_skorlari[:int(pop_sayisi / 2)]]
        yeni_nesil = [hayatta_kalanlar[0]]  # Elitizm

        while len(yeni_nesil) < pop_sayisi:
            anne = random.choice(hayatta_kalanlar)
            baba = random.choice(hayatta_kalanlar)
            cocuk = {
                'hma': anne['hma'] if random.random() > 0.5 else baba['hma'],
                'tutar': anne['tutar'] if random.random() > 0.5 else baba['tutar']
            }
            # Mutasyon (%20 ihtimal)
            if random.random() < 0.20:
                if random.random() > 0.5:
                    cocuk['hma'] = random.randint(10, 35)
                else:
                    cocuk['tutar'] = random.choice([500, 750, 1000, 1500, 2000])
            yeni_nesil.append(cocuk)

        populasyon = yeni_nesil
        st_prog.progress((nesil + 1) / nesil_sayisi)

    st_txt.text("✅ Evrim Başarıyla Tamamlandı!")
    return en_iyi_gen


# -------------------------------------------------------------
# 4. DETAYLI GRAFİK MOTORU
# -------------------------------------------------------------
def detayli_crossover_backtest(df, baslangic_kasa, islem_tutari):
    kasa_nakit = baslangic_kasa
    portfoy_varlik_miktari = 0.0
    toplam_yatirilan = 0.0

    islem_gecmisi = []
    kasa_egrisi = []

    for i in range(1, len(df)):
        bugun = df.iloc[i]
        dun = df.iloc[i - 1]
        tarih = df.index[i]
        fiyat = bugun['Close']

        guncel_portfoy_degeri = kasa_nakit + (portfoy_varlik_miktari * fiyat)
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy_degeri})

        if portfoy_varlik_miktari > 0:
            if fiyat < bugun['HMA_1W_Shifted']:
                satis_tutari = portfoy_varlik_miktari * fiyat
                kasa_nakit += satis_tutari
                getiri_orani = ((
                                            satis_tutari - toplam_yatirilan) / toplam_yatirilan) * 100 if toplam_yatirilan > 0 else 0

                islem_gecmisi.append({
                    'Tarih': tarih, 'Tip': 'SAT (Tümünü Çık)', 'Fiyat': fiyat,
                    'Neden': 'Fiyat Haftalık HMA Altına Düştü', 'Kâr/Zarar %': round(getiri_orani, 2)
                })
                portfoy_varlik_miktari = 0.0
                toplam_yatirilan = 0.0

        haftalik_tekrar_kesis = (bugun['Close_W'] > bugun['HMA_1W_Shifted']) and (
                    dun['Close_W'] <= dun['HMA_1W_Shifted_Prev'])
        haftalik_uygun = (bugun['Trend_1W_Shifted'] > 0) or haftalik_tekrar_kesis

        if bugun['Trend_1M_Shifted'] > 0 and haftalik_uygun:
            if fiyat > bugun['HMA_1D'] and dun['Close'] <= dun['HMA_1D']:
                if kasa_nakit >= islem_tutari:
                    portfoy_varlik_miktari += (islem_tutari / fiyat)
                    kasa_nakit -= islem_tutari
                    toplam_yatirilan += islem_tutari
                    islem_gecmisi.append({
                        'Tarih': tarih, 'Tip': 'AL (Ekleme)', 'Fiyat': fiyat,
                        'Neden': 'Günlük Kesişim + Haftalık Onay', 'Kâr/Zarar %': None
                    })

    df_kasa = pd.DataFrame(kasa_egrisi).set_index('Tarih')
    df_islemler = pd.DataFrame(islem_gecmisi)
    son_
    portfoy = kasa_nakit + (portfoy_varlik_miktari * df.iloc[-1]['Close'])
    return df_kasa, df_islemler, son_
    portfoy if 'son_ portfoy' in locals() else kasa_nakit


# =============================================================
# ARAYÜZ
# =============================================================
st.title("🧬 Evrimsel Crossover Laboratuvarı")
st.markdown(
    "Yapay zeka; stratejimiz için en kârlı **HMA Periyodunu** ve **Alım Tutarını** genetik algoritma evrimiyle otomatik olarak keşfeder.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Evrim Ayarları")
    sembol = st.text_input("Varlık", value="SOL-USD")
    yil_sayisi = st.slider("Geçmiş Kaç Yıl?", 1, 8, 5)
    baslangic_kasa = st.number_input("Başlangıç Kasası ($)", value=10000, step=1000)

    st.markdown("---")
    pop_sayisi = st.slider("Popülasyon (Robot Sayısı)", 10, 40, 20)
    nesil_sayisi = st.slider("Jenerasyon (Evrim Turu)", 5, 20, 10)

    st.markdown("---")
    baslat_btn = st.button("🚀 Yapay Zeka Evrimini Başlat", use_container_width=True)

with col2:
    if baslat_btn:
        df_ham = ham_veriyi_getir(sembol, yil_sayisi)
        if df_ham is None:
            st.error("Veri çekilemedi.")
        else:
            st_prog = st.progress(0)
            st_txt = st.empty()

            # 1. EVRİM AŞAMASI
            en_iyi_gen = genetik_optimizasyon(df_ham, yil_sayisi, pop_sayisi, nesil_sayisi, st_prog, st_txt)

            st.success(
                f"🏆 Yapay Zeka Kutsal Kâse Parametrelerini Buldu! -> **En İyi HMA Periyodu: {en_iyi_gen['hma']} | Sinyal Başına Alım: ${en_iyi_gen['tutar']}**")

            # 2. BULUNAN GENLERLE TEST VE GÖRSELLEŞTİRME
            df_ana = veriyi_ve_indikatorleri_hazirla(df_ham, en_iyi_gen['hma'], yil_sayisi)
            df_kasa, df_islemler, son_kasa = detayli_crossover_backtest(df_ana, baslangic_kasa, en_iyi_gen['tutar'])

            toplam_getiri = ((son_kasa - baslangic_kasa) / baslangic_kasa) * 100
            buy_hold = ((df_ana.iloc[-1]['Close'] - df_ana.iloc[0]['Close']) / df_ana.iloc[0]['Close']) * 100

            win_rate, toplam_dongu = 0, 0
            if not df_islemler.empty:
                satislar = df_islemler[df_islemler['Tip'] == 'SAT (Tümünü Çık)']
                toplam_dongu = len(satislar)
                win_rate = (len(satislar[satislar['Kâr/Zarar %'] > 0]) / toplam_dongu) * 100 if toplam_dongu > 0 else 0

            st.subheader("📊 Evrimleşmiş Strateji Sonuç Karnesi")
            m1, m2, m3, m4 = st.columns(4)
            renk = "metric-pozitif" if toplam_getiri >= 0 else "metric-negatif"
            m1.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Evrimleşmiş Getiri</div><div class='metric-deger {renk}'>% {toplam_getiri:.1f}</div></div>",
                unsafe_allow_html=True)
            m2.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Son Portföy Değeri</div><div class='metric-deger'>${son_kasa:,.0f}</div></div>",
                unsafe_allow_html=True)
            m3.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Kazanma Oranı</div><div class='metric-deger'>% {win_rate:.1f}</div></div>",
                unsafe_allow_html=True)
            m4.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>İşlem Döngüsü</div><div class='metric-deger'>{toplam_dongu}</div></div>",
                unsafe_allow_html=True)
            st.caption(f"*Not: Aynı dönemde {sembol} al-tut getirisi **%{buy_hold:.1f}** seviyesindeydi.*")

            # Renkli Çizgiler için Hazırlık
            df_ana['HMA_1D_Green'] = np.where(df_ana['Trend_1D'] > 0, df_ana['HMA_1D'], np.nan)
            df_ana['HMA_1W_Green'] = np.where(df_ana['Trend_1W_Shifted'] > 0, df_ana['HMA_1W_Shifted'], np.nan)

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig.add_trace(
                go.Scatter(x=df_ana.index, y=df_ana['Close'], name='Fiyat', line=dict(color='#8b949e', width=1.5)),
                row=1, col=1)

            fig.add_trace(go.Scatter(x=df_ana.index, y=df_ana['HMA_1D'], mode='lines', name='Günlük HMA (Kırmızı)',
                                     line=dict(color='#ff4b4b', width=1.5, dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_ana.index, y=df_ana['HMA_1D_Green'], mode='lines', name='Günlük HMA (Yeşil)',
                                     line=dict(color='#00c087', width=2, dash='dot')), row=1, col=1)

            fig.add_trace(
                go.Scatter(x=df_ana.index, y=df_ana['HMA_1W_Shifted'], mode='lines', name='Haftalık HMA (Kırmızı)',
                           line=dict(color='#ff4b4b', width=3)), row=1, col=1)
            fig.add_trace(
                go.Scatter(x=df_ana.index, y=df_ana['HMA_1W_Green'], mode='lines', name='Haftalık HMA (Yeşil)',
                           line=dict(color='#00c087', width=3)), row=1, col=1)

            if not df_islemler.empty:
                alimlar = df_islemler[df_islemler['Tip'] == 'AL (Ekleme)']
                satimlar = df_islemler[df_islemler['Tip'] == 'SAT (Tümünü Çık)']
                fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='AL Sinyali',
                                         marker=dict(color='#00c087', size=8, symbol='circle')), row=1, col=1)
                fig.add_trace(go.Scatter(x=satimlar['Tarih'], y=satimlar['Fiyat'], mode='markers', name='SAT Sinyali',
                                         marker=dict(color='#ff4b4b', size=12, symbol='triangle-down')), row=1, col=1)

            fig.add_trace(go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], fill='tozeroy', name='Portföy ($)',
                                     line=dict(color='#f59e0b', width=2), fillcolor='rgba(245, 158, 11, 0.1)'), row=2,
                          col=1)
            fig.update_layout(height=700, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0),
                              hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)