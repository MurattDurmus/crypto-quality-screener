import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import random
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Stonkfly - Sinek Beyinli Kripto Simülatörü", page_icon="🪰", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }
    .metric-kutu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; border-bottom: 3px solid #00f2fe;}
    .metric-baslik { font-size: 0.9rem; color: #8b949e; font-weight: bold; margin-bottom: 5px; }
    .metric-deger { font-size: 1.5rem; font-weight: 800; color: #ffffff; }
    .metric-pozitif { color: #3fb950; }
    .metric-negatif { color: #f85149; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# 1. SİNEK GÖZÜ DUYU VE PİKSEL ÇEVRİMİ
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def ham_veriyi_getir(sembol, gun_sayisi):
    try:
        ticker = yf.Ticker(sembol)
        df_h = ticker.history(period=f"{gun_sayisi}d", interval="1h")
        if df_h.empty: return None
        if df_h.index.tz is not None: df_h.index = df_h.index.tz_localize(None)
        return df_h[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except:
        return None


def sinek_duyularini_hazirla(df_ham):
    df = df_ham.copy()

    # Kripto grafik piksellerini sineğin ommatidyum (göz) girdilerine dönüştürme:
    # 1. Anlık Fiyat Hızı (Optik Akış)
    df['Optik_Akis'] = df['Close'].pct_change(periods=2) * 100

    # 2. Hacim Presi (Çevresel Uyarıcı)
    vol_ma = df['Volume'].rolling(24).mean()
    df['Hacim_Presi'] = np.where(vol_ma > 0, df['Volume'] / vol_ma, 1.0)

    # 3. Volatilite (Tehlike Algısı)
    df['Tehlike_Algisi'] = (df['High'] - df['Low']) / df['Close'] * 100

    df = df.dropna()
    return df


# -------------------------------------------------------------
# 2. SİNEK BEYNİ SİMÜLASYONU (DOPAMİN & CAYDIRICI NÖRONLAR)
# -------------------------------------------------------------
def stonkfly_simulasyon(df, baslangic_kasa):
    kasa_nakit = baslangic_kasa
    portfoy_varlik_miktari = 0.0

    islem_gecmisi = []
    kasa_egrisi = []

    closes = df['Close'].values
    akis = df['Optik_Akis'].values
    pres = df['Hacim_Presi'].values
    tehlike = df['Tehlike_Algisi'].values

    # Sinek Sinaptik Ağırlıkları (Başlangıç Değerleri)
    w_akis = 1.2
    w_pres = 0.8
    w_tehlike = -0.5
    atesleme_esigi = 2.0

    alis_fiyati = 0.0

    for i in range(1, len(df)):
        fiyat = closes[i]
        tarih = df.index[i]

        guncel_portfoy_degeri = kasa_nakit + (portfoy_varlik_miktari * fiyat)
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy_degeri})

        # Sinek Nöronal Membran Potansiyeli
        noron_yuku = (akis[i] * w_akis) + (pres[i] * w_pres) + (tehlike[i] * w_tehlike)

        if portfoy_varlik_miktari > 0:
            # Pozisyonda iken kâr/zarar kontrolü (Dopamin veya Caydırıcı tetikleme)
            anlik_kar_orani = ((fiyat - alis_fiyati) / alis_fiyati) * 100

            # Zarar büyükse caydırıcı hücreler uyarılır, kârda ise dopamin salgılanır
            if anlik_kar_orani <= -4.0 or noron_yuku < -1.5:
                # CAYDIRICI HÜCRE UYARILDI (Zarar cezası: ağırlıklar törpülenir)
                w_akis *= 0.95
                w_pres *= 0.95

                satis_tutari = portfoy_varlik_miktari * fiyat
                kasa_nakit += satis_tutari
                islem_gecmisi.append({
                    'Tarih': tarih, 'Tip': 'SATIŞ (Caydırıcı)', 'Fiyat': fiyat,
                    'Neden': f'Zarar Kes / Caydırıcı Uyarısı (%{anlik_kar_orani:.1f})',
                    'Kâr/Zarar %': round(anlik_kar_orani, 2)
                })
                portfoy_varlik_miktari = 0.0
                alis_fiyati = 0.0
            elif anlik_kar_orani >= 8.0:
                # DOPAMİN HÜCRELERİ UYARILDI (15 Dopamin hücresi ödülü: sinaptik ağırlıklar güçlenir)
                w_akis *= 1.05
                w_pres *= 1.05

                satis_tutari = portfoy_varlik_miktari * fiyat
                kasa_nakit += satis_tutari
                islem_gecmisi.append({
                    'Tarih': tarih, 'Tip': 'SATIŞ (Dopamin Hedefi)', 'Fiyat': fiyat,
                    'Neden': f'Hedef Kâr Realizasyonu (%{anlik_kar_orani:.1f})',
                    'Kâr/Zarar %': round(anlik_kar_orani, 2)
                })
                portfoy_varlik_miktari = 0.0
                alis_fiyati = 0.0
        else:
            # ALIM KURALI: Nöron yükü ateşleme eşiğini aşarsa sinek hamle yapar
            if noron_yuku > atesleme_esigi and kasa_nakit > 10:
                alim_tutari = kasa_nakit * 0.50  # Kasanın yarısı ile parça alım
                portfoy_varlik_miktari += (alim_tutari / fiyat)
                kasa_nakit -= alim_tutari
                alis_fiyati = fiyat

                islem_gecmisi.append({
                    'Tarih': tarih, 'Tip': 'ALIM (Sinek Refleksi)', 'Fiyat': fiyat,
                    'Neden': f'Nöron Ateşlendi (Yük: {noron_yuku:.2f})',
                    'Kâr/Zarar %': None
                })

    df_kasa = pd.DataFrame(kasa_egrisi).set_index('Tarih') if kasa_egrisi else pd.DataFrame({'Kasa': [baslangic_kasa]},
                                                                                            index=[df.index[0]])
    df_islemler = pd.DataFrame(islem_gecmisi) if islem_gecmisi else pd.DataFrame(
        columns=['Tarih', 'Tip', 'Fiyat', 'Neden', 'Kâr/Zarar %'])
    son_portfoy = kasa_nakit + (portfoy_varlik_miktari * closes[-1])

    return ((son_portfoy - baslangic_kasa) / baslangic_kasa) * 100, df_kasa, df_islemler, son_portfoy


# =============================================================
# ARAYÜZ
# =============================================================
st.title("🪰 Stonkfly: Sinek Beyinli Kripto Simülatörü")
st.markdown(
    "**Sistem Mimarisi:** MaleCNS v1.0 connectome ilkelerine dayanır. Fiyat pikselleri optik akışa dönüştürülür; kâr durumunda 15 dopamin hücresi, zarar durumunda caydırıcı hücreler tetiklenerek sinaptik ağırlıklar anlık olarak güncellenir.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Simülasyon Ayarları")
    sembol = st.text_input("Varlık", value="BTC-USD")
    gun_sayisi = st.slider("Geçmiş Kaç Gün?", 30, 365, 180)
    baslangic_kasa = st.number_input("Başlangıç Bakiyesi ($)", value=100.0, step=10.0)  # Varsayılan 100$ kağıt para

    baslat_btn = st.button("🚀 Stonkfly Simülasyonunu Başlat", use_container_width=True)

with col2:
    if baslat_btn:
        df_ham = ham_veriyi_getir(sembol, gun_sayisi)
        if df_ham is None or df_ham.empty:
            st.error("Veri alınamadı.")
        else:
            df_sinek = sinek_duyularini_hazirla(df_ham)
            toplam_getiri, df_kasa, df_islemler, son_kasa = stonks_getiri = stonkfly_simulasyon(df_sinek,
                                                                                                baslangic_kasa)

            buy_hold = ((df_sinek.iloc[-1]['Close'] - df_sinek.iloc[0]['Close']) / df_sinek.iloc[0]['Close']) * 100

            win_rate, toplam_islem = 0, 0
            if not df_islemler.empty and 'Tip' in df_islemler.columns:
                satislar = df_islemler[df_islemler['Tip'].str.contains('SATIŞ')]
                toplam_islem = len(satislar)
                if toplam_islem > 0:
                    win_rate = (len(satislar[satislar['Kâr/Zarar %'] > 0]) / toplam_islem) * 100

            st.subheader("📊 Stonkfly Performans Karnesi")
            m1, m2, m3, m4 = st.columns(4)
            renk = "metric-pozitif" if toplam_getiri >= 0 else "metric-negatif"
            m1.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Sinek Getirisi</div><div class='metric-deger {renk}'>% {toplam_getiri:.1f}</div></div>",
                unsafe_allow_html=True)
            m2.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Son Bakiye</div><div class='metric-deger'>${son_kasa:,.2f}</div></div>",
                unsafe_allow_html=True)
            m3.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Başarı Oranı</div><div class='metric-deger'>% {win_rate:.1f}</div></div>",
                unsafe_allow_html=True)
            m4.markdown(
                f"<div class='metric-kutu'><div class='metric-baslik'>Toplam İşlem</div><div class='metric-deger'>{toplam_islem}</div></div>",
                unsafe_allow_html=True)
            st.caption(f"*Not: Aynı dönemde {sembol} al-tut getirisi **%{buy_hold:.1f}** seviyesindeydi.*")

            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

            fig.add_trace(go.Scatter(x=df_sinek.index, y=df_sinek['Close'], name='Fiyat (1H)',
                                     line=dict(color='#8b949e', width=1.5)), row=1, col=1)

            if not df_islemler.empty and 'Tip' in df_islemler.columns:
                alimlar = df_islemler[df_islemler['Tip'].str.contains('ALIM')]
                satislar = df_islemler[df_islemler['Tip'].str.contains('SATIŞ')]

                if not alimlar.empty:
                    fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='Sinek Alımı',
                                             marker=dict(color='#00c087', size=9, symbol='circle')), row=1, col=1)
                if not satislar.empty:
                    fig.add_trace(
                        go.Scatter(x=satislar['Tarih'], y=satislar['Fiyat'], mode='markers', name='Sinek Satışı',
                                   marker=dict(color='#ff4b4b', size=11, symbol='triangle-down')), row=1, col=1)

            fig.add_trace(go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], fill='tozeroy', name='Portföy ($)',
                                     line=dict(color='#00f2fe', width=2), fillcolor='rgba(0, 242, 254, 0.1)'), row=2,
                          col=1)

            fig.update_layout(height=750, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0),
                              hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            if not df_islemler.empty and 'Tip' in df_islemler.columns:
                st.subheader("📋 Sinek Nöronal İşlem Logları")
                df_gosterim = df_islemler.copy()
                df_gosterim['Tarih'] = df_gosterim['Tarih'].dt.strftime('%Y-%m-%d %H:%M')
                df_gosterim['Fiyat'] = df_gosterim['Fiyat'].apply(lambda x: f"${x:,.2f}")
                st.dataframe(df_gosterim, use_container_width=True)