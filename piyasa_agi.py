import streamlit as st
import yfinance as yf
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import os

st.set_page_config(page_title="Piyasa Örümcek Ağı", page_icon="🕸️", layout="wide")

# Koyu Tema Arayüz Stili
st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e6edf3; }
    h1, h2, h3 { color: #58a6ff; }
    .stAlert { background-color: #1c2331; border: 1px solid #3b4252; color: #d8dee9; }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# ÖZEL İŞTİRAK VE EKOSİSTEM SÖZLÜĞÜ (Zenginleştirilmiş Veri)
# -------------------------------------------------------------
EKOSISTEM = {
    "KCHOL.IS": ["TUPRS.IS", "FROTO.IS", "ARCLK.IS", "YKBNK.IS", "TOASO.IS", "AYGAZ.IS", "TATGD.IS"],
    "SAHOL.IS": ["AKBNK.IS", "ENJSA.IS", "CIMSA.IS", "KORDS.IS", "BRISA.IS", "AKGRT.IS"],
    "OYAKC.IS": ["HEKTS.IS", "ERBOS.IS", "ISDMR.IS", "EREGL.IS"],
    "BTC-USD": ["ETH-USD", "SOL-USD", "MSTR", "COIN", "MARA", "RIOT"],
    "ETH-USD": ["BTC-USD", "OP-USD", "ARB-USD", "LDO-USD", "UNI-USD"],
    "AAPL": ["MSFT", "GOOGL", "TSLA", "TSM", "NVDA"],
    "NVDA": ["AMD", "TSM", "INTC", "ASML", "MSFT"]
}


# -------------------------------------------------------------
# KORELASYON VE VERİ ÇEKME MOTORU
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def piyasa_verilerini_getir(merkez_varlik):
    makro_varliklar = {
        'S&P 500 (Risk İştahı)': '^GSPC',
        'Altın (Güvenli Liman)': 'GC=F',
        'Ham Petrol (Enerji/Maliyet)': 'CL=F',
        'DXY (Dolar Endeksi)': 'DX-Y.NYB'
    }

    tum_semboller = [merkez_varlik] + list(makro_varliklar.values())

    # Son 3 aylık günlük kapanış verilerini çek
    try:
        data = yf.download(tum_semboller, period="3mo", interval="1d", progress=False)['Close']
        if isinstance(data, pd.Series):
            data = data.to_frame()
        # Korelasyon matrisini hesapla
        korelasyonlar = data.corr()[merkez_varlik].to_dict()
    except Exception:
        korelasyonlar = {v: 0.0 for v in makro_varliklar.values()}

    # Şirket / Varlık Bilgisi
    try:
        info = yf.Ticker(merkez_varlik).info
        isim = info.get("shortName", merkez_varlik)
        sektor = info.get("sector", "Genel Piyasa")
        endustri = info.get("industry", "Kripto/Emtia")
    except Exception:
        isim = merkez_varlik
        sektor = "Bilinmeyen Sektör"
        endustri = "Bilinmeyen Endüstri"

    return korelasyonlar, isim, sektor, endustri, makro_varliklar


# -------------------------------------------------------------
# AĞ (NETWORK) OLUŞTURUCU
# -------------------------------------------------------------
def ag_haritasi_ciz(merkez_varlik, korelasyonlar, isim, sektor, endustri, makro_varliklar):
    # Boş bir graf (ağ) oluştur
    G = nx.Graph()

    # 1. MERKEZ DÜĞÜM (NODE)
    G.add_node(merkez_varlik, label=isim, title=f"Hedef Varlık:\n{isim}", color="#ff0055", size=60, shape="hexagon")

    # 2. SEKTÖR VE ENDÜSTRİ DÜĞÜMLERİ
    G.add_node(sektor, label=sektor, title="Sektör", color="#d4a373", size=30)
    G.add_node(endustri, label=endustri, title="Endüstri Sınıfı", color="#faedcd", size=25)

    G.add_edge(merkez_varlik, sektor, value=2, title="Bağlı Olduğu Sektör", color="#5c6b73")
    G.add_edge(sektor, endustri, value=1, title="Alt Endüstri", color="#5c6b73")

    # 3. İŞTİRAKLER / EKOSİSTEM (Rakipler veya alt şirketler)
    iştirakler = EKOSISTEM.get(merkez_varlik.upper(), [f"{sektor} Rakip 1", f"{sektor} Rakip 2", f"{sektor} Rakip 3"])

    for iştirak in iştirakler:
        G.add_node(iştirak, label=iştirak, title="Ekosistem / Rakip", color="#4cc9f0", size=20)
        G.add_edge(merkez_varlik, iştirak, value=3, title="Doğrudan Bağlantı / Rakip", color="#4cc9f0")

    # 4. MAKRO EKONOMİK KORELASYON DÜĞÜMLERİ
    for makro_isim, makro_kod in makro_varliklar.items():
        kor_deger = korelasyonlar.get(makro_kod, 0)
        if pd.isna(kor_deger):
            kor_deger = 0

        # Rengi ve kalınlığı korelasyona göre belirle (Pozitif: Yeşil, Negatif: Kırmızı, Nötr: Gri)
        if kor_deger >= 0.3:
            edge_color = "#00c087"  # Pozitif korelasyon (Yeşil)
            node_color = "#00c087"
        elif kor_deger <= -0.3:
            edge_color = "#ff4b4b"  # Negatif korelasyon (Kırmızı)
            node_color = "#ff4b4b"
        else:
            edge_color = "#6c757d"  # Nötr
            node_color = "#ced4da"

        G.add_node(makro_kod, label=makro_isim, title=f"Son 3 Ay Korelasyon: %{kor_deger * 100:.1f}", color=node_color,
                   size=35)
        # Çizgi kalınlığını mutlak korelasyona göre artır
        G.add_edge(merkez_varlik, makro_kod, value=abs(kor_deger) * 10 + 1, title=f"Korelasyon: {kor_deger:.2f}",
                   color=edge_color)

    # PyVis Ağına Dönüştür (Karanlık mod ve fizik motoru ayarları)
    net = Network(height="650px", width="100%", bgcolor="#0d1117", font_color="#e6edf3", directed=False)
    net.from_nx(G)

    # HATA DÜZELTİLDİ: Stabil çalışan Repulsion (İtme) fiziği kullanıldı
    net.repulsion(node_distance=150, central_gravity=0.05, spring_length=150, spring_strength=0.05, damping=0.8)

    # HTML dosyası olarak kaydet
    dosya_adi = "piyasa_orcek_agi.html"
    net.save_graph(dosya_adi)
    return dosya_adi


# =============================================================
# STREAMLIT ARAYÜZÜ
# =============================================================
st.title("🕸️ Piyasa Örümcek Ağı (Etkileşimli Dedektif Paneli)")
st.markdown(
    "Bir varlığın tüm ekosistemini, rakiplerini ve küresel makro verilerle olan gizli korelasyonlarını görselleştirin. Düğümleri (topları) farenizle sürükleyebilir, tekerlekle yakınlaşabilirsiniz.")

col1, col2 = st.columns([1, 4])

with col1:
    st.subheader("Dedektif Terminali")
    hedef_varlik = st.text_input("Hedef Varlık (Örn: KCHOL.IS, BTC-USD, NVDA)", value="KCHOL.IS").upper().strip()

    baslat = st.button("🔍 Ağı Oluştur", use_container_width=True)

    st.markdown("---")
    st.markdown("**Ağ Efsanesi (Legend):**")
    st.markdown("🔴 Merkez Varlık")
    st.markdown("🔵 İştirakler / Rakipler")
    st.markdown("🟢 Pozitif Korelasyon")
    st.markdown("🖍️ Negatif Korelasyon")

with col2:
    if baslat:
        with st.spinner("Küresel piyasa bağlantıları ve korelasyonlar hesaplanıyor..."):
            # 1. Verileri Çek
            korelasyonlar, isim, sektor, endustri, makro_varliklar = piyasa_verilerini_getir(hedef_varlik)

            # 2. Ağı Çiz ve HTML Dosyasını Al
            html_dosya = ag_haritasi_ciz(hedef_varlik, korelasyonlar, isim, sektor, endustri, makro_varliklar)

            # 3. Streamlit içinde HTML'i render et
            with open(html_dosya, 'r', encoding='utf-8') as f:
                html_source = f.read()

            components.html(html_source, height=670, scrolling=False)

            # Geçici dosyayı temizle
            try:
                os.remove(html_dosya)
            except:
                pass
    else:
        st.info("Sol menüden bir varlık seçip 'Ağı Oluştur' butonuna basın.")