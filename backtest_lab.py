import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="MTF Strateji Laboratuvarı", page_icon="🧪", layout="wide")

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


def hma_hesapla(seri, periyot=20):
    half_length = int(periyot / 2)
    sqrt_length = int(np.sqrt(periyot))
    wma_half = wma(seri, half_length)
    wma_full = wma(seri, periyot)
    fark = 2 * wma_half - wma_full
    return wma(fark, sqrt_length)


# -------------------------------------------------------------
# BACKTEST MOTORU
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def verileri_hazirla(sembol, yil_sayisi):
    try:
        # 1. Günlük Veriyi Çek (download yerine history kullanıyoruz - MultiIndex sorununu çözer)
        ticker = yf.Ticker(sembol)
        df_d = ticker.history(period=f"{yil_sayisi}y")

        if df_d.empty: return None

        # BIST gibi yerel borsalardaki saat dilimi (timezone) çakışmalarını temizle
        if df_d.index.tz is not None:
            df_d.index = df_d.index.tz_localize(None)

        df_d = df_d.dropna(subset=['Close'])

        # 2. Haftalık ve Aylık Verileri Oluştur
        df_w = df_d.resample('W').last()
        df_m = df_d.resample('ME').last()

        # 3. Tüm Zaman Dilimlerinde HMA Hesapla
        df_d['HMA_1D'] = hma_hesapla(df_d['Close'], 20)
        df_w['HMA_1W'] = hma_hesapla(df_w['Close'], 20)
        df_m['HMA_1M'] = hma_hesapla(df_m['Close'], 20)

        # Eğilimleri (Yönü) Bul
        df_d['Trend_1D'] = df_d['HMA_1D'].diff()
        df_w['Trend_1W'] = df_w['HMA_1W'].diff()
        df_m['Trend_1M'] = df_m['HMA_1M'].diff()

        # 4. Gecikme (Lookahead Bias) Önlemi!
        df_w['Trend_1W_Shifted'] = df_w['Trend_1W'].shift(1)
        df_m['Trend_1M_Shifted'] = df_m['Trend_1M'].shift(1)

        # 5. Ana Tabloya Birleştir (İleriye dönük doldur - ffill)
        df_d = df_d.join(df_w[['Trend_1W_Shifted']], how='left').ffill()
        df_d = df_d.join(df_m[['Trend_1M_Shifted']], how='left').ffill()

        return df_d.dropna()
    except Exception:
        return None


def backtest_calistir(df, baslangic_kasa, stop_loss_yuzde, take_profit_yuzde):
    kasa = baslangic_kasa
    pozisyonda_mi = False
    giris_fiyati = 0

    islem_gecmisi = []
    kasa_egrisi = []

    for i in range(1, len(df)):
        bugun = df.iloc[i]
        dun = df.iloc[i - 1]
        tarih = df.index[i]

        # Güncel Kasa Değeri (Grafik için)
        guncel_portfoy_degeri = kasa if not pozisyonda_mi else (kasa / giris_fiyati) * bugun['Close']
        kasa_egrisi.append({'Tarih': tarih, 'Kasa': guncel_portfoy_degeri})

        if not pozisyonda_mi:
            # --- ALIM ŞARTLARI ---
            if bugun['Trend_1M_Shifted'] > 0 and bugun['Trend_1W_Shifted'] > 0:
                if bugun['Trend_1D'] > 0 and dun['Trend_1D'] <= 0:
                    pozisyonda_mi = True
                    giris_fiyati = bugun['Close']
                    stop_fiyati = giris_fiyati * (1 - stop_loss_yuzde / 100)
                    hedef_fiyat = giris_fiyati * (1 + take_profit_yuzde / 100)

                    islem_gecmisi.append({
                        'Tarih': tarih,
                        'Tip': 'AL',
                        'Fiyat': giris_fiyati,
                        'Neden': '3x MTF Taze Dönüş'
                    })
        else:
            # --- SATIM ŞARTLARI ---
            satis_nedeni = ""
            satis_fiyati = 0

            if bugun['Low'] <= stop_fiyati:
                satis_nedeni = f"🛑 Stop-Loss (-%{stop_loss_yuzde})"
                satis_fiyati = stop_fiyati

            elif bugun['High'] >= hedef_fiyat:
                satis_nedeni = f"🎯 Kâr Al (+%{take_profit_yuzde})"
                satis_fiyati = hedef_fiyat

            elif bugun['Trend_1W_Shifted'] <= 0:
                satis_nedeni = "⚠️ Haftalık Trend Bozuldu"
                satis_fiyati = bugun['Close']

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

    return df_kasa, df_islemler, kasa


