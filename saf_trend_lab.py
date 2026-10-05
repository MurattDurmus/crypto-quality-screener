import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Saf Trend Sörfü Laboratuvarı", page_icon="🏄‍♂️", layout="wide")

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
# TEKNİK FONKSİYONLAR
# -------------------------------------------------------------
def wma(seri, periyot):
    weights = np.arange(1, periyot + 1)
    return seri.rolling(periyot).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True)


def hma_hesapla(seri, periyot):
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    wma_half = wma(seri, half_length)
    wma_full = wma(seri, periyot)
    fark = 2 * wma_half - wma_full
    return wma(fark, sqrt_length)


@st.cache_data(ttl=3600)
def verileri_hazirla(sembol, yil_sayisi, hma_periyot):
    try:
        ticker = yf.Ticker(sembol)
        df_d = ticker.history(period=f"{yil_sayisi}y")

        if df_d.empty: return None
        if df_d.index.tz is not None: df_d.index = df_d.index.tz_localize(None)
        df_d = df_d.dropna(subset=['Close'])

        df_w = df_d.resample('W').last()
        df_m = df_d.resample('ME').last()

        df_d['HMA_1D'] = hma_hesapla(df_d['Close'], hma_periyot)
        df_w['HMA_1W'] = hma_hesapla(df_w['Close'], hma_periyot)
        df_m['HMA_1M'] = hma_hesapla(df_m['Close'], hma_periyot)

        df_d['Trend_1D'] = df_d['HMA_1D'].diff()
        df_w['Trend_1W'] = df_w['HMA_1W'].diff()
        df_m['Trend_1M'] = df_m['HMA_1M'].diff()

        df_w['Trend_1W_Shifted'] = df_w['Trend_1W'].shift(1)
        df_m['Trend_1M_Shifted'] = df_m['Trend_1M'].shift(1)

        df_d = df_d.join(df_w[['Trend_1W_Shifted']], how='left').ffill()
        df_d = df_d.join(df_m[['Trend_1M_Shifted']], how='left').ffill()

        return df_d.dropna()
    except Exception:
        return None


# -------------------------------------------------------------
# KADEMELİ ALIM STRATEJİ MOTORU
# -------------------------------------------------------------
def kademeli_trend_backtest(df, baslangic_kasa, islem_tutari):
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

        # Güncel Portföy Değeri (Nakit + Varlıkların o anki değeri)
        guncel_portfoy_degeri = kasa_nakit + (portfoy_varlik_miktari * fiyat)
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy_degeri})

        # --- KADEMELİ ALIM KURALI ---
        # Aylık ve Haftalık Yeşilken, Günlük taze yeşile döndüğünde AL (Kasada nakit varsa)
        if bugun['Trend_1M_Shifted'] > 0 and bugun['Trend_1W_Shifted'] > 0:
            if bugun['Trend_1D'] > 0 and dun['Trend_1D'] <= 0:
                if kasa_nakit >= islem_tutari:
                    alinacak_miktar = islem_tutari / fiyat
                    portfoy_varlik_miktari += alinacak_miktar
                    kasa_nakit -= islem_tutari
                    toplam_yatirilan += islem_tutari

                    islem_gecmisi.append({
                        'Tarih': tarih,
                        'Tip': 'AL (Ekleme)',
                        'Fiyat': fiyat,
                        'Neden': 'Günlük Taze Yeşil',
                        'Kâr/Zarar %': None
                    })

        # --- SATIM KURALI (TOPTAN ÇIKIŞ) ---
        # Haftalık Kırmızıya döndüğünde elimizdeki tüm malı SAT
        if bugun['Trend_1W_Shifted'] <= 0 and portfoy_varlik_miktari > 0:
            satis_tutari = portfoy_varlik_miktari * fiyat
            kasa_nakit += satis_tutari

            # Bu döngüdeki ortalama getiri
            getiri_orani = ((satis_tutari - toplam_yatirilan) / toplam_yatirilan) * 100 if toplam_yatirilan > 0 else 0

            islem_gecmisi.append({
                'Tarih': tarih,
                'Tip': 'SAT (Tümünü Çık)',
                'Fiyat': fiyat,
                'Neden': 'Haftalık Trend Bozuldu',
                'Kâr/Zarar %': round(getiri_orani, 2)
            })

            # Portföyü sıfırla, yeni bir ralli için nakitte bekle
            portfoy_varlik_miktari = 0.0
            toplam_yatirilan = 0.0

    df_kasa = pd.DataFrame(kasa_egrisi).set_index('Tarih')
    df_islemler = pd.DataFrame(islem_gecmisi)

    # Son günkü toplam değeri döndür
    son_portfoy_degeri = kasa_nakit + (portfoy_varlik_miktari * df.iloc[-1]['Close'])

    return df_kasa, df_islemler, son_portfoy_degeri


