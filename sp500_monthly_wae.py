import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(
    page_title="S&P 500 Dip Dönüşü & Kalite Sıralaması",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)
def sifre_kontrol():
    if "auth" not in st.session_state:
        st.session_state["auth"] = False
    if not st.session_state["auth"]:
        pwd = st.text_input("Giriş Şifresi:", type="password")
        if st.button("Giriş"):
            if pwd == "ozelSifreniz123":  # Kendi belirleyeceğiniz şifre
                st.session_state["auth"] = True
                st.rerun()
            else:
                st.error("Hatalı şifre!")
        st.stop()

sifre_kontrol()
st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    .card-box {
        background: linear-gradient(135deg, #151922 0%, #1c2331 100%);
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .badge-rank {
        background-color: #eab30822;
        color: #facc15;
        border: 1px solid #eab30888;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.95rem;
    }
    .badge-turn {
        background-color: #00c08722;
        color: #00c087;
        border: 1px solid #00c087aa;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .badge-metric {
        background-color: #1e293b;
        color: #94a3b8;
        border: 1px solid #334155;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.82rem;
        margin-right: 6px;
    }
    </style>
""", unsafe_allow_html=True)


# 1. TÜM S&P 500 LİSTESİ
@st.cache_data(ttl=86400)
def tum_sp500_sembollerini_getir():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception:
        url2 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df2 = pd.read_html(url2)[0]
        return df2['Symbol'].str.replace('.', '-', regex=False).tolist()


# 2. HULL MOVING AVERAGE (HMA 20)
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


# 3. WADDAH ATTAR EXPLOSION (WAE)
def wae_hesapla(df, fast=20, slow=40, bb_len=20, bb_mult=2.0):
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_prev = macd.shift(1)
    trend_up = np.maximum(0, (macd - macd_prev) * 150)

    bb_mid = df['Close'].rolling(bb_len).mean()
    bb_std = df['Close'].rolling(bb_len).std()
    bb_upper = bb_mid + (bb_std * bb_mult)
    bb_lower = bb_mid - (bb_std * bb_mult)
    explosion_line = bb_upper - bb_lower

    return trend_up, explosion_line


# 4. TEMEL VERİLER VE SKORLAMA BİLEŞENLERİ
@st.cache_data(ttl=43200)
def hisse_temel_metrikleri_al(ticker):
    """FCF Yield, ROE/ROIC ve İşletme Nakit Akışını çeker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        # 1. İşletme Nakit Akışı
        ocf = info.get("operatingCashflow", 0)
        if ocf is None or ocf <= 0:
            # Alternatif cashflow tablosu
            cf = t.cashflow
            if cf is not None and not cf.empty:
                for row in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                    if row in cf.index:
                        ocf = cf.loc[row].iloc[0]
                        break

        # 2. Serbest Nakit Akışı Verimi (FCF Yield)
        fcf = info.get("freeCashflow", 0)
        mcap = info.get("marketCap", 1)
        fcf_yield = (fcf / mcap * 100) if (fcf and mcap) else 0.0

        # 3. Kârlılık (ROE / ROIC)
        roe = info.get("returnOnEquity", 0)
        roe_yuzde = (roe * 100) if roe else 0.0

        sirket_adi = info.get("shortName", ticker)
        sektor = info.get("sector", "Belirtilmemiş")

        return {
            "sirket_adi": sirket_adi,
            "sektor": sektor,
            "ocf": ocf if ocf else 0,
            "fcf_yield": max(0.0, fcf_yield),
            "roe": max(0.0, roe_yuzde)
        }
    except Exception:
        return {
            "sirket_adi": ticker, "sektor": "Belirtilmemiş",
            "ocf": 0, "fcf_yield": 0.0, "roe": 0.0
        }


# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("⚙️ Tarayıcı Ayarları")
tarama_penceresi = st.sidebar.radio(
    "Hull Yeşil Dönüş Zamanı",
    options=["Sadece Bu Ay Yeşile Dönenler (En Taze)", "Son 1-2 Ay İçinde Yeşile Dönenler"],
    index=1
)

tarama_adeti = st.sidebar.select_slider(
    "Taranacak Şirket Sayısı",
    options=[50, 100, 250, "Tüm S&P 500 (503)"],
    value=100
)

st.sidebar.markdown("---")
st.sidebar.markdown("**🏆 Sıralama Ağırlıkları:**")
st.sidebar.caption("• %40 Serbest Nakit Akışı Verimi (FCF Yield)")
st.sidebar.caption("• %30 Özsermaye Kârlılığı (ROE/ROIC)")
st.sidebar.caption("• %30 Zirveden İskonto Marjı (Yukarı Potansiyel)")

baslat_butonu = st.sidebar.button("🚀 Hisseleri Bul ve Puanla", use_container_width=True)

# ==========================================
# ANA SAYFA
# ==========================================
st.title("🏆 S&P 500 Kalite Skoruna Göre Sıralı Dip Dönüşleri")
st.write(
    "Aylık Hull eğrisi yeni yeşile dönen hisseler **Nakit Verimi, Kârlılık ve İskonto Marjı** kriterlerine göre puanlanıp sıralanmıştır:")

if not baslat_butonu:
    st.info("Sol menüden kapsamı belirleyip **'Hisseleri Bul ve Puanla'** butonuna tıklayın.")
else:
    sp500_listesi = tum_sp500_sembollerini_getir()
    hedef_hisseler = sp500_listesi if tarama_adeti == "Tüm S&P 500 (503)" else sp500_listesi[:int(tarama_adeti)]

    st.write(f"🔄 **{len(hedef_hisseler)}** şirket analiz ediliyor...")

    sembol_str = " ".join(hedef_hisseler)
    veri = yf.download(
        sembol_str,
        period="5y",
        interval="1mo",
        group_by="ticker",
        auto_adjust=True,
        threads=True
    )

    aday_listesi = []
    bar = st.progress(0, text="Teknik ve nakit dönüşleri taranıyor...")
    toplam = len(hedef_hisseler)

    for idx, sym in enumerate(hedef_hisseler):
        bar.progress(int(((idx + 1) / toplam) * 100), text=f"Taranıyor: {idx + 1}/{toplam} ({sym})")
        try:
            if len(hedef_hisseler) == 1:
                df = veri.copy()
            else:
                if sym not in veri.columns.levels[0]:
                    continue
                df = veri[sym].dropna(how="all")

            if len(df) < 30:
                continue

            df = df.dropna(subset=['Close'])
            df['HMA'] = hma_hesapla(df['Close'], periyot=20)
            df['WAE_Up'], df['WAE_Line'] = wae_hesapla(df)
            df['HMA_Diff'] = df['HMA'].diff()

            son = df.iloc[-1]
            onceki = df.iloc[-2]
            iki_once = df.iloc[-3]

            bu_ay_yesile_dondu = (son['HMA_Diff'] > 0) and (onceki['HMA_Diff'] <= 0)
            gecen_ay_yesile_dondu = (son['HMA_Diff'] > 0) and (onceki['HMA_Diff'] > 0) and (iki_once['HMA_Diff'] <= 0)

            uygun_teknik = False
            durum_etiketi = ""

            if tarama_penceresi == "Sadece Bu Ay Yeşile Dönenler (En Taze)":
                if bu_ay_yesile_dondu:
                    uygun_teknik = True
                    durum_etiketi = "🟢 Bu Ay Yeni Yeşile Döndü"
            else:
                if bu_ay_yesile_dondu:
                    uygun_teknik = True
                    durum_etiketi = "🟢 Bu Ay Yeni Yeşile Döndü"
                elif gecen_ay_yesile_dondu:
                    uygun_teknik = True
                    durum_etiketi = "⚡ Geçen Ay Yeşile Döndü"

            if uygun_teknik and (son['Close'] >= son['HMA'] * 0.97):
                temel = hisse_temel_metrikleri_al(sym)

                # Sadece pozitif operasyonel nakit akışı olanlar
                if temel["ocf"] > 0:
                    zirve_5y = df['Close'].max()
                    iskonto_orani = ((zirve_5y - son['Close']) / zirve_5y) * 100.0

                    aday_listesi.append({
                        "Ticker": sym,
                        "Şirket": temel["sirket_adi"],
                        "Sektör": temel["sektor"],
                        "Son Fiyat ($)": round(son['Close'], 2),
                        "Dönüş": durum_etiketi,
                        "FCF Yield (%)": round(temel["fcf_yield"], 2),
                        "ROE (%)": round(temel["roe"], 1),
                        "Zirveden İskonto (%)": round(max(0.0, iskonto_orani), 1),
                        "Yıllık OCF ($)": temel["ocf"],
                        "df": df
                    })
        except Exception:
            continue

    bar.empty()

    if not aday_listesi:
        st.warning("Kriterlere uyan hisse bulunamadı.")
    else:
        # ==========================================
        # BİLEŞİK KALİTE SKORU HESAPLAMA (0 - 100)
        # ==========================================
        df_puan = pd.DataFrame(aday_listesi)


        # Min-Max Normalizasyon
        def normalize(col):
            if col.max() == col.min():
                return pd.Series(50, index=col.index)
            return (col - col.min()) / (col.max() - col.min()) * 100


        norm_fcf = normalize(df_puan["FCF Yield (%)"])
        norm_roe = normalize(df_puan["ROE (%)"])
        norm_iskonto = normalize(df_puan["Zirveden İskonto (%)"])

        # Ağırlıklı Puan: %40 Nakit Verimi + %30 ROE + %30 İskonto
        df_puan["Kalite Skoru"] = (norm_fcf * 0.40) + (norm_roe * 0.30) + (norm_iskonto * 0.30)
        df_puan["Kalite Skoru"] = df_puan["Kalite Skoru"].round(1)

        # Skora göre en yüksekten en düşüğe sıralama
        df_puan = df_puan.sort_values(by="Kalite Skoru", ascending=False).reset_index(drop=True)

        st.success(f"🎯 Kriterlere uyan **{len(df_puan)}** hisse bulundu ve potansiyellerine göre sıralandı!")

        # Özet Tablo
        tablo_gosterim = df_puan.drop(columns=["df", "Yıllık OCF ($)"]).copy()
        tablo_gosterim.index = tablo_gosterim.index + 1
        st.dataframe(tablo_gosterim, use_container_width=True)

        st.markdown("---")
        st.subheader("🥇 En Yüksek Puanlı İlk 5 Hisse (Detaylı Görünüm)")

        for i, row in df_puan.head(5).iterrows():
            sym = row['Ticker']
            df_plot = row['df'].tail(36)

            with st.container():
                st.markdown(f"""
                <div class="card-box">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="badge-rank">#{i + 1} SKOR: {row['Kalite Skoru']} / 100</span>
                            <span style="font-size: 1.6rem; font-weight: 800; color: #fff; margin-left: 10px;">${sym}</span>
                            <span style="font-size: 1.1rem; color: #94a3b8; margin-left: 10px;">{row['Şirket']} ({row['Sektör']})</span>
                            <span style="font-size: 1.2rem; color: #00c087; margin-left: 15px; font-weight: 700;">${row['Son Fiyat ($)']}</span>
                        </div>
                        <div>
                            <span class="badge-turn">{row['Dönüş']}</span>
                        </div>
                    </div>
                    <div style="margin-top: 10px;">
                        <span class="badge-metric">💵 FCF Verimi: %{row['FCF Yield (%)']}</span>
                        <span class="badge-metric">📈 ROE Kârlılık: %{row['ROE (%)']}</span>
                        <span class="badge-metric">🎯 Zirveden İskonto: %{row['Zirveden İskonto (%)']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_plot.index,
                    open=df_plot['Open'], high=df_plot['High'],
                    low=df_plot['Low'], close=df_plot['Close'],
                    name="Aylık Mum",
                    increasing_line_color='#00c087', decreasing_line_color='#ff4b4b'
                ))
                fig.add_trace(go.Scatter(
                    x=df_plot.index, y=df_plot['HMA'],
                    mode='lines', name='Hull MA (20)',
                    line=dict(color='#00c087', width=2.5)
                ))
                fig.update_layout(
                    height=260,
                    margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_dark",
                    xaxis_rangeslider_visible=False,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")