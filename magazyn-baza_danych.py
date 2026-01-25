import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Bezpieczny import plotly
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pro", layout="wide", page_icon="📦")

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
    res_kat = supabase.table("Kategorie").select("*").execute()
    # Upewnij się, że nazwa tabeli 'produkty' zgadza się z Twoją bazą (mała/wielka litera)
    res_prod = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
    return res_kat.data, res_prod.data

kategorie, produkty = fetch_all_data()

# Przygotowanie danych do analizy
df = pd.DataFrame(produkty)
if not df.empty:
    df['Kategoria_Nazwa'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- TYTUŁ I STATYSTYKI ---
st.title("📦 Zarządzanie Magazynem & Sprzedaż")

if not df.empty:
    c1, c2, c3, c4 = st.columns(4)
    total_val = df['Wartość'].sum()
    c1.metric("Produkty (łącznie)", f"{int(df['liczba'].sum())} szt.")
    c2.metric("Wartość Magazynu", f"{total_val:,.2f} PLN")
    
    # Powiadomienie o niskim stanie
    low_stock_count = len(df[df['liczba'] < 5])
    c3.metric("Niskie stany (<5)", low_stock_count, delta=-low_stock_count, delta_color="inverse")
    
    csv = df.to_csv(index=False).encode('utf-8')
    c4.download_button("📥 Pobierz Raport CSV", data=csv, file_name="magazyn.csv")

# --- ANALITYKA WIZUALNA ---
if PLOTLY_AVAILABLE and not df.empty:
    col_a, col_b = st.columns(2)
    with col_a:
        fig1 = px.pie(df, values='Wartość', names='Kategoria_Nazwa', title="Udział wartościowy kategorii")
        st.plotly_chart(fig1, use_container_width=True)
    with col_b:
        fig2 = px.bar(df.nlargest(10, 'liczba'), x='nazwa', y='liczba', title="Top 10 najliczniejszych produktów")
        st.plotly_chart(fig2, use_container_width=True)
elif not PLOTLY_AVAILABLE:
    st.info("💡 Zainstaluj 'plotly', aby zobaczyć wykresy.")

st.divider()

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["🛒 Zamówienia", "📦 Produkty", "📂 Kategorie"])

# --- ZAKŁADKA 1: ZAMÓWIENIA (KOSZYK) ---
with tab1:
    st.header("Nowe Zamówienie")
    if df.empty:
        st.info("Brak produktów w bazie.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_in, col_out = st.columns([1, 1])
        
        with col_in:
            with st.form("add_to_cart"):
                sel_id = st.selectbox("Wybierz produkt", options=df['id'].tolist(),
                                      format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
                order_qty = st.number_input("Ilość", min_value=1, step=1)
                if st.form_submit_button("➕ Dodaj do koszyka"):
                    p_info = df[df['id'] == sel_id].iloc[0]
                    if order_qty > p_info['liczba']:
                        st.error("Brak wystarczającej ilości na stanie!")
                    else:
                        st.session_state.cart.append({
                            "id": int(sel_id), "nazwa": p_info['nazwa'], 
                            "cena": float(p_info['cena']), "ilosc": int(order_qty), 
                            "suma": float(order_qty * p_info['cena'])
                        })
                        st.rerun()

        with col_out:
            if st.session_state.cart:
                temp_cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(temp_cart_df[['nazwa', 'ilosc', 'suma']], use_container_width=True)
                total_cart = temp_cart_df['suma'].sum()
                st.write(f"### Razem: {total_cart:.2f} PLN")
                
                if st.button("✅ Potwierdź i odejmij z bazy"):
                    for item in st.session_state.cart:
                        curr_stock = df[df['id'] == item['id']]['liczba'].values[0]
                        supabase.table("produkty").update({"liczba": int(curr_stock - item['ilosc'])}).eq("id", item['id']).execute()
                    st.success("Zamówienie zrealizowane!")
                    st.session_state.cart = []
                    st.rerun()
                if st.button("🗑️ Wyczyść koszyk"):
                    st.session_state.cart = []
                    st.rerun()

# --- ZAKŁADKA 2: PRODUKTY (ZARZĄDZANIE) ---
with tab2:
    st.header("Baza Produktów")
    with st.expander("➕ Dodaj nowy produkt"):
        if not kategorie:
            st.warning("Najpierw dodaj kategorię!")
        else:
            with st.form("new_product"):
                n_nazwa = st.text_input("Nazwa")
                n_liczba = st.number_input("Ilość", min_value=0)
                n_cena = st.number_input("Cena", min_value=0.0)
                n_kat = st.selectbox("Kategoria", options=[k['id'] for k in kategorie],
                                     format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
                if st.form_submit_button("Zapisz produkt"):
                    supabase.table("produkty").insert({"nazwa": n_nazwa, "liczba": n_liczba, "cena": n_cena, "kategoria_id": n_kat}).execute()
                    st.rerun()

    if not df.empty:
        # Kolorowanie niskich stanów w tabeli
        def highlight_low(s):
            return ['color: red' if v < 5 else '' for v in s]
        
        st.dataframe(df[['id', 'nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']]
                     .style.apply(highlight_low, subset=['liczba']), use_container_width=True)
        
        # Usuwanie
        to_del = st.selectbox("Wybierz produkt do usunięcia", options=df['id'].tolist(),
                              format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
        if st.button("🗑️ Usuń produkt", key="del_prod_btn"):
            supabase.table("produkty").delete().eq("id", to_del).execute()
            st.rerun()

# --- ZAKŁADKA 3: KATEGORIE ---
with tab3:
    st.header("Kategorie")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.form("new_cat"):
            c_nazwa = st.text_input("Nazwa kategorii")
            c_opis = st.text_area("Opis")
            if st.form_submit_button("Dodaj kategorię"):
                if c_nazwa:
                    supabase.table("Kategorie").insert({"nazwa": c_nazwa, "opis": c_opis}).execute()
                    st.rerun()
    with col_b:
        if kategorie:
            for k in kategorie:
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{k['nazwa']}**")
                if c2.button("Usuń", key=f"del_k_{k['id']}"):
                    try:
                        supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                        st.rerun()
                    except:
                        st.error("Nie można usunąć kategorii z przypisanymi produktami!")