# =============================================================
# ARAYÜZ
# =============================================================
st.title("🏄‍♂️ Saf Trend Sörfü (Kademeli Alım)")
st.markdown(
    "**Strateji Kuralı:** Toplam kasanız vardır. Aylık ve Haftalık HMA yeşilken, her günlük taze yeşil sinyalinde belirlediğiniz tutar kadar **kademeli alım (ekleme)** yapılır. Haftalık HMA kırmızıya döndüğünde elde biriken tüm varlıklar satılır ve nakde geçilir.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Ayarlar")
    sembol = st.text_input("Varlık", value="BTC-USD")
    yil_sayisi = st.slider("Geçmiş Kaç Yıl?", 1, 5, 4)
    hma_periyot = st.number_input("HMA Periyodu", value=19, step=1)

    st.markdown("---")
    baslangic_kasa = st.number_input("Toplam Kasa ($)", value=10000, step=1000)
    islem_tutari = st.number_input("Her Sinyalde Alınacak Tutar ($)", value=500, step=100)
    st.markdown("---")
    baslat_btn = st.button("🚀 Kademeli Modu Test Et", use_container_width=True)

with col2:
    if baslat_btn:
        with st.spinner(f"{sembol} test ediliyor. Kademeli alım ve toptan satım motoru devrede..."):
            df_ana = verileri_hazirla(sembol, yil_sayisi, hma_periyot)

            if df_ana is None or len(df_ana) < 50:
                st.error("Veri çekilemedi.")
            else:
                df_kasa, df_islemler, son_kasa = kademeli_trend_backtest(df_ana, baslangic_kasa, islem_tutari)

                toplam_getiri_yuzde = ((son_kasa - baslangic_kasa) / baslangic_kasa) * 100

                if not df_islemler.empty:
                    satislar = df_islemler[df_islemler['Tip'] == 'SAT (Tümünü Çık)']
                    toplam_islem_dongusu = len(satislar)
                    basarili_islem = len(satislar[satislar['Kâr/Zarar %'] > 0])
                    win_rate = (basarili_islem / toplam_islem_dongusu) * 100 if toplam_islem_dongusu > 0 else 0
                else:
                    toplam_islem_dongusu = 0
                    win_rate = 0

                ilk_fiyat = df_ana.iloc[0]['Close']
                son_fiyat = df_ana.iloc[-1]['Close']
                buy_hold_getiri = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100

                st.subheader("📊 Kademeli Strateji Sonuçları")
                m1, m2, m3, m4 = st.columns(4)

                renk_sinifi = "metric-pozitif" if toplam_getiri_yuzde >= 0 else "metric-negatif"

                m1.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Strateji Net Getirisi</div><div class='metric-deger {renk_sinifi}'>% {toplam_getiri_yuzde:.1f}</div></div>",
                    unsafe_allow_html=True)
                m2.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Son Portföy Değeri</div><div class='metric-deger'>${son_kasa:,.0f}</div></div>",
                    unsafe_allow_html=True)
                m3.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Kazanma Oranı (Win Rate)</div><div class='metric-deger'>% {win_rate:.1f}</div></div>",
                    unsafe_allow_html=True)
                m4.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Tamamlanan İşlem Döngüsü</div><div class='metric-deger'>{toplam_islem_dongusu}</div></div>",
                    unsafe_allow_html=True)

                st.caption(
                    f"*Not: Eğer en başta tüm paranızla {sembol} alıp hiç satmasaydınız getiri **%{buy_hold_getiri:.1f}** olacaktı. 'İşlem Döngüsü' alımların toplanıp tek seferde satıldığı serileri temsil eder.*")

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

                fig.add_trace(
                    go.Scatter(x=df_ana.index, y=df_ana['Close'], name='Fiyat', line=dict(color='#8b949e', width=1)),
                    row=1, col=1)

                if not df_islemler.empty:
                    alimlar = df_islemler[df_islemler['Tip'] == 'AL (Ekleme)']
                    satimlar = df_islemler[df_islemler['Tip'] == 'SAT (Tümünü Çık)']

                    fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='AL (Ekleme)',
                                             marker=dict(color='#00c087', size=8, symbol='circle')), row=1, col=1)
                    fig.add_trace(
                        go.Scatter(x=satimlar['Tarih'], y=satimlar['Fiyat'], mode='markers', name='SAT (Komple Çıkış)',
                                   marker=dict(color='#ff4b4b', size=12, symbol='triangle-down')), row=1, col=1)

                fig.add_trace(go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], fill='tozeroy', name='Portföy Değeri ($)',
                                         line=dict(color='#58a6ff', width=2), fillcolor='rgba(88, 166, 255, 0.1)'),
                              row=2, col=1)

                fig.update_layout(height=600, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0),
                                  hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                if not df_islemler.empty:
                    st.subheader("📋 İşlem Geçmişi (Log)")
                    df_gosterim = df_islemler.copy()
                    df_gosterim['Tarih'] = df_gosterim['Tarih'].dt.strftime('%Y-%m-%d')
                    df_gosterim['Fiyat'] = df_gosterim['Fiyat'].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df_gosterim, use_container_width=True)