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
    try:
        res_kat = supabase.table("Kategorie").select("*").execute()
        # Upewnij się, że nazwa tabeli w Supabase to 'produkty' (małymi) lub 'Produkty'
        res_prod = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
        return res_kat.data, res_prod.data
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return [], []

kategorie, produkty = fetch_all_data()

# Przygotowanie danych do analizy w Pandas
df = pd.DataFrame(produkty)
if not df.empty:
    df['Kategoria_Nazwa'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- TYTUŁ I STATYSTYKI ---
st.title("📦 System Zarządzania Magazynem")

if not df.empty:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Produkty (łącznie)", f"{int(df['liczba'].sum())} szt.")
    c2.metric("Wartość Magazynu", f"{df['Wartość'].sum():,.2f} PLN")
    low_stock_count = len(df[df['liczba'] < 5])
    c3.metric("Niskie stany (<5)", low_stock_count)
    
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

st.divider()

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["🛒 Nowe Zamówienie", "📦 Baza Produktów", "📂 Kategorie"])

# --- ZAKŁADKA 1: ZAMÓWIENIA ---
with tab1:
    st.header("🛒 Kreator Zamówienia")
    if df.empty:
        st.info("Brak produktów w bazie.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_filter, col_cart = st.columns([1, 1])
        
        with col_filter:
            st.subheader("Wybierz produkty")
            
            # FILTR KATEGORII
            lista_kat_nazw = ["Wszystkie"] + [k['nazwa'] for k in kategorie]
            wybrana_kat = st.selectbox("Filtruj wg kategorii", options=lista_kat_nazw)
            
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
                        format_func=lambda x: f"{df_filtered[df_filtered['id']==x]['nazwa'].values[0]} (Stan: {df_filtered[df_filtered['id']==x]['liczba'].values[0]})"
                    )
                    order_qty = st.number_input("Ilość", min_value=1, step=1)
                    
                    if st.form_submit_button("➕ Dodaj do koszyka"):
                        p_info = df_filtered[df_filtered['id'] == sel_id].iloc[0]
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
                st.table(cart_df[['nazwa', 'ilosc', 'suma']])
                st.write(f"### Suma: {cart_df['suma'].sum():,.2f} PLN")
                
                if st.button("✅ Potwierdź zamówienie"):
                    for item in st.session_state.cart:
                        actual_stock = supabase.table("produkty").select("liczba").eq("id", item['id']).single().execute()
                        new_qty = actual_stock.data['liczba'] - item['ilosc']
                        supabase.table("produkty").update({"liczba": new_qty}).eq("id", item['id']).execute()
                    
                    st.success("Zrealizowano zamówienie!")
                    st.session_state.cart = []
                    st.rerun()
                
                if st.button("🗑️ Wyczyść koszyk"):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.info("Koszyk jest pusty.")

# --- ZAKŁADKA 2: PRODUKTY ---
with tab2:
    st.header("📦 Zarządzanie Produktami")
    
    with st.expander("➕ Dodaj nowy produkt"):
        if not kategorie:
            st.warning("Najpierw dodaj kategorię w zakładce 'Kategorie'!")
        else:
            with st.form("new_product_form"):
                n_nazwa = st.text_input("Nazwa produktu")
                n_liczba = st.number_input("Ilość", min_value=0, step=1)
                n_cena = st.number_input("Cena", min_value=0.0, format="%.2f")
                n_kat = st.selectbox("Kategoria", options=[k['id'] for k in kategorie],
                                     format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
                if st.form_submit_button("Zapisz produkt"):
                    if n_nazwa:
                        supabase.table("produkty").insert({
                            "nazwa": n_nazwa, "liczba": n_liczba, 
                            "cena": n_cena, "kategoria_id": n_kat
                        }).execute()
                        st.success("Dodano produkt!")
                        st.rerun()

    if not df.empty:
        st.subheader("Lista produktów w magazynie")
        # Kolorowanie niskich stanów
        def highlight_low(s):
            return ['color: red' if v < 5 else '' for v in s]
        
        st.dataframe(df[['id', 'nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']]
                     .style.apply(highlight_low, subset=['liczba']), use_container_width=True)
        
        st.divider()
        st.subheader("Usuwanie produktu")
        to_del = st.selectbox("Wybierz produkt do usunięcia", options=df['id'].tolist(),
                              format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
        if st.button("🗑️ Usuń wybrany produkt"):
            supabase.table("produkty").delete().eq("id", to_del).execute()
            st.success("Usunięto!")
            st.rerun()
    else:
        st.info("Brak produktów do wyświetlenia.")

# --- ZAKŁADKA 3: KATEGORIE ---
with tab3:
    st.header("📂 Zarządzanie Kategoriami")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Dodaj kategorię")
        with st.form("new_cat_form"):
            c_nazwa = st.text_input("Nazwa kategorii")
            c_opis = st.text_area("Opis (opcjonalnie)")
            if st.form_submit_button("Dodaj kategorię"):
                if c_nazwa:
                    supabase.table("Kategorie").insert({"nazwa": c_nazwa, "opis": c_opis}).execute()
                    st.success(f"Dodano kategorię: {c_nazwa}")
                    st.rerun()

    with col_b:
        st.subheader("Istniejące kategorie")
        if kategorie:
            for k in kategorie:
                with st.expander(f"📁 {k['nazwa']}"):
                    st.write(f"Opis: {k['opis'] if k['opis'] else 'Brak'}")
                    if st.button("Usuń", key=f"del_k_{k['id']}"):
                        try:
                            supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                            st.rerun()
                        except:
                            st.error("Nie można usunąć kategorii, która ma przypisane produkty!")
        else:
            st.info("Brak zdefiniowanych kategorii.")
