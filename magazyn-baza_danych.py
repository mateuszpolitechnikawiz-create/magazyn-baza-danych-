import streamlit as st
import pandas as pd
from supabase import create_client, Client

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

# --- KONFIGURACJA PROGÓW ---
LIMIT_MINIMUM = 5      # Poniżej tej ilości produkt jest "krytyczny"
UZUPELNIJ_DO = 50      # Do tej ilości uzupełniamy przyciskiem

st.title("📦 Inteligentny Magazyn WMS")

# --- SEKCA ANALIZY I AUTO-ZAMAWIANIA ---
if not df.empty:
    low_stock_df = df[df['liczba'] <= LIMIT_MINIMUM]
    
    c1, c2, c3 = st.columns([2, 1, 1])
    
    with c1:
        if not low_stock_df.empty:
            st.warning(f"⚠️ Znaleziono **{len(low_stock_df)}** produktów wymagających uzupełnienia!")
        else:
            st.success("✅ Wszystkie stany magazynowe są w normie.")
            
    with c2:
        if not low_stock_df.empty:
            if st.button("🚀 Zamów i uzupełnij braki", use_container_width=True):
                with st.spinner("Aktualizowanie stanów..."):
                    for _, row in low_stock_df.iterrows():
                        supabase.table("produkty").update({"liczba": UZUPELNIJ_DO}).eq("id", row['id']).execute()
                    st.success(f"Uzupełniono zapasy do poziomu {UZUPELNIJ_DO} sztuk!")
                    st.rerun()

st.divider()

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["🛒 Zamówienia", "📦 Baza i Edycja", "📂 Kategorie"])

# --- ZAKŁADKA 1: ZAMÓWIENIA ---
with tab1:
    st.header("🛒 Kreator Zamówienia")
    if df.empty:
        st.info("Brak produktów.")
    else:
        if 'cart' not in st.session_state:
            st.session_state.cart = []

        col_f, col_c = st.columns([1, 1])
        with col_f:
            lista_kat = ["Wszystkie"] + [k['nazwa'] for k in kategorie]
            wybrana_kat = st.selectbox("Kategoria", options=lista_kat)
            
            df_f = df[df['liczba'] > 0] if wybrana_kat == "Wszystkie" else df[(df['Kategoria_Nazwa'] == wybrana_kat) & (df['liczba'] > 0)]
            
            with st.form("cart_form"):
                sel_id = st.selectbox("Produkt", options=df_f['id'].tolist(), 
                                    format_func=lambda x: f"{df_f[df_f['id']==x]['nazwa'].values[0]} (Stan: {df_f[df_f['id']==x]['liczba'].values[0]})")
                qty = st.number_input("Ilość", min_value=1, step=1)
                if st.form_submit_button("➕ Dodaj"):
                    p = df_f[df_f['id'] == sel_id].iloc[0]
                    st.session_state.cart.append({"id": int(sel_id), "nazwa": p['nazwa'], "cena": float(p['cena']), "ilosc": int(qty), "suma": float(qty * p['cena'])})
                    st.rerun()
        with col_c:
            if st.session_state.cart:
                st.table(pd.DataFrame(st.session_state.cart)[['nazwa', 'ilosc', 'suma']])
                if st.button("✅ Potwierdź sprzedaż"):
                    for i in st.session_state.cart:
                        act = supabase.table("produkty").select("liczba").eq("id", i['id']).single().execute()
                        supabase.table("produkty").update({"liczba": act.data['liczba'] - i['ilosc']}).eq("id", i['id']).execute()
                    st.session_state.cart = []
                    st.rerun()

# --- ZAKŁADKA 2: BAZA I EDYCJA ---
with tab2:
    st.header("📦 Zarządzanie i Inwentaryzacja")
    
    # 1. Podgląd z kolorami
    st.subheader("Aktualny stan magazynowy")
    def color_stock(val):
        color = 'red' if val <= LIMIT_MINIMUM else 'white'
        return f'background-color: {color}; color: {"black" if val <= LIMIT_MINIMUM else "white"}'
    
    st.dataframe(df[['nazwa', 'Kategoria_Nazwa', 'liczba', 'cena', 'Wartość']]
                 .style.applymap(color_stock, subset=['liczba']), use_container_width=True)
    
    # 2. Edycja
    st.divider()
    st.subheader("📝 Edytuj wybrany produkt")
    edit_id = st.selectbox("Produkt do zmiany", options=df['id'].tolist(), format_func=lambda x: df[df['id']==x]['nazwa'].values[0])
    p_edit = df[df['id'] == edit_id].iloc[0]
    
    ce1, ce2, ce3 = st.columns(3)
    new_n = ce1.text_input("Nowa nazwa", value=p_edit['nazwa'])
    new_s = ce2.number_input("Nowy stan", value=int(p_edit['liczba']))
    new_p = ce3.number_input("Nowa cena", value=float(p_edit['cena']))
    
    if st.button("💾 Zapisz zmiany"):
        supabase.table("produkty").update({"nazwa": new_n, "liczba": new_s, "cena": new_p}).eq("id", edit_id).execute()
        st.success("Zaktualizowano!")
        st.rerun()

    # 3. Usuwanie
    st.divider()
    if st.button("🗑️ Usuń zaznaczony powyżej produkt", type="secondary"):
        supabase.table("produkty").delete().eq("id", edit_id).execute()
        st.rerun()

# --- ZAKŁADKA 3: KATEGORIE ---
with tab3:
    st.header("📂 Kategorie")
    with st.form("kat_form"):
        c_n = st.text_input("Nazwa nowej kategorii")
        if st.form_submit_button("Dodaj"):
            supabase.table("Kategorie").insert({"nazwa": c_n}).execute()
            st.rerun()
    
    for k in kategorie:
        c1, c2 = st.columns([4, 1])
        c1.write(f"📁 {k['nazwa']}")
        if c2.button("Usuń", key=f"k_{k['id']}"):
            try:
                supabase.table("Kategorie").delete().eq("id", k['id']).execute()
                st.rerun()
            except:
                st.error("Kategoria zajęta!")
