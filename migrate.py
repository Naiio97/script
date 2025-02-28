from app import app, db
from models import Server, Certifikat
import sqlite3

def migrate_database():
    with app.app_context():
        try:
            # Přidáme sloupec popis do tabulky server
            conn = sqlite3.connect('certifikaty.db')
            cursor = conn.cursor()
            cursor.execute('ALTER TABLE server ADD COLUMN popis TEXT')
            conn.commit()
            conn.close()
            print("Migrace proběhla úspěšně")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Sloupec již existuje")
            else:
                print(f"Chyba při migraci: {e}")

if __name__ == "__main__":
    migrate_database() 