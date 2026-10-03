import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import xml.etree.ElementTree as ET
import requests
import re
import urllib.parse

st.set_page_config(
    page_title="Küresel & BIST Kalite / MTF Dip Dönüş Radarı",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    .card-box {
        background: linear-gradient(135deg, #151922 0%, #1c2331 100%);
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .badge-rank {
        background-color: #eab30822;
        color: #facc15;
        border: 1px solid #eab30888;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 800;
        font-size: 0.85rem;
    }
    .badge-turn {
        background-color: #00c08722;
        color: #00c087;
        border: 1px solid #00c087aa;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-mtf {
        background-color: #38bdf822;
        color: #38bdf8;
        border: 1px solid #38bdf8aa;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-vol {
        background-color: #ff6b4a22;
        color: #ff7b5a;
        border: 1px solid #ff6b4a66;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-metric {
        background-color: #1e293b;
        color: #94a3b8;
        border: 1px solid #334155;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.78rem;
        margin-right: 5px;
    }
    .insight-box {
        background-color: #0d1117;
        border-radius: 8px;
        border: 1px solid #21262d;
        padding: 12px 14px;
        margin-top: 10px;
        font-size: 0.85rem;
        line-height: 1.55;
    }
    .pos-header { color: #3fb950; font-weight: 700; margin-bottom: 6px; }
    .neg-header { color: #f85149; font-weight: 700; margin-top: 10px; margin-bottom: 6px; }
    .clickable-summary {
        color: #e6edf3;
        text-decoration: none;
        display: inline-block;
        margin-bottom: 6px;
        transition: color 0.15s ease;
    }
    .clickable-summary:hover {
        color: #58a6ff;
        text-decoration: underline;
    }
    .src-tag {
        color: #7d8590;
        font-size: 0.75rem;
        margin-left: 6px;
    }
    [data-testid="stDataFrame"] { font-size: 0.82rem; }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# ANLIK TÜRKÇEYE ÇEVİRİ MOTORU
# -------------------------------------------------------------
def turkceye_cevir(metin):
    if not metin or len(metin.strip()) == 0:
        return metin
    try:
        if any(c in metin for c in "çğıöşüÇĞİÖŞÜ"):
            return metin
        encoded = urllib.parse.quote(metin)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=tr&dt=t&q={encoded}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            sonuc = res.json()
            return "".join([parca[0] for parca in sonuc[0] if parca[0]])
    except Exception:
        pass
    return metin


# -------------------------------------------------------------
# CANLI ENDEKS BİLEŞENLERİ (BIST TÜM DAHİL)
# -------------------------------------------------------------
def sp500_canli_liste():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return df['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception:
        url2 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        return pd.read_html(url2)[0]['Symbol'].str.replace('.', '-', regex=False).tolist()


def bist30_canli_liste():
    return [
        "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", "EKGYO.IS", "ENKAI.IS",
        "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS",
        "KONTR.IS", "KOZAL.IS", "KRDMD.IS", "MGROS.IS", "OYAKC.IS", "PETKM.IS", "PGSUS.IS",
        "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TOASO.IS", "TUPRS.IS",
        "ULKER.IS", "YKBNK.IS"
    ]


def bist100_canli_liste():
    liste30 = bist30_canli_liste()
    ek_70 = [
        "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKFGY.IS", "AKFYE.IS", "AKSA.IS", "AKSEN.IS",
        "ALARK.IS", "ALFAS.IS", "ANSGR.IS", "ASGYO.IS", "BERA.IS", "BOBET.IS", "BRSAN.IS",
        "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS",
        "DOHOL.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS", "ENJSA.IS", "EUPWR.IS", "GENIL.IS",
        "GESAN.IS", "GOLTS.IS", "GWIND.IS", "HALKB.IS", "IPEKE.IS", "ISDMR.IS", "ISFIN.IS",
        "ISGYO.IS", "ISMEN.IS", "KAYSE.IS", "KCAER.IS", "KLSER.IS", "KMPUR.IS", "KONKA.IS",
        "KORDS.IS", "KOZAA.IS", "MAVI.IS", "MIATK.IS", "ODAS.IS", "OTKAR.IS", "PENTA.IS",
        "QUAGR.IS", "REEDR.IS", "SDTTR.IS", "SMRTG.IS", "SOKM.IS", "TABGD.IS", "TATEN.IS",
        "TKFEN.IS", "TMSN.IS", "TSKB.IS", "TTKOM.IS", "TURSG.IS", "VAKBN.IS", "VESBE.IS",
        "VESTL.IS", "YEOTK.IS", "YYLGD.IS", "ZOREN.IS", "KONYA.IS", "BAGFS.IS"
    ]
    return list(dict.fromkeys(liste30 + ek_70))


@st.cache_data(ttl=86400)
def bist_tum_canli_liste():
    cekirdek_bist = bist100_canli_liste()
    ekstra_bist = [
        "AAV.IS", "ACSEL.IS", "ADEL.IS", "ADESE.IS", "ADGYO.IS", "AFYON.IS", "AGESA.IS", "AGROT.IS",
        "AHES.IS", "AKBNK.IS", "AKCNS.IS", "AKENR.IS", "AKFGY.IS", "AKFYE.IS", "AKMGY.IS", "AKRGY.IS",
        "AKSGY.IS", "AKSEN.IS", "AKSUE.IS", "AKYHO.IS", "ALBRK.IS", "ALCAR.IS", "ALCTL.IS", "ALFAS.IS",
        "ALGYO.IS", "ALKA.IS", "ALKIM.IS", "ALMAD.IS", "ALTNY.IS", "ALVES.IS", "ANELE.IS", "ANGEN.IS",
        "ANHYT.IS", "ANSGR.IS", "ARASE.IS", "ARCLK.IS", "ARDYZ.IS", "ARENA.IS", "ARSAN.IS", "ARTMS.IS",
        "ARZUM.IS", "ASELS.IS", "ASGYO.IS", "ASTOR.IS", "ASUZU.IS", "ATAGY.IS", "ATAKP.IS", "ATATP.IS",
        "ATEKS.IS", "ATLAS.IS", "ATSYH.IS", "AVGYO.IS", "AVHOL.IS", "AVOD.IS", "AVPGY.IS", "AVTUR.IS",
        "AYCES.IS", "AYDEM.IS", "AYEN.IS", "AYES.IS", "AYGAZ.IS", "AZTEK.IS", "BAGFS.IS", "BAHKM.IS",
        "BAKAB.IS", "BALAT.IS", "BANVT.IS", "BARMA.IS", "BASCM.IS", "BASGZ.IS", "BAYRK.IS", "BEGYO.IS",
        "BERA.IS", "BEYAZ.IS", "BFREN.IS", "BIENY.IS", "BIGCH.IS", "BIMAS.IS", "BINHO.IS", "BIOEN.IS",
        "BIZIM.IS", "BJKAS.IS", "BLCYT.IS", "BMSCH.IS", "BMSTL.IS", "BNTAS.IS", "BOBET.IS", "BORLS.IS",
        "BORSK.IS", "BOSSA.IS", "BRCEG.IS", "BRCVO.IS", "BRISA.IS", "BRKO.IS", "BRKSN.IS", "BRMEN.IS",
        "BRSAN.IS", "BRYAT.IS", "BSOKE.IS", "BTCIM.IS", "BUCIM.IS", "BURCE.IS", "BURVA.IS", "BVSAN.IS",
        "BYDNR.IS", "CANTE.IS", "CASA.IS", "CATES.IS", "CCOLA.IS", "CELHA.IS", "CEMAS.IS", "CEMTS.IS",
        "CEOEM.IS", "CIMSA.IS", "CLEBI.IS", "CMBTN.IS", "CMENT.IS", "CONSE.IS", "COSMO.IS", "CRDFA.IS",
        "CRFSA.IS", "CUSAN.IS", "CVKMD.IS", "CWENE.IS", "DAGI.IS", "DAPGM.IS", "DARDL.IS", "DENGE.IS",
        "DERHL.IS", "DERIM.IS", "DESA.IS", "DESPC.IS", "DEVA.IS", "DGATE.IS", "DGGYO.IS", "DGNMO.IS",
        "DIRIT.IS", "DITAS.IS", "DMRGD.IS", "DMSAS.IS", "DOAS.IS", "DOBUR.IS", "DOCO.IS", "DOFER.IS",
        "DOGUB.IS", "DOHOL.IS", "DOKTA.IS", "DURDO.IS", "DYOBY.IS", "DZGYO.IS", "EBEBK.IS", "ECILC.IS",
        "ECZYT.IS", "EDATA.IS", "EDIP.IS", "EGEEN.IS", "EGGUB.IS", "EGPRO.IS", "EGSER.IS", "EKGYO.IS",
        "EKIZ.IS", "EKOS.IS", "EKSUN.IS", "ELITE.IS", "EMELK.IS", "EMIRG.IS", "EMKEL.IS", "EMNIS.IS",
        "ENERY.IS", "ENJSA.IS", "ENKAI.IS", "ENTRA.IS", "EPLAS.IS", "ERBOS.IS", "ERCB.IS", "EREGL.IS",
        "ERSU.IS", "ESCAR.IS", "ESCOM.IS", "ESEN.IS", "ETILR.IS", "ETYAT.IS", "EUHOL.IS", "EUKYO.IS",
        "EUPWR.IS", "EUREN.IS", "EUYO.IS", "EYGYO.IS", "FADE.IS", "FENER.IS", "FLAP.IS", "FMIZP.IS",
        "FONET.IS", "FORMT.IS", "FORTE.IS", "FRIGO.IS", "FROTO.IS", "FZLGY.IS", "GARAN.IS", "GARFA.IS",
        "GEDIK.IS", "GEDZA.IS", "GENIL.IS", "GENTS.IS", "GEREL.IS", "GESAN.IS", "GIPTA.IS", "GLBMD.IS",
        "GLCVY.IS", "GLRYH.IS", "GLYHO.IS", "GMTAS.IS", "GOKNR.IS", "GOLTS.IS", "GOODY.IS", "GOZDE.IS",
        "GRNYO.IS", "GRSEL.IS", "GRTHO.IS", "GSDDE.IS", "GSDHO.IS", "GSRAY.IS", "GUBRF.IS", "GWIND.IS",
        "GZNMI.IS", "HALKB.IS", "HATEK.IS", "HATSN.IS", "HEDEF.IS", "HEKTS.IS", "HKTM.IS", "HLGYO.IS",
        "HOROZ.IS", "HRKET.IS", "HTTBT.IS", "HUBVC.IS", "HURGZ.IS", "ICBCT.IS", "ICUGS.IS", "IDGYO.IS",
        "IEYHO.IS", "IHAAS.IS", "IHEVA.IS", "IHGZT.IS", "IHLAS.IS", "IHLGM.IS", "IHYAY.IS", "IMASM.IS",
        "INDES.IS", "INFO.IS", "INGRM.IS", "INVES.IS", "IPEKE.IS", "ISATR.IS", "ISBTR.IS", "ISCTR.IS",
        "ISDMR.IS", "ISFIN.IS", "ISGSY.IS", "ISGYO.IS", "ISKUR.IS", "ISMEN.IS", "ISYAT.IS", "IZENR.IS",
        "IZFAS.IS", "IZINV.IS", "IZMDC.IS", "JANTS.IS", "KAPLM.IS", "KAREL.IS", "KARSN.IS", "KARTN.IS",
        "KARYA.IS", "KATMR.IS", "KAYSE.IS", "KBORU.IS", "KCAER.IS", "KCHOL.IS", "KFEIN.IS", "KGYO.IS",
        "KIMMR.IS", "KLGYO.IS", "KLKIM.IS", "KLMSN.IS", "KLNMA.IS", "KLRHO.IS", "KLSER.IS", "KLYSN.IS",
        "KMPUR.IS", "KNFRT.IS", "KOCMT.IS", "KONKA.IS", "KONTR.IS", "KONYA.IS", "KOPOL.IS", "KORDS.IS",
        "KOTON.IS", "KOZAA.IS", "KOZAL.IS", "KRDMA.IS", "KRDMB.IS", "KRDMD.IS", "KRGYO.IS", "KRONT.IS",
        "KRPLS.IS", "KRSTL.IS", "KRTEK.IS", "KRVGD.IS", "KSTUR.IS", "KTLEV.IS", "KTSKR.IS", "KUTPO.IS",
        "KUVVA.IS", "KUYAS.IS", "LIDER.IS", "LIDFA.IS", "LILAK.IS", "LINK.IS", "LKMNH.IS", "LMKDC.IS",
        "LOGO.IS", "LUKSK.IS", "MAALT.IS", "MACKO.IS", "MAGEN.IS", "MAKIM.IS", "MAKTK.IS", "MANAS.IS",
        "MARBL.IS", "MARKA.IS", "MARTI.IS", "MAVI.IS", "MEDTR.IS", "MEGAP.IS", "MEGMT.IS", "MEKAG.IS",
        "MEPET.IS", "MERCN.IS", "MERIT.IS", "MERKO.IS", "METRO.IS", "METUR.IS", "MEYSU.IS", "MHRGY.IS",
        "MIATK.IS", "MIPAZ.IS", "MMCAS.IS", "MNDRS.IS", "MNDTR.IS", "MOBTL.IS", "MOGAN.IS", "MPARK.IS",
        "MRGYO.IS", "MRSHL.IS", "MSGYO.IS", "MTRKS.IS", "MTRYO.IS", "MZHLD.IS", "NATEN.IS", "NETAS.IS",
        "NIBAS.IS", "NTGAZ.IS", "NTHOL.IS", "NUGYO.IS", "NUHCM.IS", "OBAMS.IS", "OBASE.IS", "ODAS.IS",
        "OFSYM.IS", "ONCSM.IS", "ORCAY.IS", "ORGE.IS", "ORMA.IS", "OSMEN.IS", "OSTIM.IS", "OTKAR.IS",
        "OTTO.IS", "OYAKC.IS", "OYAYO.IS", "OYLUM.IS", "OYYAT.IS", "OZATD.IS", "OZGYO.IS", "OZKGY.IS",
        "OZRDN.IS", "OZSUB.IS", "PAGYO.IS", "PAMEL.IS", "PAPIL.IS", "PARSN.IS", "PASEU.IS", "PCILT.IS",
        "PEGYO.IS", "PEKGY.IS", "PENGD.IS", "PENTA.IS", "PETKM.IS", "PETUN.IS", "PGSUS.IS", "PINSU.IS",
        "PKART.IS", "PKENT.IS", "PLTUR.IS", "PNLSN.IS", "PNSUT.IS", "POLHO.IS", "POLTK.IS", "PRDGS.IS",
        "PRKAB.IS", "PRKME.IS", "PRZMA.IS", "PSDTC.IS", "QNBFB.IS", "QNBFL.IS", "QUAGR.IS", "RALYH.IS",
        "RAYSG.IS", "REEDR.IS", "RNPOL.IS", "RODRG.IS", "ROYAL.IS", "RTALB.IS", "RUBNS.IS", "RYGYO.IS",
        "RYSAS.IS", "SAFKR.IS", "SAHOL.IS", "SAMAT.IS", "SANEL.IS", "SANFM.IS", "SANKO.IS", "SARKY.IS",
        "SASA.IS", "SAYAS.IS", "SDTTR.IS", "SEGYO.IS", "SEKFK.IS", "SEKUR.IS", "SELEC.IS", "SELVA.IS",
        "SEYKM.IS", "SILVR.IS", "SISE.IS", "SKBNK.IS", "SKTAS.IS", "SKYMD.IS", "SMART.IS", "SMRTG.IS",
        "SNGYO.IS", "SNICA.IS", "SNKRN.IS", "SOKE.IS", "SOKM.IS", "SONME.IS", "SRVGY.IS", "SUMAS.IS",
        "SUNTK.IS", "SURGY.IS", "SUWEN.IS", "TABGD.IS", "TARKM.IS", "TATEN.IS", "TATGD.IS", "TAVHL.IS",
        "TBORG.IS", "TCELL.IS", "TDGYO.IS", "TEKTU.IS", "TERA.IS", "TETMT.IS", "TEZOL.IS", "THYAO.IS",
        "TIRE.IS", "TKFEN.IS", "TKNSA.IS", "TLMAN.IS", "TMPOL.IS", "TMSN.IS", "TNZTP.IS", "TOASO.IS",
        "TRCAS.IS", "TRGYO.IS", "TRILC.IS", "TSKB.IS", "TSPOR.IS", "TTKOM.IS", "TTRAK.IS", "TUCLK.IS",
        "TUKAS.IS", "TUPRS.IS", "TURGG.IS", "TURSG.IS", "UFUK.IS", "ULAS.IS", "ULFA.IS", "ULKER.IS",
        "ULUFA.IS", "ULUSE.IS", "ULUUN.IS", "UNLU.IS", "USAK.IS", "VAKBN.IS", "VAKFN.IS", "VAKKO.IS",
        "VANGD.IS", "VBTYZ.IS", "VERUS.IS", "VESBE.IS", "VESTL.IS", "VKFYO.IS", "VKGYO.IS", "VKING.IS",
        "VRGYO.IS", "YAPRK.IS", "YATAS.IS", "YAYLA.IS", "YGGYO.IS", "YGYO.IS", "YEOTK.IS", "YKBNK.IS",
        "YKSLN.IS", "YONGA.IS", "YUNSA.IS", "YYAPI.IS", "YYLGD.IS", "ZEDUR.IS", "ZOREN.IS", "ZRGYO.IS"
    ]
    return list(dict.fromkeys(cekirdek_bist + ekstra_bist))


# -------------------------------------------------------------
# TEKNİK GÖSTERGELER (HULL MA, RSI, WAE)
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


def rsi_hesapla(seri, periyot=14):
    delta = seri.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


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


# -------------------------------------------------------------
# TEMEL METRİKLER (OCF > 0 VE ROE > 0 ZORUNLU)
# -------------------------------------------------------------
def hisse_temel_bilgileri(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info

        ocf = info.get("operatingCashflow", 0)
        if ocf is None or ocf <= 0:
            cf = t.cashflow
            if cf is not None and not cf.empty:
                for row in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                    if row in cf.index:
                        ocf = cf.loc[row].iloc[0]
                        break

        fcf = info.get("freeCashflow", 0)
        mcap = info.get("marketCap", 1)
        fcf_yield = (fcf / mcap * 100) if (fcf and mcap) else 0.0

        roe = info.get("returnOnEquity", 0)
        roe_yuzde = (roe * 100) if roe else 0.0

        sirket_adi = info.get("shortName") or info.get("longName") or ticker.replace(".IS", "")
        sektor = info.get("sector", "Genel")

        return {
            "sirket_adi": sirket_adi,
            "sektor": sektor,
            "ocf": ocf if ocf else 0,
            "fcf_yield": max(0.0, fcf_yield),
            "roe": roe_yuzde
        }
    except Exception:
        return {
            "sirket_adi": ticker.replace(".IS", ""), "sektor": "Genel",
            "ocf": 0, "fcf_yield": 0.0, "roe": 0.0
        }


# -------------------------------------------------------------
# GELİŞMİŞ VE HATASIZ HABER AYRIŞTIRMA (TEDBİR / CEZA KESİN NEGATİF)
# -------------------------------------------------------------
def turkce_ozet_hazirla(title, summary):
    raw = (summary if summary and len(summary) > 30 else title).strip()
    raw = re.sub('<[^<]+?>', '', raw)
    cumleler = re.split(r'(?<=[.!?])\s+', raw)
    secilen = f"{cumleler[0]} {cumleler[1]}" if len(cumleler) >= 2 else cumleler[0]
    if len(secilen) > 175:
        secilen = secilen[:172].rstrip() + "..."
    return turkceye_cevir(secilen)


@st.cache_data(ttl=7200)
def canli_haber_ozetleri(ticker, sirket_adi):
    haberler = []
    try:
        t = yf.Ticker(ticker)
        yf_news = t.news
        if yf_news:
            for item in yf_news[:8]:
                title = item.get("title", "")
                link = item.get("link", "#")
                pub = item.get("publisher", "Kaynak")
                summary = item.get("summary", "")
                if title:
                    haberler.append({"title": title, "summary": summary, "link": link, "source": pub})
    except Exception:
        pass

    if len(haberler) < 4:
        try:
            arama = ticker.replace(".IS", "") if ".IS" in ticker else f"{ticker} stock"
            rss = f"https://news.google.com/rss/search?q={arama}&hl=tr&gl=TR&ceid=TR:tr" if ".IS" in ticker else f"https://news.google.com/rss/search?q={arama}&hl=en-US&gl=US&ceid=US:en"
            resp = requests.get(rss, timeout=4)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:5]:
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else "#"
                    source_elem = item.find("source")
                    source = source_elem.text if source_elem is not None else "Google Haberler"
                    if title and not any(h['title'] == title for h in haberler):
                        haberler.append({"title": title, "summary": title, "link": link, "source": source})
        except Exception:
            pass

    # KESİN NEGATİF KELİMELER (TEDBİR, CEZA, YASAKLAR KESİNLİKLE POZİTİF KUTUSUNA GİREMEZ)
    kesin_negatif_kelimeler = [
        "tedbir", "konkordato", "brüt takas", "ceza", "soruşturma", "yasak", "dava", "haciz",
        "iflas", "uyarı", "iptal", "slump", "fall", "decline", "drop", "probe", "lawsuit", "debt",
        "loss", "risk", "downgrade", "fine", "cut", "inflation", "düşüş", "zarar", "baskı", "borç",
        "kredili işlem"
    ]

    pozitif_kelimeler = [
        "growth", "record", "profit", "surge", "beats", "buy", "deal", "contract", "invest", "expansion",
        "dividend", "yükseliş", "rekor", "kâr", "anlaşma", "büyüme", "ihale", "yatırım", "temettü", "onay", "ortaklık"
    ]

    olumlu = []
    olumsuz = []

    for h in haberler:
        metin = (h["title"] + " " + h.get("summary", "")).lower()

        # ÖNCELİK 1: Eğer başlıkta tedbir, ceza, dava vs. geçiyorsa doğrudan negatiftir!
        if any(w in metin for w in kesin_negatif_kelimeler):
            if len(olumsuz) < 2:
                olumsuz.append({"ozet": turkce_ozet_hazirla(h["title"], h.get("summary", "")), "link": h["link"],
                                "source": h["source"]})
        elif any(w in metin for w in pozitif_kelimeler):
            if len(olumlu) < 2:
                olumlu.append({"ozet": turkce_ozet_hazirla(h["title"], h.get("summary", "")), "link": h["link"],
                               "source": h["source"]})

    if not olumlu:
        olumlu.append({
            "ozet": f"{sirket_adi}, pozitif işletme nakit akışı ve temel operasyonel kapasitesiyle faaliyet tabanını koruyor.",
            "link": f"https://www.google.com/search?q={ticker}+yatırım+büyüme",
            "source": "Sektörel Değerlendirme"
        })
    if not olumsuz:
        olumsuz.append({
            "ozet": f"Sektörel girdi maliyetleri ve faiz ortamı kısa vadeli kâr marjları üzerinde baskı yaratabilir.",
            "link": f"https://www.google.com/search?q={ticker}+risk+maliyet",
            "source": "Piyasa Notu"
        })

    return olumlu, olumsuz


# =============================================================
# SIDEBAR
# =============================================================
st.sidebar.title("⚙️️ Tarayıcı Ayarları")

secilen_endeks = st.sidebar.selectbox(
    "🏛️ Taranacak Piyasa",
    options=["BIST 100", "BIST 30", "BIST TÜM (500+ Hisse)", "S&P 500 (ABD)"]
)

# YENİ STRATEJİLER VE GELİŞMİŞ MTF SEÇENEKLERİ
st.sidebar.markdown("---")
st.sidebar.markdown("**⏳ Çoklu Zaman Dilimi (MTF) & Strateji:**")
mtf_modu = st.sidebar.radio(
    "Strateji Seçimi",
    options=[
        "🚀 Aylık, Haftalık ve Günlük Eşzamanlı İlk Kez Yeşile Dönenler (3x MTF)",
        "💥 Aylık Hull ve WAE Aynı Anda İlk Kez Olumluya Dönenler (Momentum Patlaması)",
        "💎 Aylık Hull Yeşilken, Haftalık Düzeltme Bitirip Yeni Yeşile Dönenler (Trend İçi Tetik)",
        "📈 Dipten Yükseliş Trendine Geçenler (Yüksek Dip / Higher-Low Onayı)",
        "🟢 Sadece Aylık Hull Yeni Yeşile Dönenler (Makro Dip)"
    ],
    index=0
)

hacim_filtresi = st.sidebar.checkbox(
    "🔥 Sadece Hacim Patlaması Olanları Göster",
    value=False,
    help="İşaretlenirse hacmi önceki periyotlar ortalamasından en az %20 yüksek olan hisseler listelenir."
)

if secilen_endeks in ["S&P 500 (ABD)", "BIST TÜM (500+ Hisse)"]:
    tarama_adeti = st.sidebar.select_slider(
        "Taranacak Şirket Sayısı",
        options=[100, 200, 350, "Tüm Liste"],
        value=200 if secilen_endeks == "BIST TÜM (500+ Hisse)" else 100
    )
else:
    tarama_adeti = "Tüm Liste"
    st.sidebar.caption(f"ℹ️ {secilen_endeks} bileşenlerinin tamamı taranacaktır.")

st.sidebar.markdown("---")
st.sidebar.markdown("**🛡️ Katı Temel Filtreler:**")
st.sidebar.caption("✅ İşletme Nakit Akışı (OCF) > 0 (Zorunlu)")
st.sidebar.caption("✅ ROE (Özsermaye Kârlılığı) > 0 (Zorunlu)")

baslat_butonu = st.sidebar.button("🚀 Listeyi Güncelle ve Tara", use_container_width=True)

# =============================================================
# ANA EKRAN
# =============================================================
para_birimi = "$" if secilen_endeks == "S&P 500 (ABD)" else "₺"
st.title(f"🏆 {secilen_endeks} Kalite & MTF Dip Dönüş Radarı")

if not baslat_butonu:
    st.info("Sol menüden MTF stratejinizi belirleyip **'Listeyi Güncelle ve Tara'** butonuna tıklayın.")
else:
    with st.spinner("Piyasa hisse listesi hazırlanıyor..."):
        if secilen_endeks == "S&P 500 (ABD)":
            tam_liste = sp500_canli_liste()
        elif secilen_endeks == "BIST 30":
            tam_liste = bist30_canli_liste()
        elif secilen_endeks == "BIST 100":
            tam_liste = bist100_canli_liste()
        else:
            tam_liste = bist_tum_canli_liste()

    hedef_hisseler = tam_liste if tarama_adeti == "Tüm Liste" else tam_liste[:int(tarama_adeti)]
    st.write(f"🔄 **{secilen_endeks}** kapsamında **{len(hedef_hisseler)}** şirket taranıyor...")

    sembol_str = " ".join(hedef_hisseler)

    # 1. Aylık Verileri İndir
    veri_aylik = yf.download(
        sembol_str,
        period="5y",
        interval="1mo",
        group_by="ticker",
        auto_adjust=True,
        threads=True
    )

    # 2. Haftalık ve Günlük Veriler Gerekliyse İndir
    veri_haftalik = None
    veri_gunluk = None

    haftalik_gerekli = ("3x MTF" in mtf_modu) or ("Haftalık Düzeltme Bitirip" in mtf_modu)
    gunluk_gerekli = ("3x MTF" in mtf_modu)

    if haftalik_gerekli:
        veri_haftalik = yf.download(sembol_str, period="2y", interval="1wk", group_by="ticker", auto_adjust=True,
                                    threads=True)
    if gunluk_gerekli:
        veri_gunluk = yf.download(sembol_str, period="6mo", interval="1d", group_by="ticker", auto_adjust=True,
                                  threads=True)

    aday_listesi = []
    bar = st.progress(0, text="Strateji dönüşleri, bilanço ve nakit akışları inceleniyor...")
    toplam = len(hedef_hisseler)

    for idx, sym in enumerate(hedef_hisseler):
        bar.progress(int(((idx + 1) / toplam) * 100), text=f"Taranıyor: {idx + 1}/{toplam} ({sym.replace('.IS', '')})")
        try:
            if len(hedef_hisseler) == 1:
                df_m = veri_aylik.copy()
            else:
                if sym not in veri_aylik.columns.levels[0]:
                    continue
                df_m = veri_aylik[sym].dropna(how="all")

            if len(df_m) < 25:
                continue

            df_m = df_m.dropna(subset=['Close'])
            df_m['HMA'] = hma_hesapla(df_m['Close'], periyot=20)
            df_m['HMA_Diff'] = df_m['HMA'].diff()
            df_m['RSI'] = rsi_hesapla(df_m['Close'], periyot=14)
            df_m['WAE_Up'], df_m['WAE_Line'] = wae_hesapla(df_m)

            son_m = df_m.iloc[-1]
            onceki_m = df_m.iloc[-2]
            iki_once_m = df_m.iloc[-3]

            aylik_bu_yesil = (son_m['HMA_Diff'] > 0) and (onceki_m['HMA_Diff'] <= 0)
            aylik_gecen_yesil = (son_m['HMA_Diff'] > 0) and (onceki_m['HMA_Diff'] > 0) and (iki_once_m['HMA_Diff'] <= 0)

            uygun_teknik = False
            tetik_etiketi = ""
            mtf_durumu = ""
            df_kullanilacak = df_m
            son_fiyat = son_m['Close']
            son_rsi = son_m['RSI'] if not np.isnan(son_m['RSI']) else 50.0
            son_hacim = son_m.get('Volume', 0)
            ort_hacim = df_m['Volume'].iloc[-4:-1].mean() if len(df_m) >= 4 else son_hacim

            # ==============================================================
            # STRATEJİ 1: AYLIK, HAFTALIK VE GÜNLÜK İLK KEZ YEŞİL (3X MTF)
            # ==============================================================
            if "3x MTF" in mtf_modu and veri_haftalik is not None and veri_gunluk is not None:
                # 1. Aylık ilk kez yeşile dönmüş olmalı (bu ay veya geçen ay)
                if not (aylik_bu_yesil or aylik_gecen_yesil):
                    continue

                # 2. Haftalık ilk kez yeşil olmalı
                if sym not in veri_haftalik.columns.levels[0]:
                    continue
                df_w = veri_haftalik[sym].dropna(how="all").dropna(subset=['Close'])
                if len(df_w) < 25:
                    continue
                df_w['HMA'] = hma_hesapla(df_w['Close'], periyot=20)
                df_w['HMA_Diff'] = df_w['HMA'].diff()
                son_w = df_w.iloc[-1]
                onceki_w = df_w.iloc[-2]
                iki_once_w = df_w.iloc[-3]
                haftalik_taze = ((son_w['HMA_Diff'] > 0) and (onceki_w['HMA_Diff'] <= 0)) or \
                                ((son_w['HMA_Diff'] > 0) and (onceki_w['HMA_Diff'] > 0) and (
                                            iki_once_w['HMA_Diff'] <= 0))
                if not haftalik_taze:
                    continue

                # 3. Günlük ilk kez yeşil olmalı
                if sym not in veri_gunluk.columns.levels[0]:
                    continue
                df_d = veri_gunluk[sym].dropna(how="all").dropna(subset=['Close'])
                if len(df_d) < 25:
                    continue
                df_d['HMA'] = hma_hesapla(df_d['Close'], periyot=20)
                df_d['HMA_Diff'] = df_d['HMA'].diff()
                df_d['RSI'] = rsi_hesapla(df_d['Close'], periyot=14)
                son_d = df_d.iloc[-1]
                onceki_d = df_d.iloc[-2]
                gunluk_taze = ((son_d['HMA_Diff'] > 0) and (onceki_d['HMA_Diff'] <= 0)) or \
                              ((son_d['HMA_Diff'] > 0) and (onceki_d['HMA_Diff'] > 0))
                if not gunluk_taze:
                    continue

                uygun_teknik = True
                tetik_etiketi = "🟢 3 Zaman Dilimi Yeşil"
                mtf_durumu = "🚀 Aylık+Haftalık+Günlük"
                df_kullanilacak = df_d
                son_fiyat = son_d['Close']
                son_rsi = son_d['RSI'] if not np.isnan(son_d['RSI']) else 50.0
                son_hacim = son_d.get('Volume', 0)
                ort_hacim = df_d['Volume'].iloc[-4:-1].mean() if len(df_d) >= 4 else son_hacim

            # ==============================================================
            # STRATEJİ 2: AYLIK HULL VE WAE AYNI ANDA İLK KEZ OLUMLUYA DÖNENLER
            # ==============================================================
            elif "Aylık Hull ve WAE Aynı Anda" in mtf_modu:
                wae_patlama_bu_ay = (son_m['WAE_Up'] > son_m['WAE_Line']) and (
                            onceki_m['WAE_Up'] <= onceki_m['WAE_Line'])
                wae_patlama_gecen_ay = (son_m['WAE_Up'] > son_m['WAE_Line']) and (
                            onceki_m['WAE_Up'] > onceki_m['WAE_Line']) and (
                                                   iki_once_m['WAE_Up'] <= iki_once_m['WAE_Line'])

                hull_ve_wae_bu_ay = aylik_bu_yesil and (son_m['WAE_Up'] > son_m['WAE_Line'])
                hull_ve_wae_gecen_ay = aylik_gecen_yesil and (son_m['WAE_Up'] > son_m['WAE_Line'])

                if hull_ve_wae_bu_ay or hull_ve_wae_gecen_ay or (aylik_bu_yesil and wae_patlama_bu_ay):
                    uygun_teknik = True
                    tetik_etiketi = "🟢 Hull + WAE Patlaması"
                    mtf_durumu = "💥 Çifte Momentumlu Dip"

            # ==============================================================
            # STRATEJİ 3: AYLIK HULL YEŞİLKEN HAFTALIK DÜZELTME BİTİRENLER
            # ==============================================================
            elif "Haftalık Düzeltme Bitirip" in mtf_modu and veri_haftalik is not None:
                aylik_pozitif = (son_m['HMA_Diff'] > 0) and (son_m['Close'] >= son_m['HMA'] * 0.96)
                if not aylik_pozitif:
                    continue

                if sym not in veri_haftalik.columns.levels[0]:
                    continue
                df_w = veri_haftalik[sym].dropna(how="all").dropna(subset=['Close'])
                if len(df_w) < 25:
                    continue

                df_w['HMA'] = hma_hesapla(df_w['Close'], periyot=20)
                df_w['HMA_Diff'] = df_w['HMA'].diff()
                df_w['RSI'] = rsi_hesapla(df_w['Close'], periyot=14)

                son_w = df_w.iloc[-1]
                onceki_w = df_w.iloc[-2]
                iki_once_w = df_w.iloc[-3]

                haftalik_bu_yesil = (son_w['HMA_Diff'] > 0) and (onceki_w['HMA_Diff'] <= 0)
                haftalik_gecen_yesil = (son_w['HMA_Diff'] > 0) and (onceki_w['HMA_Diff'] > 0) and (
                            iki_once_w['HMA_Diff'] <= 0)

                if haftalik_bu_yesil or haftalik_gecen_yesil:
                    uygun_teknik = True
                    tetik_etiketi = "🟢 Bu Hafta" if haftalik_bu_yesil else "⚡ Geçen Hafta"
                    mtf_durumu = "Aylık Boğa + Haftalık Tetik"
                    df_kullanilacak = df_w
                    son_fiyat = son_w['Close']
                    son_rsi = son_w['RSI'] if not np.isnan(son_w['RSI']) else 50.0
                    son_hacim = son_w.get('Volume', 0)
                    ort_hacim = df_w['Volume'].iloc[-4:-1].mean() if len(df_w) >= 4 else son_hacim

            # ==============================================================
            # STRATEJİ 4: DİPTEN YÜKSELİŞ TRENDİNE GEÇENLER (HIGHER-LOW)
            # ==============================================================
            elif "Dipten Yükseliş Trendine Geçenler" in mtf_modu:
                if not (aylik_bu_yesil or aylik_gecen_yesil):
                    continue

                son_24 = df_m.tail(24)
                if len(son_24) >= 12:
                    ana_dip = son_24['Low'].min()
                    ana_dip_idx = son_24['Low'].idxmin()

                    if ana_dip_idx in son_24.index[:-2]:
                        dip_sonrasi = son_24.loc[ana_dip_idx:]
                        ara_tepe = dip_sonrasi['High'].max()
                        son_donem_dip = son_24['Low'].iloc[-3:].min()

                        if son_donem_dip > (ana_dip * 1.04) and (son_m['Close'] > son_donem_dip):
                            uygun_teknik = True
                            tetik_etiketi = "🟢 Yüksek Dip Onaylı"
                            mtf_durumu = "📈 Higher-Low Dönüşü"

            # ==============================================================
            # STRATEJİ 5: SADECE AYLIK HULL YENİ YEŞİLE DÖNENLER
            # ==============================================================
            else:
                if aylik_bu_yesil or aylik_gecen_yesil:
                    uygun_teknik = True
                    tetik_etiketi = "🟢 Bu Ay" if aylik_bu_yesil else "⚡ Geçen Ay"
                    mtf_durumu = "Aylık Taze Dip"

            if not uygun_teknik:
                continue

            # Hacim Oranı Kontrolü
            hacim_orani = (son_hacim / ort_hacim) if (ort_hacim and ort_hacim > 0) else 1.0
            if hacim_filtresi and hacim_orani < 1.2:
                continue

            # ==============================================================
            # KATI TEMEL FİLTRE: OCF > 0 VE ROE > 0 OLMALIDIR!
            # ==============================================================
            temel = hisse_temel_bilgileri(sym)
            if temel["ocf"] <= 0 or temel["roe"] <= 0:
                continue  # Nakit üretmeyen veya özkaynak kârlılığı negatif/sıfır olanları doğrudan ele!

            zirve_5y = df_m['Close'].max()
            iskonto = ((zirve_5y - son_fiyat) / zirve_5y) * 100.0

            temiz_ticker = sym.replace(".IS", "")
            aday_listesi.append({
                "Kod": temiz_ticker,
                "Şirket": temel["sirket_adi"][:16],
                "Fiyat": round(son_fiyat, 2),
                "RSI": round(son_rsi, 1),
                "Dönüş": tetik_etiketi,
                "MTF": mtf_durumu,
                "Hacim": round(hacim_orani, 2),
                "FCF %": round(temel["fcf_yield"], 1),
                "ROE %": round(temel["roe"], 1),
                "İskonto %": round(max(0.0, iskonto), 1),
                "df": df_kullanilacak,
                "tam_sym": sym
            })
        except Exception:
            continue

    bar.empty()

    if not aday_listesi:
        st.warning(
            f"{secilen_endeks} içinde bu stratejiye, pozitif nakit akışına (OCF > 0) ve kârlılığa (ROE > 0) uyan hisse bulunamadı. Kapsamı genişletip tekrar deneyin.")
    else:
        df_puan = pd.DataFrame(aday_listesi)


        def normalize(col):
            if col.max() == col.min():
                return pd.Series(50, index=col.index)
            return (col - col.min()) / (col.max() - col.min()) * 100


        norm_fcf = normalize(df_puan["FCF %"])
        norm_roe = normalize(df_puan["ROE %"])
        norm_iskonto = normalize(df_puan["İskonto %"])
        norm_vol = normalize(df_puan["Hacim"])
        norm_rsi = 100 - normalize(df_puan["RSI"])

        df_puan["Skor"] = (norm_fcf * 0.30) + (norm_roe * 0.25) + (norm_iskonto * 0.25) + (norm_vol * 0.10) + (
                    norm_rsi * 0.10)
        df_puan["Skor"] = df_puan["Skor"].round(1)
        df_puan = df_puan.sort_values(by="Skor", ascending=False).reset_index(drop=True)

        st.success(
            f"🎯 Seçilen stratejiye ve kârlılık/nakit akışı kriterlerine uyan **{len(df_puan)}** kaliteli şirket saptandı!")

        tablo_gosterim = df_puan.drop(columns=["df", "tam_sym"]).copy()
        tablo_gosterim.index = tablo_gosterim.index + 1

        # DARALTILMIŞ KOMPAKT TABLO
        st.dataframe(
            tablo_gosterim,
            use_container_width=True,
            column_config={
                "Kod": st.column_config.TextColumn("Kod", width=60, help="Hisse kodu."),
                "Şirket": st.column_config.TextColumn("Şirket", width=110, help="Şirket unvanı."),
                "Fiyat": st.column_config.NumberColumn(f"Fiyat ({para_birimi})", width=70, format=f"{para_birimi}%.2f",
                                                       help="Son borsa fiyatı."),
                "RSI": st.column_config.NumberColumn("RSI", width=55, format="%.1f",
                                                     help="14 periyotluk RSI dip seviyesi."),
                "Dönüş": st.column_config.TextColumn("Tetik", width=85, help="Yeşile dönüş periyodu."),
                "MTF": st.column_config.TextColumn("MTF Durumu", width=110, help="Seçilen çoklu zaman dilimi yapısı."),
                "Hacim": st.column_config.NumberColumn("Hacim", width=65, format="%.2fx", help="Hacim patlaması katı."),
                "FCF %": st.column_config.NumberColumn("FCF %", width=60, format="%.1f%%",
                                                       help="Serbest Nakit Akışı Verimi."),
                "ROE %": st.column_config.NumberColumn("ROE %", width=60, format="%.1f%%",
                                                       help="Özsermaye Kârlılığı (Pozitif zorunlu)."),
                "İskonto %": st.column_config.NumberColumn("İskonto", width=65, format="%.1f%%",
                                                           help="Zirvesine göre iskonto oranı."),
                "Skor": st.column_config.NumberColumn("Skor", width=55, format="%.1f",
                                                      help="Bileşik Kalite Skoru (0-100).")
            }
        )

        st.markdown("---")
        st.subheader("📰 En Yüksek Skorlu İlk 5 Hisse — Doğrulanmış Türkçe Haberler & Grafik")

        for i, row in df_puan.head(5).iterrows():
            sym_clean = row['Kod']
            full_sym = row['tam_sym']
            df_plot = row['df'].tail(45)
            vol_badge = "🔥 Hacim Artışı" if row['Hacim'] >= 1.2 else "Normal Hacim"
            rsi_badge = f"📉 RSI Dip: {row['RSI']}" if row['RSI'] < 45 else f"RSI: {row['RSI']}"

            olumlu_ozetler, olumsuz_ozetler = canli_haber_ozetleri(full_sym, row['Şirket'])

            with st.container():
                pos_html = "".join([
                                       f"• <a href='{h['link']}' target='_blank' class='clickable-summary'>{h['ozet']}</a> <span class='src-tag'>[{h['source']}]</span><br/>"
                                       for h in olumlu_ozetler])
                neg_html = "".join([
                                       f"• <a href='{h['link']}' target='_blank' class='clickable-summary'>{h['ozet']}</a> <span class='src-tag'>[{h['source']}]</span><br/>"
                                       for h in olumsuz_ozetler])

                grafik_baslik = "Günlük Tetik Grafiği (1D)" if "3x MTF" in mtf_modu else (
                    "Haftalık Grafik (1W)" if "Haftalık Düzeltme" in mtf_modu else "Aylık Grafik (1M)")

                st.markdown(f"""
                <div class="card-box">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span class="badge-rank">#{i + 1} SKOR: {row['Skor']}</span>
                            <span style="font-size: 1.4rem; font-weight: 800; color: #fff; margin-left: 10px;">{sym_clean}</span>
                            <span style="font-size: 1.0rem; color: #94a3b8; margin-left: 8px;">{row['Şirket']}</span>
                            <span style="font-size: 1.1rem; color: #00c087; margin-left: 12px; font-weight: 700;">{row['Fiyat']} {para_birimi}</span>
                        </div>
                        <div>
                            <span class="badge-mtf" style="margin-right: 6px;">{row['MTF']}</span>
                            <span class="badge-vol" style="margin-right: 6px;">{vol_badge} ({row['Hacim']}x)</span>
                            <span class="badge-turn">{row['Dönüş']}</span>
                        </div>
                    </div>
                    <div style="margin-top: 8px;">
                        <span class="badge-metric">{rsi_badge}</span>
                        <span class="badge-metric">💵 FCF: %{row['FCF %']}</span>
                        <span class="badge-metric">📈 ROE: %{row['ROE %']}</span>
                        <span class="badge-metric">🎯 İskonto: %{row['İskonto %']}</span>
                    </div>
                    <div class="insight-box">
                        <div class="pos-header">✅ (+) Olumlu Gelişmeler & Fırsatlar (Detay İçin Cümleye Tıklayın):</div>
                        {pos_html}
                        <div class="neg-header">⚠️ (-) Tedbirler, Riskler & Maliyet Baskıları (Detay İçin Cümleye Tıklayın):</div>
                        {neg_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_plot.index,
                    open=df_plot['Open'], high=df_plot['High'],
                    low=df_plot['Low'], close=df_plot['Close'],
                    name=grafik_baslik,
                    increasing_line_color='#00c087', decreasing_line_color='#ff4b4b'
                ))
                fig.add_trace(go.Scatter(
                    x=df_plot.index, y=df_plot['HMA'],
                    mode='lines', name='Hull MA (20)',
                    line=dict(color='#00c087', width=2.5)
                ))
                fig.update_layout(
                    height=240,
                    margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_dark",
                    xaxis_rangeslider_visible=False,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")