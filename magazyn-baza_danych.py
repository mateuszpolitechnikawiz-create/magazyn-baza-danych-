import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="WMS Pro - Pełny System", layout="wide", page_icon="📦")

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

# --- KONFIGURACJA PROGÓW DLA AUTO-ZAMAWIANIA ---
LIMIT_MINIMUM = 5      # Próg alarmowy
UZUPELNIJ_DO = 50      # Do jakiej ilości uzupełnia przycisk

# --- NAGŁÓWEK I AUTO-UZUPEŁNIANIE ---
st.title("📦 System Zarządzania Magazynem WMS")

if not df.empty:
    low_stock_df = df[df['liczba'] <= LIMIT_MINIMUM]
    
    if not low_stock_df.empty:
        col_alert, col_btn = st.columns([3, 1])
        with col_alert:
            st.warning(f"⚠️ **Alarm niskiego stanu!** {len(low_stock_df)} produktów wymaga uzupełnienia (stan <= {LIMIT_MINIMUM}).")
        with col_btn:
            if st.button("🚀 Zamów i uzupełnij wszystkie braki", use_container_width=True):
                for _, row in low_stock_df.iterrows():
                    supabase.table("produkty").update({"liczba": UZUPELNIJ_DO}).eq("id", row['id']).execute()
                st.success("Wszystkie braki zostały uzupełnione!")
                st.rerun()

st.divider()

# --- STATYSTYKI OGÓLNE ---
if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Wszystkie Produkty", f"{int(df['liczba'].sum())} szt.")
    m2.metric("Wartość Magazynu", f"{df['Wartość'].sum():,.2f} PLN")
    m3.metric("Niskie stany", len(low_stock_df))
    csv = df.to_csv(index=False).encode('utf-8')
    m4.download_button("📥 Raport CSV", data=csv, file_name="magazyn.csv")

    if PLOTLY_AVAILABLE:
        c_plot1, c_plot2 = st.columns(2)
        with c_plot1:
            st.plotly_chart(px.pie(df, values='Wartość', names='Kategoria_Nazwa', title="Wartość wg kategorii"), use_container_width=True)
        with c_plot2:
            st.plotly_chart(px.bar(df.nlargest(10, 'liczba'), x='nazwa', y='liczba', title="Top 10 najliczniejszych"), use_container_width=True)

st.divider()

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["🛒 Zamówienia", "📦 Baza i Edycja Produktów", "📂 Kategorie"])

