import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- BEZPIECZNY IMPORT PLOTLY ---
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
    # Zakładamy nazwę tabeli 'produkty' (małe litery)
    res_prod = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
    return res_kat.data, res_prod.data

kategorie, produkty = fetch_all_data()

# Przygotowanie danych do analizy w Pandas
df = pd.DataFrame(produkty)
if not df.empty:
    df['Kategoria_Nazwa'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- DASHBOARD STATYSTYK ---
st.title("📦 Magazyn z filtrowaniem zamówień")

if not df.empty:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Produkty", f"{int(df['liczba'].sum())} szt.")
    c2.metric("Wartość", f"{df['Wartość'].sum():,.2f} PLN")
    low_stock = len(df[df['liczba'] < 5])
    c3.metric("Niski stan", low_stock)
    
    csv = df.to_csv(index=False).encode('utf-8')
    c4.download_button("📥 Pobierz CSV", data=csv, file_name="magazyn.csv")

st.divider()

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["🛒 Zamówienia", "📦 Produkty", "📂 Kategorie"])

# --- ZAKŁADKA 1: ZAMÓWIENIA (Z FILTREM KATEGORII) ---
with tab1:
    st.header("Nowe Zamówienie")
    if df.empty:
        st.info("Brak produktów w bazie.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_filter, col_cart = st.columns([1, 1])
        
        with col_filter:
            st.subheader("Wybierz produkty")
            
            # --- FILTR KATEGORII ---
            lista_kat = ["Wszystkie"] + [k['nazwa'] for k in kategorie]
            wybrana_kat = st.selectbox("Filtruj wg kategorii", options=lista_kat)
            
            # Filtrowanie DataFrame na podstawie wyboru
            if wybrana_kat == "Wszystkie":
                df_filtered = df[df['liczba'] > 0]
            else:
                df_filtered = df[(df['Kategoria_Nazwa'] == wybrana_kat) & (df['liczba'] > 0)]
            
            if df_filtered.empty:
                st.warning("Brak dostępnych produktów w tej kategorii.")
            else:
                with st.form("add_to_cart_form"):
                    sel_id = st.selectbox(
                        "Produkt", 
                        options=df_filtered['id'].tolist(),
                        format_func=lambda x: f"{df_filtered[df_filtered['id']==x]['nazwa'].values[0]} (Dostępne: {df_filtered[df_filtered['id']==x]['liczba'].values[0]})"
                    )
                    order_qty = st.number_input("Ilość", min_value=1, step=1)
                    
                    if st.form_submit_button("➕ Dodaj do koszyka"):
                        p_info = df_filtered[df_filtered['id'] == sel_id].iloc[0]
                        
                        # Sprawdzenie czy już nie ma tego w koszyku (aby nie przekroczyć stanu)
                        qty_in_cart = sum(item['ilosc'] for item in st.session_state.cart if item['id'] == sel_id)
                        
                        if (order_qty + qty_in_cart) > p_info['liczba']:
                            st.error(f"Nie możesz zamówić więcej niż {p_info['liczba']} sztuk!")
                        else:
                            st.session_state.cart.append({
                                "id": int(sel_id), 
                                "nazwa": p_info['nazwa'], 
                                "cena": float(p_info['cena']), 
                                "ilosc": int(order_qty), 
                                "suma": float(order_qty * p_info['cena'])
                            })
                            st.rerun()

        with col_cart:
            st.subheader("Twój Koszyk")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['nazwa', 'ilosc', 'suma']], use_container_width=True)
                st.write(f"### Suma: {cart_df['suma'].sum():,.2f} PLN")
                
                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("✅ Potwierdź zamówienie", use_container_width=True):
                    for item in st.session_state.cart:
                        # Pobranie najświeższego stanu z bazy przed update
                        actual_stock = supabase.table("produkty").select("liczba").eq("id", item['id']).single().execute()
                        new_qty = actual_stock.data['liczba'] - item['ilosc']
                        supabase.table("produkty").update({"liczba": new_qty}).eq("id", item['id']).execute()
                    
                    st.success("Sprzedano!")
                    st.session_state.cart = []
                    st.rerun()
                
                if c_btn2.button("🗑️ Wyczyść koszyk", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.info("Koszyk jest pusty.")

# --- ZAKŁADKA 2: PRODUKTY (ZACHOWANO FUNKCJE) ---
with tab2:
    st.header("Zarządzanie Produktami")
    # ... Kod dodawania i listy produktów (taki jak wcześniej) ...
    # [Tutaj wklej sekcję z tab2 z poprzedniej wiadomości]

# --- ZAKŁADKA 3: KATEGORIE (ZACHOWANO FUNKCJE) ---
with tab3:
    st.header("Zarządzanie Kategoriami")
    # ... Kod dodawania i usuwania kategorii ...
    # [Tutaj wklej sekcję z tab3 z poprzedniej wiadomości]
