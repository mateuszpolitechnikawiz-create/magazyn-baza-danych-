import streamlit as st
import pandas as pd
from supabase import create_client, Client
from fpdf import FPDF
import io
from datetime import datetime

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

# --- BEZPIECZNY IMPORT PLOTLY ---
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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
    pdf = FPDF()
    pdf.add_page()
    
    # Nagłówek
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "RAPORT STANU MAGAZYNOWEGO", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 10, f"Data wygenerowania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)
    
    # Tabela - Nagłówki
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(80, 10, "Nazwa Produktu", 1, 0, "C", True)
    pdf.cell(40, 10, "Kategoria", 1, 0, "C", True)
    pdf.cell(30, 10, "Ilosc", 1, 0, "C", True)
    pdf.cell(40, 10, "Wartosc (PLN)", 1, 1, "C", True)
    
    # Tabela - Dane
    pdf.set_font("Arial", "", 9)
    for _, row in dataframe.iterrows():
        pdf.cell(80, 8, str(row['nazwa']), 1)
        pdf.cell(40, 8, str(row['Kategoria_Nazwa']), 1)
        pdf.cell(30, 8, str(int(row['liczba'])), 1, 0, "C")
        pdf.cell(40, 8, f"{row['Wartość']:,.2f}", 1, 1, "R")
    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 10, f"Łączna wartość magazynu: {dataframe['Wartość'].sum():,.2f} PLN", ln=True, align="R")
    
    return pdf.output()

# --- NAGŁÓWEK I AUTO-UZUPEŁNIANIE ---
st.title("📦 System Zarządzania Magazynem WMS Pro")

LIMIT_MINIMUM = 5
UZUPELNIJ_DO = 50

if not df.empty:
    low_stock_df = df[df['liczba'] <= LIMIT_MINIMUM]
    if not low_stock_df.empty:
        col_alert, col_btn = st.columns([3, 1])
        with col_alert:
            st.warning(f"⚠️ **UWAGA!** Braki w {len(low_stock_df)} produktach.")
        with col_btn:
            if st.button("🚀 Auto-Uzupełnianie", use_container_width=True):
                for _, row in low_stock_df.iterrows():
                    supabase.table("produkty").update({"liczba": UZUPELNIJ_DO}).eq("id", row['id']).execute()
                st.rerun()

st.divider()

# --- STATYSTYKI I RAPORTY ---
if not df.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("Łączna Ilość", f"{int(df['liczba'].sum())} szt.")
    m2.metric("Wartość Sumaryczna", f"{df['Wartość'].sum():,.2f} PLN")
    
    with m3:
        st.write("📂 **Pobierz Raporty:**")
        c_csv, c_pdf = st.columns(2)
        
        # Pobieranie CSV
        csv_data = df.to_csv(index=False).encode('utf-8')
        c_csv.download_button("📊 CSV", data=csv_data, file_name="magazyn.csv", use_container_width=True)
        
        # Pobieranie PDF
        pdf_bytes = generate_pdf(df)
        c_pdf.download_button("📄 PDF", data=pdf_bytes, file_name="raport_magazyn.pdf", use_container_width=True)

    if PLOTLY_AVAILABLE:
        c_plot1, c_plot2 = st.columns(2)
        with c_plot1:
            st.plotly_chart(px.pie(df, values='Wartość', names='Kategoria_Nazwa', title="Podział Wartościowy"), use_container_width=True)
        with c_plot2:
            st.plotly_chart(px.bar(df.nlargest(8, 'Wartość'), x='nazwa', y='Wartość', color='nazwa', title="Top 8 Najdroższych Zapasów"), use_container_width=True)

st.divider()

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["🛒 Zamówienia", "📦 Produkty & Inwentaryzacja", "📂 Kategorie"])

# --- ZAKŁADKA 1: ZAMÓWIENIA (Z KATEGORIAMI) ---
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
                if st.button("✅ Potwierdź", use_container_width=True):
                    for i in st.session_state.cart:
                        act = supabase.table("produkty").select("liczba").eq("id", i['id']).single().execute()
                        supabase.table("produkty").update({"liczba": act.data['liczba'] - i['ilosc']}).eq("id", i['id']).execute()
                    st.session_state.cart = []
                    st.rerun()
                if st.button("🗑️ Wyczyść"):
                    st.session_state.cart = []
                    st.rerun()

# --- ZAKŁADKA 2: PRODUKTY (DODAWANIE + EDYCJA + LISTA) ---
with tab2:
    st.header("📦 Magazyn")
    with st.expander("➕ Dodaj nowy produkt"):
        with st.form("add_p"):
            n_n = st.text_input("Nazwa")
            n_l = st.number_input("Ilość", min_value=0)
            n_c = st.number_input("Cena", min_value=0.0)
            n_k = st.selectbox("Kategoria", options=[k['id'] for k in kategorie], format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
            if st.form_submit_button("Zapisz"):
                supabase.table("produkty").insert({"nazwa": n_n, "liczba": n_l, "cena": n_c, "kategoria_id": n_k}).execute()
                st.rerun()

    if not df.empty:
        st.subheader("📝 Szybka edycja i szukanie")
        szukaj = st.text_input("Szukaj produktu...")
        df_v = df[df['nazwa'].str.contains(szukaj, case=False)] if szukaj else df
        
        # Edycja
        e_id = st.selectbox("Edytuj produkt:", options=df_v['id'].tolist(), format_func=lambda x: df_v[df_v['id']==x]['nazwa'].values[0])
        p_e = df_v[df_v['id'] == e_id].iloc[0]
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        u_n = c1.text_input("Nazwa", value=p_e['nazwa'], key="un")
        u_s = c2.number_input("Stan", value=int(p_e['liczba']), key="us")
        u_p = c3.number_input("Cena", value=float(p_e['cena']), key="up")
        if c4.button("💾 Zapisz", use_container_width=True):
            supabase.table("produkty").update({"nazwa": u_n, "liczba": u_s, "cena": u_p}).eq("id", e_id).execute()
            st.rerun()
            
        def color_l(s): return ['background-color: #ffcccc' if v <= LIMIT_MINIMUM else '' for v in s]
        st.dataframe(df_v[['id', 'nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']].style.apply(color_l, subset=['liczba']), use_container_width=True)
        
        if st.button(f"🗑️ Usuń {p_e['nazwa']}"):
            supabase.table("produkty").delete().eq("id", e_id).execute()
            st.rerun()

# --- ZAKŁADKA 3: KATEGORIE ---
with tab3:
    st.header("📂 Kategorie")
    with st.form("add_k"):
        k_n = st.text_input("Nazwa kategorii")
        if st.form_submit_button("Dodaj"):
            supabase.table("Kategorie").insert({"nazwa": k_n}).execute()
            st.rerun()
    for k in kategorie:
        with st.expander(f"📁 {k['nazwa']}"):
            if st.button("Usuń kategorię", key=f"k_{k['id']}"):
                try:
                    supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                    st.rerun()
                except: st.error("Kategoria zawiera produkty!")
                    
