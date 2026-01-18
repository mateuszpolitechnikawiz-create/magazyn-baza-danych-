import streamlit as st
from supabase import create_client, Client

# Konfiguracja połączenia z Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("📦 Zarządzanie Magazynem")

# --- ZAKŁADKI ---
tab1, tab2 = st.tabs(["Kategorie", "Produkty"])

# --- TABELA: KATEGORIE ---
with tab1:
    st.header("Zarządzanie Kategoriami")
    
    # Dodawanie kategorii
    with st.expander("➕ Dodaj nową kategorię"):
        with st.form("add_category"):
            nazwa_kat = st.text_input("Nazwa kategorii")
            opis_kat = st.text_area("Opis")
            submitted_kat = st.form_submit_button("Zapisz kategorię")
            
            if submitted_kat and nazwa_kat:
                data = {"nazwa": nazwa_kat, "opis": opis_kat}
                supabase.table("Kategorie").insert(data).execute()
                st.success("Dodano kategorię!")
                st.rerun()

    # Wyświetlanie i Usuwanie
    res_kat = supabase.table("Kategorie").select("*").execute()
    kategorie = res_kat.data
    
    if kategorie:
        st.table(kategorie)
        kat_to_del = st.selectbox("Wybierz kategorię do usunięcia", 
                                  options=[k['id'] for k in kategorie],
                                  format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
        if st.button("🗑️ Usuń kategorię", key="del_kat"):
            supabase.table("Kategorie").delete().eq("id", kat_to_del).execute()
            st.success("Usunięto!")
            st.rerun()
    else:
        st.info("Brak kategorii w bazie.")

# --- TABELA: PRODUKTY ---
with tab2:
    st.header("Zarządzanie Produktami")
    
    # Dodawanie produktu
    with st.expander("➕ Dodaj nowy produkt"):
        if not kategorie:
            st.warning("Najpierw dodaj kategorię!")
        else:
            with st.form("add_product"):
                nazwa_prod = st.text_input("Nazwa produktu")
                liczba = st.number_input("Liczba (ilość)", step=1)
                cena = st.number_input("Cena", min_value=0.0, format="%.2f")
                kat_id = st.selectbox("Kategoria", 
                                      options=[k['id'] for k in kategorie],
                                      format_func=lambda x: next(k['nazwa'] for k in kategorie if k['id'] == x))
                
                submitted_prod = st.form_submit_button("Zapisz produkt")
                
                if submitted_prod and nazwa_prod:
                    prod_data = {
                        "nazwa": nazwa_prod, 
                        "liczba": liczba, 
                        "Cena": cena, # Wielka litera zgodnie ze schematem
                        "kategoria_id": kat_id
                    }
                    supabase.table("produkty").insert(prod_data).execute()
                    st.success("Dodano produkt!")
                    st.rerun()

    # Wyświetlanie i Usuwanie
    res_prod = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
    produkty = res_prod.data
    
    if produkty:
        # Przekształcenie danych do ładniejszej tabeli
        display_data = []
        for p in produkty:
            display_data.append({
                "ID": p['id'],
                "Nazwa": p['nazwa'],
                "Ilość": p['liczba'],
                "Cena": p['Cena'],
                "Kategoria": p['Kategorie']['nazwa'] if p['Kategorie'] else "Brak"
            })
        st.table(display_data)
        
        prod_to_del = st.selectbox("Wybierz produkt do usunięcia", 
                                   options=[p['id'] for p in produkty],
                                   format_func=lambda x: next(p['nazwa'] for p in produkty if p['id'] == x))
        if st.button("🗑️ Usuń produkt", key="del_prod"):
            supabase.table("produkty").delete().eq("id", prod_to_del).execute()
            st.success("Usunięto produkt!")
            st.rerun()
    else:
        st.info("Brak produktów w bazie.")
