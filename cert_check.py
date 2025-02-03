import pandas as pd
from datetime import datetime, timedelta
import os

def nacti_excel(cesta_k_souboru):
    # Načtení Excel souboru
    try:
        df = pd.read_excel(cesta_k_souboru)
        
        # Vyplnění prázdných hodnot hodnotou z předchozího řádku
        df['Server'] = df['Server'].fillna(method='ffill')
        df['Cesta'] = df['Cesta'].fillna(method='ffill')
        
        print("\nNázvy sloupců v Excel souboru:")
        print(df.columns.tolist())
        
        # Pro debugování vypíšeme prvních pár řádků
        print("\nPrvních pár řádků dat:")
        print(df.head())
        
        return df
    except Exception as e:
        print(f"Chyba při načítání Excel souboru: {e}")
        return None

def zkontroluj_certifikaty(df):
    nazev_sloupce_expirace = 'Expirace'
    
    try:
        # Vytvoříme kopii
        df = df.copy()
        
        # Seznam hodnot k ignorování
        ignorovat = ["Neřešíme", "Neřešime", "Automaticky", "Automacticky", 
                    "?????", "Expirace", "Expirace ", ""]
        
        # Odfiltrujeme nežádoucí hodnoty
        df = df[~df[nazev_sloupce_expirace].astype(str).isin(ignorovat)]
        
        # Převedeme na datetime a ignorujeme chyby
        df[nazev_sloupce_expirace] = pd.to_datetime(
            df[nazev_sloupce_expirace], 
            errors='coerce'  # Neplatná data budou NaT
        )
        
        # Odstraníme řádky s NaT (neplatná data)
        df = df.dropna(subset=[nazev_sloupce_expirace])
        
        if df.empty:
            return df
        
        # Získání aktuálního data
        dnes = pd.Timestamp.now().date()
        za_dva_mesice = dnes + timedelta(days=60)
        
        # Filtrování certifikátů
        koncici_certifikaty = df[
            (df[nazev_sloupce_expirace].dt.date > dnes) & 
            (df[nazev_sloupce_expirace].dt.date <= za_dva_mesice)
        ]
        
        return koncici_certifikaty
    except Exception as e:
        print(f"\nChyba při zpracování dat: {e}")
        return pd.DataFrame()

def vypis_certifikaty(koncici_certifikaty):
    if koncici_certifikaty.empty:
        print("Žádné certifikáty nekončí v příštích dvou měsících.")
        return

    print("\nCertifikáty končící v příštích dvou měsících:")
    print("-" * 50)
    
    for _, radek in koncici_certifikaty.iterrows():
        print(f"Server: {radek['Server']}")
        print(f"Cesta: {radek['Cesta']}")
        print(f"Název certifikátu: {radek['Název certifikátu']}")
        print(f"Expirace: {radek['Expirace'].strftime('%d.%m.%Y')}")
        print("-" * 50)

def main():
    # Vypíše aktuální pracovní adresář
    print(f"Aktuální adresář: {os.getcwd()}")
    
    excel_soubor = "./certy_uat.xlsx"
    # Načtení dat
    df = nacti_excel(excel_soubor)
    if df is None:
        return
    
    # Kontrola certifikátů
    koncici_certifikaty = zkontroluj_certifikaty(df)
    
    # Výpis do konzole
    vypis_certifikaty(koncici_certifikaty)

if __name__ == "__main__":
    main() 