import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pro + Analityka", layout="wide", page_icon="📊")

# --- POŁĄCZENIE Z SUPABASE ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Błąd połączenia z bazą danych. Sprawdź secrets.toml.")
    st.stop()

# --- POBIERANIE DANYCH ---
def get_data():
    kat_res = supabase.table("Kategorie").select("*").execute()
    prod_res = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
    return kat_res.data, prod_res.data

kategorie, produkty = get_data()

# Przygotowanie DataFrame dla analityki
if produkty:
    df = pd.DataFrame(produkty)
    # Wyciąganie nazwy kategorii z zagnieżdżonego słownika
    df['Kategoria_Nazwa'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
    df['Wartość Całkowita'] = df['liczba'] * df['cena']
else:
    df = pd.DataFrame()

st.title("📊 Zaawansowany System Magazynowy")

# --- SEKCJIA 1: DASHBOARD I ANALITYKA ---
if not df.empty:
    st.subheader("📈 Analityka i Stan Magazynu")
    
    # Metryki główne
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Suma Produktów", f"{int(df['liczba'].sum())} szt.")
    c2.metric("Wartość Magazynu", f"{df['Wartość Całkowita'].sum():,.2f} PLN")
    c3.metric("Pozycje poniżej limitu", len(df[df['liczba'] < 5]))
    
    # Eksport do CSV (Nowa funkcja)
    csv = df[['nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość Całkowita']].to_csv(index=False).encode('utf-8')
    c4.download_button("📥 Pobierz Raport CSV", data=csv, file_name="stan_magazynu.csv", mime="text/csv")

    # Powiadomienia o niskim stanie (System ostrzegania)
    low_stock = df[df['liczba'] < 5]
    if not low_stock.empty:
        st.warning(f"⚠️ **Uwaga! Następujące produkty kończą się (poniżej 5 szt.):** {', '.join(low_stock['nazwa'].tolist())}")

    # Wykresy
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        fig_pie = px.pie(df, values='Wartość Całkowita', names='Kategoria_Nazwa', 
                         title="Udział Kategorii w Wartości Magazynu", hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
        

    with col_chart2:
        fig_bar = px.bar(df.sort_values('liczba', ascending=False).head(10), 
                         x='nazwa', y='liczba', color='Kategoria_Nazwa',
                         title="Top 10 Produktów wg Ilości")
        st.plotly_chart(fig_bar, use_container_width=True)
        

st.divider()

# --- ZAKŁADKI ---
tab_order, tab_prod, tab_kat = st.tabs(["🛒 ZAMÓWIENIE", "📦 PRODUKTY", "📂 KATEGORIE"])

# --- TAB: ZAMÓWIENIA (KOSZYK) ---
with tab_order:
    if not produkty:
        st.info("Brak produktów.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_sell, col_cart = st.columns([1, 1])

        with col_sell:
            st.subheader("Dodaj do koszyka")
            with st.form("order_form"):
                sel_p_id = st.selectbox("Wybierz towar", options=df['id'].tolist(),
                                        format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
                qty = st.number_input("Ilość", min_value=1, step=1)
                if st.form_submit_button("➕ Dodaj"):
                    p_row = df[df['id'] == sel_p_id].iloc[0]
                    if qty > p_row['liczba']:
                        st.error("Brak wystarczającej ilości!")
                    else:
                        st.session_state.cart.append({
                            "id": int(sel_p_id), "nazwa": p_row['nazwa'], 
                            "cena": float(p_row['cena']), "ilosc": int(qty), "suma": float(qty * p_row['cena'])
                        })
                        st.rerun()

        with col_cart:
            st.subheader("Podsumowanie")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.table(cart_df[['nazwa', 'ilosc', 'suma']])
                st.write(f"### RAZEM: {cart_df['suma'].sum():,.2f} PLN")
                
                if st.button("✅ Potwierdź Wydanie z Magazynu"):
                    for item in st.session_state.cart:
                        current_qty = df[df['id'] == item['id']]['liczba'].values[0]
                        supabase.table("produkty").update({"liczba": int(current_qty - item['ilosc'])}).eq("id", item['id']).execute()
                    st.success("Zrealizowano!")
                    st.session_state.cart = []
                    st.rerun()
                
                if st.button("🗑️ Wyczyść"):
                    st.session_state.cart = []
                    st.rerun()

# --- TAB: PRODUKTY ---
with tab_prod:
    with st.expander("➕ Dodaj produkt"):
        with st.form("new_p"):
            name = st.text_input("Nazwa")
            stock = st.number_input("Ilość", min_value=0)
            price = st.number_input("Cena", min_value=0.0)
            cat = st.selectbox("Kategoria", options=[k['id'] for k in kategorie], 
                                format_func=lambda x: next(kat['nazwa'] for kat in kategorie if kat['id'] == x))
            if st.form_submit_button("Zapisz"):
                supabase.table("produkty").insert({"nazwa": name, "liczba": stock, "cena": price, "kategoria_id": cat}).execute()
                st.rerun()

    # Tabela z kolorowaniem niskiego stanu
    if not df.empty:
        def color_low_stock(val):
            color = 'red' if val < 5 else 'black'
            return f'color: {color}'
        
        st.write("### Lista towarów")
        st.dataframe(df[['id', 'nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość Całkowita']]
                     .style.applymap(color_low_stock, subset=['liczba']), use_container_width=True)

# --- TAB: KATEGORIE ---
with tab_kat:
    # ... (Twój kod do zarządzania kategoriami pozostaje bez zmian) ...
    st.write("Zarządzaj kategoriami tutaj.")
    # (Możesz tu wkleić kod z poprzedniej odpowiedzi)