# --- ZAKŁADKA 1: ZAMÓWIENIA ---
with tab1:
    st.header("🛒 Nowe Zamówienie")
    if df.empty:
        st.info("Brak produktów w bazie.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_f, col_c = st.columns([1, 1])
        with col_f:
            lista_kat_nazw = ["Wszystkie"] + [k['nazwa'] for k in kategorie]
            wybrana_kat = st.selectbox("Filtruj wg kategorii", options=lista_kat_nazw, key="sel_kat_order")
            
            df_order = df[df['liczba'] > 0] if wybrana_kat == "Wszystkie" else df[(df['Kategoria_Nazwa'] == wybrana_kat) & (df['liczba'] > 0)]
            
            if df_order.empty:
                st.warning("Brak towaru w tej kategorii.")
            else:
                with st.form("order_form"):
                    sel_id = st.selectbox("Wybierz Produkt", options=df_order['id'].tolist(),
                                        format_func=lambda x: f"{df_order[df_order['id']==x]['nazwa'].values[0]} (Dostępne: {df_order[df_order['id']==x]['liczba'].values[0]})")
                    order_qty = st.number_input("Ilość", min_value=1, step=1)
                    if st.form_submit_button("➕ Dodaj do koszyka"):
                        p_info = df_order[df_order['id'] == sel_id].iloc[0]
                        st.session_state.cart.append({"id": int(sel_id), "nazwa": p_info['nazwa'], "cena": float(p_info['cena']), "ilosc": int(order_qty), "suma": float(order_qty * p_info['cena'])})
                        st.rerun()

        with col_c:
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.table(cart_df[['nazwa', 'ilosc', 'suma']])
                st.write(f"### Suma: {cart_df['suma'].sum():,.2f} PLN")
                if st.button("✅ Potwierdź zamówienie", use_container_width=True):
                    for item in st.session_state.cart:
                        actual = supabase.table("produkty").select("liczba").eq("id", item['id']).single().execute()
                        supabase.table("produkty").update({"liczba": actual.data['liczba'] - item['ilosc']}).eq("id", item['id']).execute()
                    st.success("Sprzedano!")
                    st.session_state.cart = []
                    st.rerun()
                if st.button("🗑️ Wyczyść koszyk"):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.info("Koszyk jest pusty.")

# --- ZAKŁADKA 2: BAZA, EDYCJA I LISTA ---
with tab2:
    st.header("📦 Zarządzanie Produktami")
    
    # 1. Dodawanie
    with st.expander("➕ Dodaj nowy produkt"):
        with st.form("new_p"):
            n_nazwa = st.text_input("Nazwa produktu")
            n_liczba = st.number_input("Ilość", min_value=0)
            n_cena = st.number_input("Cena", min_value=0.0)
            n_kat = st.selectbox("Kategoria", options=[k['id'] for k in kategorie], format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
            if st.form_submit_button("Zapisz"):
                supabase.table("produkty").insert({"nazwa": n_nazwa, "liczba": n_liczba, "cena": n_cena, "kategoria_id": n_kat}).execute()
                st.rerun()

    if not df.empty:
        st.divider()
        # 2. Edycja
        st.subheader("📝 Edycja wybranego produktu")
        edit_id = st.selectbox("Wybierz produkt do zmiany danych", options=df['id'].tolist(), format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
        p_edit = df[df['id'] == edit_id].iloc[0]
        
        ce1, ce2, ce3, ce4 = st.columns([2, 1, 1, 1])
        with ce1: new_name = st.text_input("Zmień nazwę", value=p_edit['nazwa'])
        with ce2: new_stock = st.number_input("Zmień stan", value=int(p_edit['liczba']))
        with ce3: new_price = st.number_input("Zmień cenę", value=float(p_edit['cena']))
        with ce4:
            st.write("Akcja")
            if st.button("💾 Zapisz"):
                supabase.table("produkty").update({"nazwa": new_name, "liczba": new_stock, "cena": new_price}).eq("id", edit_id).execute()
                st.rerun()

        st.divider()
        # 3. Lista z wyszukiwarką
        st.subheader("🔍 Przeglądaj i Szukaj")
        szukaj = st.text_input("Wyszukaj produkt po nazwie...")
        df_view = df[df['nazwa'].str.contains(szukaj, case=False)] if szukaj else df

        def color_low(s):
            return ['background-color: #ffcccc; color: black' if v <= LIMIT_MINIMUM else '' for v in s]
        
        st.dataframe(df_view[['id', 'nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']].style.apply(color_low, subset=['liczba']), use_container_width=True)

        # 4. Usuwanie
        st.divider()
        if st.button(f"🗑️ Usuń produkt: {p_edit['nazwa']}"):
            supabase.table("produkty").delete().eq("id", edit_id).execute()
            st.rerun()

# --- ZAKŁADKA 3: KATEGORIE ---
with tab3:
    st.header("📂 Zarządzanie Kategoriami")
    c_a, c_b = st.columns(2)
    with c_a:
        with st.form("new_cat"):
            c_name = st.text_input("Nazwa kategorii")
            c_desc = st.text_area("Opis")
            if st.form_submit_button("Dodaj kategorię"):
                supabase.table("Kategorie").insert({"nazwa": c_name, "opis": c_desc}).execute()
                st.rerun()
    with c_b:
        for k in kategorie:
            with st.expander(f"📁 {k['nazwa']}"):
                st.write(f"Opis: {k['opis']}")
                if st.button("Usuń", key=f"del_{k['id']}"):
                    try:
                        supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                        st.rerun()
                    except:
                        st.error("Nie można usunąć – kategoria zawiera produkty!")
