import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from neuprint import Client, fetch_adjacencies

st.set_page_config(page_title="Nöro-Quant Laboratuvarı (Saf Makro Trend Botu)", page_icon="🧠", layout="wide")

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
# 1. SİNEK KONEKTOMU YÜKLEME
# -------------------------------------------------------------
@st.cache_data(ttl=86400)
def sinek_noronlarini_yukle(token):
    try:
        c = Client('neuprint.janelia.org', dataset='hemibrain:v1.2.1', token=token)
        _, conn_df = fetch_adjacencies(rois=['MB(R)'], include_nonprimary=True)
        if conn_df is not None and not conn_df.empty:
            weights = conn_df['weight'].values
            return {'faktor': float(np.clip(np.mean(weights) / 10.0, 0.5, 2.0)), 'baglanti_sayisi': len(conn_df)}
    except:
        pass
    return {'faktor': 1.0, 'baglanti_sayisi': 0}


@st.cache_data(ttl=3600)
def veri_getir(sembol, gun_sayisi):
    try:
        ticker = yf.Ticker(sembol)
        df = ticker.history(period=f"{gun_sayisi}d", interval="1d")
        if df.empty: return None
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except:
        return None


# -------------------------------------------------------------
# 2. AYLIK CDLTRD HESAPLAMA
# -------------------------------------------------------------
def wma(seri, periyot):
    weights = np.arange(1, periyot + 1)
    return seri.rolling(periyot).apply(lambda p: np.dot(p, weights) / weights.sum(), raw=True)


def hma_hesapla(seri, periyot):
    if len(seri) < periyot: periyot = max(2, len(seri) // 2)
    if periyot < 2: return seri
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    wma_half = wma(seri, half_length)
    wma_full = wma(seri, periyot)
    return wma((2 * wma_half - wma_full), sqrt_length)


def veri_hazirla(df, malength=20):
    d = df.copy()
    df_aylik = d['Close'].resample('ME').last().dropna()
    hma_1m = hma_hesapla(df_aylik, malength)
    cdl_1m_green = hma_1m > hma_1m.shift(1)

    d['CDLTRD_1M'] = hma_1m.reindex(d.index).ffill()
    d['CDL_1M_Green'] = cdl_1m_green.reindex(d.index).ffill().fillna(False)
    return d.dropna()


# -------------------------------------------------------------
# 3. SAF MAKRO TREND TEST MOTORU (AL VE TUT)
# -------------------------------------------------------------
def saf_makro_test(df, baslangic_kasa):
    kasa_nakit = baslangic_kasa
    portfoy_varlik = 0.0
    islem_gecmisi = []
    kasa_egrisi = []

    closes = df['Close'].values
    aylik_green = df['CDL_1M_Green'].values
    komisyon_orani = 0.001

    pozisyonda_mi = False

    for i in range(1, len(df)):
        fiyat = closes[i]
        tarih = df.index[i]

        guncel_portfoy = kasa_nakit + (portfoy_varlik * fiyat)
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy})

        yesil_mi = aylik_green[i]

        # Aylık CDLTRD Kırmızıya döndü ve portföyde mal varsa -> HEPSİNİ SAT
        if not yesil_mi and pozisyonda_mi:
            satis_tutari = portfoy_varlik * fiyat
            komisyon = satis_tutari * komisyon_orani
            kasa_nakit += (satis_tutari - komisyon)
            islem_gecmisi.append({'Tarih': tarih, 'Tip': 'SATIŞ (AYI SEZONU)', 'Fiyat': fiyat, 'Kâr/Zarar %': 0.0})
            portfoy_varlik = 0.0
            pozisyonda_mi = False
            continue

        # Kırmızı iken işlem yapma
        if not yesil_mi:
            continue

        # Aylık CDLTRD Yeşil ve malda değiliz -> TEK KALEMDE AL VE TUT
        if yesil_mi and not pozisyonda_mi:
            harcanacak = kasa_nakit * 0.99
            if harcanacak > 50:
                komisyon = harcanacak * komisyon_orani
                portfoy_varlik += ((harcanacak - komisyon) / fiyat)
                kasa_nakit -= harcanacak
                pozisyonda_mi = True
                islem_gecmisi.append(
                    {'Tarih': tarih, 'Tip': 'AL (BOĞA BAŞLANGICI)', 'Fiyat': fiyat, 'Kâr/Zarar %': None})

    son_portfoy = kasa_nakit + (portfoy_varlik * closes[-1])
    net_getiri = ((son_portfoy - baslangic_kasa) / baslangic_kasa) * 100
    return net_getiri, kasa_egrisi, islem_gecmisi, son_portfoy


# -------------------------------------------------------------
# 4. STREAMLIT ARAYÜZÜ
# -------------------------------------------------------------
st.title("🧠 Nöro-Quant Laboratuvarı (Saf Makro Trend Botu)")
st.markdown(
    "**Kesin Kural:** Sadece Aylık CDLTRD yeşilken alım yapılır ve ralli sonuna kadar tutulur. Kırmızı olduğunda nakite geçilir.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Test Ayarları")
    sembol = st.text_input("Varlık", value="BTC-USD")
    gun_sayisi = st.slider("Geçmiş Kaç Gün?", 365, 2920, 2190)
    baslangic_kasa = st.number_input("Başlangıç Kasası ($)", value=10000, step=1000)

    st.markdown("---")
    st.subheader("🧬 NeuPrint Bağlantısı")
    neuprint_token = st.text_input("NeuPrint Auth Token", type="password", placeholder="Token giriniz...")

    baslat_btn = st.button("🚀 Saf Trend Testini Başlat", use_container_width=True)

