import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Dinamik İzleyen Stop Laboratuvarı", page_icon="📈", layout="wide")

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
def verileri_hazirla(sembol, yil_sayisi, hma_periyot):
    try:
        ticker = yf.Ticker(sembol)

        # DÜZELTME: İndikatörlerin "ısınması" için fazladan 3 yıl çekiyoruz
        isizma_payli_yil = yil_sayisi + 3
        df_d = ticker.history(period=f"{isizma_payli_yil}y")

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

        df_d = df_d.dropna()

        # DÜZELTME: Isınma verilerini çöpe at, sadece kullanıcının istediği tam net yılı filtrele
        hedef_baslangic = df_d.index[-1] - pd.DateOffset(years=yil_sayisi)
        df_d = df_d[df_d.index >= hedef_baslangic]

        return df_d
    except Exception:
        return None


# -------------------------------------------------------------
# 2. İZLEYEN STOP (TRAILING STOP) BACKTEST MOTORU
# -------------------------------------------------------------
def trailing_stop_backtest(df, baslangic_kasa, trailing_stop_orani):
    kasa = baslangic_kasa
    pozisyonda_mi = False
    giris_fiyati = 0.0
    zirve_fiyat = 0.0

    islem_gecmisi = []
    kasa_egrisi = []
    trailing_stop_cizgisi = [np.nan] * len(df)

    for i in range(1, len(df)):
        bugun = df.iloc[i]
        dun = df.iloc[i - 1]
        tarih = df.index[i]
        fiyat = bugun['Close']

        guncel_portfoy_degeri = kasa if not pozisyonda_mi else (kasa / giris_fiyati) * fiyat
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy_degeri})

        if not pozisyonda_mi:
            if bugun['Trend_1M_Shifted'] > 0 and bugun['Trend_1W_Shifted'] > 0:
                if bugun['Trend_1D'] > 0 and dun['Trend_1D'] <= 0:
                    pozisyonda_mi = True
                    giris_fiyati = fiyat
                    zirve_fiyat = fiyat

                    islem_gecmisi.append({
                        'Tarih': tarih,
                        'Tip': 'AL',
                        'Fiyat': giris_fiyati,
                        'Neden': '3x MTF Taze Dönüş'
                    })
                    trailing_stop_cizgisi[i] = zirve_fiyat * (1 - trailing_stop_orani / 100)
        else:
            if bugun['High'] > zirve_fiyat:
                zirve_fiyat = bugun['High']

            dinamik_stop_seviyesi = zirve_fiyat * (1 - trailing_stop_orani / 100)
            trailing_stop_cizgisi[i] = dinamik_stop_seviyesi

            satis_nedeni = ""
            satis_fiyati = 0.0

            if bugun['Low'] <= dinamik_stop_seviyesi:
                satis_nedeni = f"🛡️ İzleyen Stop Patladı (-%{trailing_stop_orani})"
                satis_fiyati = dinamik_stop_seviyesi
            elif bugun['Trend_1W_Shifted'] <= 0:
                satis_nedeni = "⚠️ Haftalık Trend Bozuldu (Kırmızı)"
                satis_fiyati = fiyat

            if satis_nedeni != "":
                pozisyonda_mi = False
                getiri_orani = (satis_fiyati - giris_fiyati) / giris_fiyati
                kasa = kasa * (1 + getiri_orani)

                islem_gecmisi.append({
                    'Tarih': tarih,
                    'Tip': 'SAT',
                    'Fiyat': satis_fiyati,
                    'Neden': satis_nedeni,
                    'Kâr/Zarar %': round(getiri_orani * 100, 2)
                })

    df_kasa = pd.DataFrame(kasa_egrisi).set_index('Tarih')
    df_islemler = pd.DataFrame(islem_gecmisi)
    df['Trailing_Stop'] = trailing_stop_cizgisi

    return df_kasa, df_islemler, kasa, df


# =============================================================
# 3. ARAYÜZ
# =============================================================
st.title("📈 Dinamik İzleyen Stop (Trailing Stop) Laboratuvarı")
st.markdown(
    "Bu sistemde kâr limiti yoktur. Kod; fiyat yükseldikçe stop noktanızı yukarı taşır (kârı kilitler) ve sadece fiyat zirveden sizin belirlediğiniz oranda aşağı düştüğünde satışı gerçekleştirir.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Test Ayarları")
    sembol = st.text_input("Varlık Sembolü", value="SOL-USD")
    yil_sayisi = st.slider("Geçmiş Kaç Yıl Test Edilsin?", 1, 8, 5)
    hma_periyot = st.number_input("HMA Periyodu", value=19)
    baslangic_kasa = st.number_input("Başlangıç Kasası ($)", value=10000, step=1000)
    st.markdown("---")
    trailing_stop = st.number_input("🛡️️ İzleyen Stop Oranı (%)", value=15.0, step=1.0)
    st.markdown("---")
    baslat_btn = st.button("🚀 Trailing Stop Simülasyonunu Başlat", use_container_width=True)