# =============================================================
# ARAYÜZ
# =============================================================
st.title("🧪 MTF Strateji Laboratuvarı (Backtest)")
st.markdown(
    "Aylık ve Haftalık Hull MA yeşilken, Günlük taze dönüşte (dipten) işleme giren stratejinin geçmiş yıllardaki performansını simüle edin.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("⚙️ Test Ayarları")
    sembol = st.text_input("Test Edilecek Varlık", value="BTC-USD")
    yil_sayisi = st.slider("Geçmiş Kaç Yıl Test Edilsin?", 1, 5, 4)
    st.markdown("---")
    baslangic_kasa = st.number_input("Başlangıç Kasası ($)", value=10000, step=1000)
    stop_loss = st.number_input("🛑 Zarar Kes (Stop-Loss) %", value=7.0, step=1.0)
    take_profit = st.number_input("🎯 Kâr Al (Take-Profit) %", value=25.0, step=1.0)
    st.markdown("---")
    baslat_btn = st.button("🚀 Simülasyonu Başlat", use_container_width=True)

with col2:
    if baslat_btn:
        with st.spinner(f"{sembol} için geçmiş veriler indiriliyor ve simülasyon çalıştırılıyor..."):
            df_ana = verileri_hazirla(sembol, yil_sayisi)

            if df_ana is None or len(df_ana) < 50:
                st.error("Veri çekilemedi veya yeterli veri yok.")
            else:
                df_kasa, df_islemler, son_kasa = backtest_calistir(df_ana, baslangic_kasa, stop_loss, take_profit)

                toplam_getiri_yuzde = ((son_kasa - baslangic_kasa) / baslangic_kasa) * 100

                if not df_islemler.empty:
                    satislar = df_islemler[df_islemler['Tip'] == 'SAT']
                    toplam_islem = len(satislar)
                    basarili_islem = len(satislar[satislar['Kâr/Zarar %'] > 0])
                    win_rate = (basarili_islem / toplam_islem) * 100 if toplam_islem > 0 else 0

                    ilk_fiyat = df_ana.iloc[0]['Close']
                    son_fiyat = df_ana.iloc[-1]['Close']
                    buy_hold_getiri = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100
                else:
                    toplam_islem = 0
                    win_rate = 0
                    buy_hold_getiri = 0

                st.subheader("📊 Backtest Sonuç Karnesi")
                m1, m2, m3, m4 = st.columns(4)

                renk_sinifi = "metric-pozitif" if toplam_getiri_yuzde >= 0 else "metric-negatif"

                m1.markdown(
                    f"<div class='metric-kutu'><div class='metric-baslik'>Strateji Net Getirisi</div><div class='metric-deger {renk_sinifi}'>% {toplam_getiri_yuzde:.1f}</div></div>",
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
                    f"*Not: Eğer en başta sadece {sembol} alıp hiç dokunmasaydınız getiri **%{buy_hold_getiri:.1f}** olacaktı.*")

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

                fig.add_trace(
                    go.Scatter(x=df_ana.index, y=df_ana['Close'], name='Fiyat', line=dict(color='#8b949e', width=1)),
                    row=1, col=1)

                if not df_islemler.empty:
                    alimlar = df_islemler[df_islemler['Tip'] == 'AL']
                    satimlar = df_islemler[df_islemler['Tip'] == 'SAT']

                    fig.add_trace(go.Scatter(x=alimlar['Tarih'], y=alimlar['Fiyat'], mode='markers', name='AL (Tetik)',
                                             marker=dict(color='#00c087', size=10, symbol='triangle-up')), row=1, col=1)
                    fig.add_trace(
                        go.Scatter(x=satimlar['Tarih'], y=satimlar['Fiyat'], mode='markers', name='SAT (Çıkış)',
                                   marker=dict(color='#ff4b4b', size=10, symbol='triangle-down')), row=1, col=1)

                fig.add_trace(go.Scatter(x=df_kasa.index, y=df_kasa['Kasa'], fill='tozeroy', name='Kasa ($)',
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