with col2:
    if baslat_btn:
        with st.spinner("Piyasa verileri ve aylık makro trend analiz ediliyor..."):
            df_ham = veri_getir(sembol, gun_sayisi)

            if df_ham is None or df_ham.empty:
                st.error("Piyasa verisi çekilemedi.")
            else:
                df_ind = veri_hazirla(df_ham, malength=20)
                toplam_getiri, kasa_egrisi, islem_gecmisi, son_kasa = saf_makro_test(df_ind, baslangic_kasa)

                buy_hold = ((df_ind.iloc[-1]['Close'] - df_ind.iloc[0]['Close']) / df_ind.iloc[0]['Close']) * 100

                df_kasa = pd.DataFrame(kasa_egrisi).set_index('Tarih') if kasa_egrisi else pd.DataFrame(
                    {'Kasa': [baslangic_kasa]})
                df_islemler = pd.DataFrame(islem_gecmisi) if islem_gecmisi else pd.DataFrame(
                    columns=['Tarih', 'Tip', 'Fiyat', 'Kâr/Zarar %'])

                satislar = df_islemler[
                    df_islemler['Tip'] == 'SATIŞ (AYI SEZONU)'] if not df_islemler.empty else pd.DataFrame()

                st.subheader("📊 Saf Makro Trend Sonuç Karnesi")
                m1, m2, m3, m4 = st.columns(4)
                renk = "metric-pozitif" if toplam_getiri >= 0 else "metric-negatif"
                m1.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Nöro-Getiri</div><div class='metric-deger {renk}'>% {toplam_getiri:.1f}</div></div>",
                    unsafe_allow_html=True)
                m2.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Son Portföy</div><div class='metric-deger'>${son_kasa:,.0f}</div></div>",
                    unsafe_allow_html=True)
                m3.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Toplam İşlem</div><div class='metric-deger'>{len(df_islemler)}</div></div>",
                    unsafe_allow_html=True)
                m4.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Çıkış Sayısı</div><div class='metric-deger'>{len(satislar)}</div></div>",
                    unsafe_allow_html=True)
                st.caption(f"*Not: Aynı dönemde {sembol} al-tut getirisi **%{buy_hold:.1f}** seviyesindeydi.*")

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

                # Fiyat Mumları
                fig.add_trace(go.Candlestick(
                    x=df_ind.index, open=df_ind['Open'], high=df_ind['High'], low=df_ind['Low'], close=df_ind['Close'],
                    name='Günlük Mumlar', increasing_line_color='#3fb950', decreasing_line_color='#f85149'
                ), row=1, col=1)

                # Tek Aylık CDLTRD Çizgisi (Yeşil / Kırmızı Renklendirme)
                df_ind['CDLTRD_Next'] = df_ind['CDLTRD_1M'].shift(-1)
                for idx in range(len(df_ind) - 1):
                    x_val = [df_ind.index[idx], df_ind.index[idx + 1]]
                    y_val = [df_ind['CDLTRD_1M'].iloc[idx], df_ind['CDLTRD_Next'].iloc[idx]]
                    renk_cizgi = '#00c087' if df_ind['CDL_1M_Green'].iloc[idx] else '#ff4b4b'
                    fig.add_trace(go.Scatter(x=x_val, y=y_val, mode='lines', line=dict(color=renk_cizgi, width=3),
                                             showlegend=False), row=1, col=1)

                if not df_islemler.empty and 'Tip' in df_islemler.columns:
                    alimlar = df_islemler[df_islemler['Tip'] == 'AL (BOĞA BAŞLANGICI)']

                    if not alimlar.empty:
                        fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='Boğa-AL',
                                                 marker=dict(color='#00c087', size=12, symbol='circle')), row=1, col=1)
                    if not satislar.empty:
                        fig.add_trace(
                            go.Scatter(x=satislar['Tarih'], y=satislar['Fiyat'], mode='markers', name='Ayı-SAT',
                                       marker=dict(color='#ff4b4b', size=14, symbol='square')), row=1, col=1)

                fig.add_trace(
                    go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], mode='lines', fill='tozeroy', name='Portföy ($)',
                               line=dict(color='#00f2fe', width=2), fillcolor='rgba(0, 242, 254, 0.1)'), row=2, col=1)

                fig.update_layout(height=750, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0),
                                  hovermode="x unified", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

                if not df_islemler.empty and 'Tip' in df_islemler.columns:
                    st.subheader("📋 İşlem Logları")
                    df_gosterim = df_islemler.copy()
                    df_gosterim['Tarih'] = pd.to_datetime(df_gosterim['Tarih']).dt.strftime('%Y-%m-%d')
                    df_gosterim['Fiyat'] = df_gosterim['Fiyat'].apply(lambda x: f"${x:,.2f}")


                    def color_row(row):
                        if 'AL' in row['Tip']:
                            return ['background-color: rgba(0, 192, 135, 0.1)'] * len(row)
                        else:
                            return ['background-color: rgba(255, 75, 75, 0.1)'] * len(row)


                    st.dataframe(df_gosterim.style.apply(color_row, axis=1), use_container_width=True)