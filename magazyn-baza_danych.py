import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- BEZPIECZNY IMPORT PLOTLY ---
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pro + Finanse", layout="wide", page_icon="📊")

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
        res_sales = supabase.table("sprzedaz").select("*").execute()
        return res_kat.data, res_prod.data, res_sales.data
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return [], [], []

kategorie, produkty, sprzedaz_raw = fetch_all_data()

# Przygotowanie danych do analizy w Pandas
df = pd.DataFrame(produkty)
if not df.empty:
    df['Kategoria_Nazwa'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- ZAKŁADKI ---
tab1, tab2, tab3, tab4 = st.tabs(["🛒 Zamówienia", "📦 Baza Produktów", "📂 Kategorie", "📈 Analiza Zysków"])

# --- ZAKŁADKA 1: ZAMÓWIENIA ---
with tab1:
    st.header("🛒 Nowe Zamówienie")
    if df.empty:
        st.info("Brak produktów w bazie.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_filter, col_cart = st.columns([1, 1])
        
        with col_filter:
            st.subheader("Wybierz produkty")
            lista_kat_nazw = ["Wszystkie"] + [k['nazwa'] for k in kategorie]
            wybrana_kat = st.selectbox("Filtruj wg kategorii", options=lista_kat_nazw)
            
            df_filtered = df[df['liczba'] > 0] if wybrana_kat == "Wszystkie" else df[(df['Kategoria_Nazwa'] == wybrana_kat) & (df['liczba'] > 0)]
            
            if df_filtered.empty:
                st.warning("Brak dostępnych towarów.")
            else:
                with st.form("add_to_cart_form"):
                    sel_id = st.selectbox("Produkt", options=df_filtered['id'].tolist(),
                                        format_func=lambda x: f"{df_filtered[df_filtered['id']==x]['nazwa'].values[0]} (Stan: {df_filtered[df_filtered['id']==x]['liczba'].values[0]})")
                    order_qty = st.number_input("Ilość", min_value=1, step=1)
                    if st.form_submit_button("➕ Dodaj do koszyka"):
                        p_info = df_filtered[df_filtered['id'] == sel_id].iloc[0]
                        st.session_state.cart.append({
                            "id": int(sel_id), "nazwa": p_info['nazwa'], 
                            "cena": float(p_info['cena']), "ilosc": int(order_qty), 
                            "suma": float(order_qty * p_info['cena'])
                        })
                        st.rerun()

        with col_cart:
            st.subheader("Twój Koszyk")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.table(cart_df[['nazwa', 'ilosc', 'suma']])
                total_sum = cart_df['suma'].sum()
                st.write(f"### Razem: {total_sum:.2f} PLN")
                
                if st.button("✅ Potwierdź i zapisz sprzedaż"):
                    for item in st.session_state.cart:
                        # Update stanu
                        actual = supabase.table("produkty").select("liczba").eq("id", item['id']).single().execute()
                        supabase.table("produkty").update({"liczba": actual.data['liczba'] - item['ilosc']}).eq("id", item['id']).execute()
                        # Zapis sprzedaży
                        supabase.table("sprzedaz").insert({"produkt_id": item['id'], "ilosc": item['ilosc'], "kwota_total": item['suma']}).execute()
                    
                    st.success("Zamówienie zrealizowane!")
                    st.session_state.cart = []
                    st.rerun()
                
                if st.button("🗑️ Wyczyść koszyk"):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.info("Koszyk jest pusty.")

# --- ZAKŁADKA 2: PRODUKTY ---
with tab2:
    st.header("📦 Magazyn i Produkty")
    with st.expander("➕ Dodaj nowy produkt"):
        if not kategorie:
            st.warning("Dodaj najpierw kategorię!")
        else:
            with st.form("new_p"):
                n_nazwa = st.text_input("Nazwa")
                n_liczba = st.number_input("Ilość", min_value=0)
                n_cena = st.number_input("Cena", min_value=0.0, format="%.2f")
                n_kat = st.selectbox("Kategoria", options=[k['id'] for k in kategorie], format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
                if st.form_submit_button("Zapisz"):
                    supabase.table("produkty").insert({"nazwa": n_nazwa, "liczba": n_liczba, "cena": n_cena, "kategoria_id": n_kat}).execute()
                    st.rerun()

    if not df.empty:
        def highlight_low(s):
            return ['color: red' if v < 5 else '' for v in s]
        st.dataframe(df[['nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']].style.apply(highlight_low, subset=['liczba']), use_container_width=True)
        
        st.subheader("Usuwanie")
        to_del = st.selectbox("Produkt do usunięcia", options=df['id'].tolist(), format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
        if st.button("Usuń produkt"):
            supabase.table("produkty").delete().eq("id", to_del).execute()
            st.rerun()

# --- ZAKŁADKA 3: KATEGORIE ---
with tab3:
    st.header("📂 Kategorie")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.form("new_cat"):
            c_name = st.text_input("Nazwa kategorii")
            c_desc = st.text_area("Opis")
            if st.form_submit_button("Dodaj"):
                supabase.table("Kategorie").insert({"nazwa": c_name, "opis": c_desc}).execute()
                st.rerun()
    with col_b:
        for k in kategorie:
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{k['nazwa']}**")
            if c2.button("Usuń", key=f"dk_{k['id']}"):
                try:
                    supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                    st.rerun()
                except:
                    st.error("Kategoria ma przypisane produkty!")

# --- ZAKŁADKA 4: ANALIZA ZYSKÓW ---
with tab4:
    st.header("📈 Dzienne Zyski")
    if not sprzedaz_raw:
        st.info("Brak historii sprzedaży.")
    else:
        sales_df = pd.DataFrame(sprzedaz_raw)
        sales_df['data'] = pd.to_datetime(sales_df['created_at']).dt.date
        daily_profit = sales_df.groupby('data')['kwota_total'].sum().reset_index()

        st.metric("Całkowity Przychód", f"{daily_profit['kwota_total'].sum():,.2f} PLN")
        
        if PLOTLY_AVAILABLE:
            fig = px.bar(daily_profit, x='data', y='kwota_total', title="Zysk na przestrzeni dni", color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.bar_chart(daily_profit.set_index('data'))

        st.subheader("Ostatnie operacje")
        st.dataframe(sales_df.sort_values('created_at', ascending=False), use_container_width=True)
