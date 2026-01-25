import streamlit as st
import pandas as pd
from supabase import create_client, Client
import io
from datetime import datetime

# --- BEZPIECZNY IMPORT FPDF ---
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# --- BEZPIECZNY IMPORT PLOTLY ---
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pro + PDF", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Błąd konfiguracji Supabase. Sprawdź st.secrets.")
    st.stop()

# --- FUNKCJA POBIERANIA DANYCH ---
def fetch_all_data():
    try:
        res_kat = supabase.table("Kategorie").select("*").execute()
        res_prod = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
        return res_kat.data, res_prod.data
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return [], []

kategorie, produkty = fetch_all_data()
df = pd.DataFrame(produkty)

if not df.empty:
    df['Kategoria_Nazwa'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- FUNKCJA GENEROWANIA PDF ---
def generate_pdf(dataframe):
    if not FPDF_AVAILABLE:
        return None
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "RAPORT STANU MAGAZYNOWEGO", ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 10, f"Data wygenerowania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)
    
    # Nagłówki tabeli
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(80, 10, "Nazwa Produktu", 1, 0, "C", True)
    pdf.cell(40, 10, "Kategoria", 1, 0, "C", True)
    pdf.cell(30, 10, "Ilosc", 1, 0, "C", True)
    pdf.cell(40, 10, "Wartosc (PLN)", 1, 1, "C", True)
    
    # Dane
    pdf.set_font("helvetica", "", 9)
    for _, row in dataframe.iterrows():
        pdf.cell(80, 8, str(row['nazwa'])[:40], 1)
        pdf.cell(40, 8, str(row['Kategoria_Nazwa']), 1)
        pdf.cell(30, 8, str(int(row['liczba'])), 1, 0, "C")
        pdf.cell(40, 8, f"{row['Wartość']:,.2f}", 1, 1, "R")
    
    return pdf.output()

# --- INTERFEJS UŻYTKOWNIKA ---
st.title("📦 System Zarządzania Magazynem WMS Pro")

# Auto-uzupełnianie
LIMIT_MINIMUM = 5
UZUPELNIJ_DO = 50

if not df.empty:
    low_stock_df = df[df['liczba'] <= LIMIT_MINIMUM]
    if not low_stock_df.empty:
        c_al, c_bt = st.columns([3, 1])
        with c_al: st.warning(f"⚠️ **UWAGA!** Braki w {len(low_stock_df)} produktach.")
        with c_bt:
            if st.button("🚀 Auto-Uzupełnianie"):
                for _, row in low_stock_df.iterrows():
                    supabase.table("produkty").update({"liczba": UZUPELNIJ_DO}).eq("id", row['id']).execute()
                st.rerun()

st.divider()

# --- STATYSTYKI I RAPORTY ---
if not df.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("Łączna Ilość", f"{int(df['liczba'].sum())} szt.")
    m2.metric("Wartość Magazynu", f"{df['Wartość'].sum():,.2f} PLN")
    
    with m3:
        st.write("📂 **Eksportuj Dane:**")
        c_csv, c_pdf = st.columns(2)
        
        # CSV
        csv_data = df.to_csv(index=False).encode('utf-8')
        c_csv.download_button("📊 CSV", data=csv_data, file_name="magazyn.csv", use_container_width=True)
        
        # PDF
        if FPDF_AVAILABLE:
            pdf_data = generate_pdf(df)
            c_pdf.download_button("📄 PDF", data=pdf_data, file_name="raport.pdf", use_container_width=True)
        else:
            c_pdf.error("Zainstaluj fpdf2")

# --- ZAKŁADKI (ZAMÓWIENIA, PRODUKTY, KATEGORIE) ---
tab1, tab2, tab3 = st.tabs(["🛒 Zamówienia", "📦 Produkty & Inwentaryzacja", "📂 Kategorie"])

# [Kod zakładek pozostaje taki sam jak wcześniej]
with tab1:
    st.header("🛒 Nowe Zamówienie")
    if df.empty:
        st.info("Brak produktów.")
    else:
        if 'cart' not in st.session_state: st.session_state.cart = []
        cf, cc = st.columns([1, 1])
        with cf:
            lista_k = ["Wszystkie"] + [k['nazwa'] for k in kategorie]
            wyb_k = st.selectbox("Wybierz kategorię", options=lista_k)
            df_o = df[df['liczba'] > 0] if wyb_k == "Wszystkie" else df[(df['Kategoria_Nazwa'] == wyb_k) & (df['liczba'] > 0)]
            with st.form("order_f"):
                s_id = st.selectbox("Produkt", options=df_o['id'].tolist(), format_func=lambda x: f"{df_o[df_o['id']==x]['nazwa'].values[0]} (Stan: {df_o[df_o['id']==x]['liczba'].values[0]})")
                o_qty = st.number_input("Ilość", min_value=1, step=1)
                if st.form_submit_button("➕ Dodaj"):
                    p = df_o[df_o['id'] == s_id].iloc[0]
                    st.session_state.cart.append({"id": int(s_id), "nazwa": p['nazwa'], "cena": float(p['cena']), "ilosc": int(o_qty), "suma": float(o_qty * p['cena'])})
                    st.rerun()
        with cc:
            if st.session_state.cart:
                st.table(pd.DataFrame(st.session_state.cart)[['nazwa', 'ilosc', 'suma']])
                if st.button("✅ Potwierdź zamówienie"):
                    for i in st.session_state.cart:
                        act = supabase.table("produkty").select("liczba").eq("id", i['id']).single().execute()
                        supabase.table("produkty").update({"liczba": act.data['liczba'] - i['ilosc']}).eq("id", i['id']).execute()
                    st.session_state.cart = []
                    st.rerun()

with tab2:
    st.header("📦 Magazyn")
    with st.expander("➕ Dodaj produkt"):
        with st.form("add_p"):
            n_n = st.text_input("Nazwa")
            n_l = st.number_input("Ilość", min_value=0)
            n_c = st.number_input("Cena", min_value=0.0)
            n_k = st.selectbox("Kategoria", options=[k['id'] for k in kategorie], format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
            if st.form_submit_button("Zapisz"):
                supabase.table("produkty").insert({"nazwa": n_n, "liczba": n_l, "cena": n_c, "kategoria_id": n_k}).execute()
                st.rerun()
    if not df.empty:
        szukaj = st.text_input("Szukaj...")
        df_v = df[df['nazwa'].str.contains(szukaj, case=False)] if szukaj else df
        e_id = st.selectbox("Edytuj:", options=df_v['id'].tolist(), format_func=lambda x: df_v[df_v['id']==x]['nazwa'].values[0])
        p_e = df_v[df_v['id'] == e_id].iloc[0]
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        un = c1.text_input("Nazwa", value=p_e['nazwa'])
        us = c2.number_input("Stan", value=int(p_e['liczba']))
        up = c3.number_input("Cena", value=float(p_e['cena']))
        if c4.button("💾 Zapisz"):
            supabase.table("produkty").update({"nazwa": un, "liczba": us, "cena": up}).eq("id", e_id).execute()
            st.rerun()
        st.dataframe(df_v[['nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']], use_container_width=True)

with tab3:
    st.header("📂 Kategorie")
    with st.form("kat_f"):
        kn = st.text_input("Nowa kategoria")
        if st.form_submit_button("Dodaj"):
            supabase.table("Kategorie").insert({"nazwa": kn}).execute()
            st.rerun()
    for k in kategorie:
        with st.expander(f"📁 {k['nazwa']}"):
            if st.button("Usuń", key=f"k_{k['id']}"):
                try:
                    supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                    st.rerun()
                except: st.error("Kategoria ma produkty!")
                
