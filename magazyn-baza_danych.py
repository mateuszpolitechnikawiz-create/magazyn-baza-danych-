import streamlit as st
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn WMS Pro", layout="wide", page_icon="📦")

# --- POŁĄCZENIE Z SUPABASE ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Błąd połączenia z bazą danych. Sprawdź plik secrets.toml.")
    st.stop()

# --- FUNKCJE POMOCNICZE ---
def get_data():
    """Pobiera świeże dane z bazy."""
    kat_res = supabase.table("Kategorie").select("*").execute()
    prod_res = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
    return kat_res.data, prod_res.data

kategorie, produkty = get_data()

# --- STYLE CSS (opcjonalnie dla lepszego wyglądu) ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 System Zarządzania Magazynem")

# --- DASHBOARD (Statystyki na górze) ---
if produkty:
    st.subheader("Podsumowanie Magazynu")
    c1, c2, c3 = st.columns(3)
    total_items = sum(p['liczba'] for p in produkty)
    total_val = sum(p['liczba'] * p['cena'] for p in produkty)
    
    c1.metric("Wszystkie produkty", f"{total_items} szt.")
    c2.metric("Wartość magazynu", f"{total_val:,.2f} PLN")
    c3.metric("Liczba kategorii", len(kategorie))
    st.divider()

# --- ZAKŁADKI ---
tab_order, tab_prod, tab_kat = st.tabs(["🛒 NOWE ZAMÓWIENIE", "📦 PRODUKTY", "📂 KATEGORIE"])

# --- TAB: ZAMÓWIENIA (KOSZYK) ---
with tab_order:
    st.header("Kreator Zamówień")
    
    if not produkty:
        st.info("Dodaj produkty w zakładce obok, aby móc składać zamówienia.")
    else:
        # Inicjalizacja koszyka w sesji
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_sell, col_cart = st.columns([1, 1])

        with col_sell:
            st.subheader("Dodaj do listy")
            with st.form("add_to_cart"):
                # Wybór produktu (tylko te, które mają stan > 0)
                available_prods = [p for p in produkty if p['liczba'] > 0]
                
                if not available_prods:
                    st.warning("Brak towaru na stanie!")
                    submitted = False
                else:
                    sel_p_id = st.selectbox(
                        "Produkt", 
                        options=[p['id'] for p in available_prods],
                        format_func=lambda x: next(f"{p['nazwa']} (Stan: {p['liczba']}) | {p['cena']} zł" for p in available_prods if p['id'] == x)
                    )
                    qty = st.number_input("Zamawiana ilość", min_value=1, step=1)
                    submitted = st.form_submit_button("➕ Dodaj do zamówienia")

                    if submitted:
                        p_data = next(p for p in available_prods if p['id'] == sel_p_id)
                        
                        # Sprawdzenie czy nie przekraczamy stanu (również tego w koszyku)
                        in_cart = sum(item['ilosc'] for item in st.session_state.cart if item['id'] == sel_p_id)
                        
                        if (qty + in_cart) > p_data['liczba']:
                            st.error(f"Nie możesz dodać tyle produktu! Dostępne łącznie: {p_data['liczba']}")
                        else:
                            st.session_state.cart.append({
                                "id": p_data['id'],
                                "nazwa": p_data['nazwa'],
                                "cena": p_data['cena'],
                                "ilosc": qty,
                                "suma": qty * p_data['cena']
                            })
                            st.rerun()

        with col_cart:
            st.subheader("Twoje Zamówienie")
            if st.session_state.cart:
                total_order = 0
                for idx, item in enumerate(st.session_state.cart):
                    col_a, col_b = st.columns([3, 1])
                    col_a.write(f"**{item['nazwa']}** ({item['ilosc']} szt. x {item['cena']} zł)")
                    col_b.write(f"**{item['suma']:.2f} zł**")
                    total_order += item['suma']
                
                st.divider()
                st.write(f"### RAZEM: {total_order:.2f} PLN")

                if st.button("✅ Potwierdź sprzedaż / Wydanie"):
                    with st.spinner("Aktualizowanie bazy..."):
                        for item in st.session_state.cart:
                            # Pobranie aktualnego stanu prosto z bazy przed update
                            db_prod = supabase.table("produkty").select("liczba").eq("id", item['id']).single().execute()
                            new_qty = db_prod.data['liczba'] - item['ilosc']
                            # Update
                            supabase.table("produkty").update({"liczba": new_qty}).eq("id", item['id']).execute()
                    
                    st.success("Zamówienie zrealizowane! Stan magazynowy zaktualizowany.")
                    st.session_state.cart = []
                    st.rerun()
                
                if st.button("🗑️ Wyczyść koszyk", type="secondary"):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.info("Koszyk jest pusty.")

# --- TAB: PRODUKTY ---
with tab_prod:
    st.header("Zarządzanie Produktami")
    
    with st.expander("➕ Dodaj nowy produkt"):
        if not kategorie:
            st.warning("Najpierw dodaj kategorię!")
        else:
            with st.form("add_product_form"):
                n_p = st.text_input("Nazwa produktu")
                n_l = st.number_input("Ilość na start", min_value=0, step=1)
                n_c = st.number_input("Cena jednostkowa (PLN)", min_value=0.0, format="%.2f")
                n_k = st.selectbox("Kategoria", options=[k['id'] for k in kategorie], 
                                    format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
                if st.form_submit_button("Dodaj do bazy"):
                    if n_p:
                        supabase.table("produkty").insert({"nazwa": n_p, "liczba": n_l, "cena": n_c, "kategoria_id": n_k}).execute()
                        st.success("Produkt dodany!")
                        st.rerun()

    if produkty:
        # Wyświetlanie jako DataFrame dla lepszej czytelności
        display_df = []
        for p in produkty:
            display_df.append({
                "ID": p['id'],
                "Nazwa": p['nazwa'],
                "Kategoria": p['Kategorie']['nazwa'] if p['Kategorie'] else "Brak",
                "Ilość": p['liczba'],
                "Cena": f"{p['cena']:.2f} zł",
                "Wartość": f"{p['liczba'] * p['cena']:.2f} zł"
            })
        st.dataframe(display_df, use_container_width=True)
        
        # Usuwanie
        to_del = st.selectbox("Usuń produkt", options=[p['id'] for p in produkty], 
                              format_func=lambda x: next(p['nazwa'] for p in produkty if p['id'] == x))
        if st.button("🗑️ Usuń produkt permanentnie", key="del_p"):
            supabase.table("produkty").delete().eq("id", to_del).execute()
            st.rerun()
    else:
        st.info("Magazyn jest pusty.")

# --- TAB: KATEGORIE ---
with tab_kat:
    st.header("Kategorie Produktów")
    
    col_add, col_list = st.columns([1, 2])
    
    with col_add:
        with st.form("add_kat_form"):
            new_kat_name = st.text_input("Nowa kategoria")
            new_kat_desc = st.text_area("Opis")
            if st.form_submit_button("Zapisz kategorię"):
                if new_kat_name:
                    supabase.table("Kategorie").insert({"nazwa": new_kat_name, "opis": new_kat_desc}).execute()
                    st.rerun()
    
    with col_list:
        if kategorie:
            for k in kategorie:
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{k['nazwa']}**")
                    if c2.button("Usuń", key=f"del_k_{k['id']}"):
                        # Uwaga: Supabase zgłosi błąd, jeśli kategoria ma przypisane produkty
                        try:
                            supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                            st.rerun()
                        except:
                            st.error("Nie można usunąć kategorii, która zawiera produkty!")
        else:
            st.info("Brak kategorii.")
