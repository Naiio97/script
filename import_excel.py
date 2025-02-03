import pandas as pd
import sqlite3
from cert_check import vytvor_databazi

def importuj_z_excelu(excel_soubor):
    # Načtení dat z Excelu
    df = pd.read_excel(excel_soubor)
    
    # Připojení k databázi
    with sqlite3.connect('certifikaty.db') as conn:
        # Import dat do databáze
        df.to_sql('certifikaty', conn, if_exists='append', index=False)

if __name__ == "__main__":
    # Nejdřív vytvoříme databázi
    vytvor_databazi()
    
    # Pak importujeme data
    importuj_z_excelu('./certy_uat.xlsx') 