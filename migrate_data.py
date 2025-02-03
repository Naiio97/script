from app import app, db
from models import Server, Certifikat

def migrate_data():
    with app.app_context():
        # Získáme všechny unikátní servery z certifikátů
        existing_servers = db.session.query(Certifikat.server.distinct()).all()
        
        # Pro každý server vytvoříme záznam v tabulce Server
        for server_tuple in existing_servers:
            server_name = server_tuple[0]
            if server_name:  # Kontrola na prázdné hodnoty
                # Zkontrolujeme, zda server už neexistuje
                existing = Server.query.filter_by(nazev=server_name).first()
                if not existing:
                    new_server = Server(nazev=server_name)
                    db.session.add(new_server)
        
        db.session.commit()
        print("Migrace dokončena")

if __name__ == "__main__":
    migrate_data() 