with col2:
    if baslat_btn:
        with st.spinner("İzleyen stop seviyeleri hesaplanıyor ve geçmişte test ediliyor..."):
            df_ham = verileri_hazirla(sembol, yil_sayisi, hma_periyot)

            if df_ham is None or len(df_ham) < 50:
                st.error("Veri çekilemedi. Bu varlık seçilen yıl kadar eski olmayabilir.")
            else:
                df_kasa, df_islemler, son_kasa, df_son = trailing_stop_backtest(df_ham, baslangic_kasa, trailing_stop)

                toplam_getiri = ((son_kasa - baslangic_kasa) / baslangic_kasa) * 100
                buy_hold_getiri = ((df_ham.iloc[-1]['Close'] - df_ham.iloc[0]['Close']) / df_ham.iloc[0]['Close']) * 100

                win_rate, toplam_islem = 0, 0
                if not df_islemler.empty:
                    satislar = df_islemler[df_islemler['Tip'] == 'SAT']
                    toplam_islem = len(satislar)
                    win_rate = (len(
                        satislar[satislar['Kâr/Zarar %'] > 0]) / toplam_islem) * 100 if toplam_islem > 0 else 0

                st.subheader("📊 İzleyen Stop Sonuç Karnesi")
                m1, m2, m3, m4 = st.columns(4)

                renk_sinifi = "metric-pozitif" if toplam_getiri >= 0 else "metric-negatif"
                m1.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Strateji Net Getirisi</div><div class='metric-deger {renk_sinifi}'>% {toplam_getiri:.1f}</div></div>",
                    unsafe_allow_html=True)
                m2.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Son Kasa Değeri</div><div class='metric-deger'>${son_kasa:,.0f}</div></div>",
                    unsafe_allow_html=True)
                m3.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Kazanma Oranı (Win Rate)</div><div class='metric-deger'>% {win_rate:.1f}</div></div>",
                    unsafe_allow_html=True)
                m4.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Toplam İşlem Sayısı</div><div class='metric-deger'>{toplam_islem}</div></div>",
                    unsafe_allow_html=True)
                st.caption(
                    f"*Not: Eğer en başta {sembol} alıp hiç dokunmasaydınız getiri **%{buy_hold_getiri:.1f}** olacaktı.*")

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

                fig.add_trace(
                    go.Scatter(x=df_son.index, y=df_son['Close'], name='Fiyat', line=dict(color='#8b949e', width=1.5)),
                    row=1, col=1)
                fig.add_trace(go.Scatter(x=df_son.index, y=df_son['Trailing_Stop'], name='İzleyen Stop Çizgisi',
                                         line=dict(color='#f59e0b', width=2, dash='dot')), row=1, col=1)

                if not df_islemler.empty:
                    alimlar = df_islemler[df_islemler['Tip'] == 'AL']
                    satimlar = df_islemler[df_islemler['Tip'] == 'SAT']
                    fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='AL Sinyali',
                                             marker=dict(color='#00c087', size=10, symbol='triangle-up')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=satimlar['Tarih'], y=satimlar['Fiyat'], mode='markers',
                                             name='SAT (Stop/Trend Bozuldu)',
                                             marker=dict(color='#ff4b4b', size=10, symbol='triangle-down')), row=1,
                                  col=1)

                fig.add_trace(go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], fill='tozeroy', name='Kasa ($)',
                                         line=dict(color='#58a6ff', width=2), fillcolor='rgba(88, 166, 255, 0.1)'),
                              row=2, col=1)

                fig.update_layout(height=650, template="plotly_dark", hovermode="x unified",
                                  margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)

                if not df_islemler.empty:
                    st.subheader("📋 İşlem Geçmişi (Log)")
                    df_gosterim = df_islemler.copy()
                    df_gosterim['Tarih'] = df_gosterim['Tarih'].dt.strftime('%Y-%m-%d')
                    df_gosterim['Fiyat'] = df_gosterim['Fiyat'].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df_gosterim, use_container_width=True)