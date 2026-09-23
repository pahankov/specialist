"""Reset database and create superuser."""
import os
from sqlalchemy import create_engine, text
from passlib.context import CryptContext

def main():
    db_path = './online_booking.db'
    
    # Delete file directly
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted {db_path}")
    
    # Use sync engine
    engine = create_engine(f'sqlite:///{db_path}')
    
    with engine.connect() as conn:
        # Create users table with raw SQL
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(255) UNIQUE,
                phone VARCHAR(20) UNIQUE,
                hashed_password VARCHAR(255),
                name VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'client',
                city_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                is_verified BOOLEAN DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE SET NULL
            )
        """))
        
        # Create master_profiles table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS master_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                description TEXT,
                avatar_url VARCHAR(500),
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """))
        
        # Create other required tables (simplified)
        for table in [
            'client_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE, no_show_count INTEGER DEFAULT 0, created_at DATETIME, updated_at DATETIME, FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)',
            'services (id INTEGER PRIMARY KEY AUTOINCREMENT, master_id INTEGER NOT NULL, name VARCHAR(200) NOT NULL, description TEXT, duration_minutes INTEGER NOT NULL, price REAL NOT NULL, is_active BOOLEAN DEFAULT 1, created_at DATETIME, updated_at DATETIME, FOREIGN KEY (master_id) REFERENCES master_profiles(id) ON DELETE CASCADE)',
            'appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, master_id INTEGER NOT NULL, service_id INTEGER NOT NULL, client_id INTEGER NOT NULL, appointment_date DATETIME NOT NULL, status VARCHAR(20) DEFAULT "pending", notes TEXT, created_at DATETIME, updated_at DATETIME, FOREIGN KEY (master_id) REFERENCES master_profiles(id) ON DELETE CASCADE, FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE, FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE)',
            'countries (id INTEGER PRIMARY KEY AUTOINCREMENT, code VARCHAR(3) UNIQUE NOT NULL, name_ru VARCHAR(100) NOT NULL, name_en VARCHAR(100) NOT NULL, phone_prefix VARCHAR(10) NOT NULL, is_active BOOLEAN DEFAULT 1)',
            'cities (id INTEGER PRIMARY KEY AUTOINCREMENT, country_id INTEGER NOT NULL, name_ru VARCHAR(200) NOT NULL, name_en VARCHAR(200), slug VARCHAR(200) NOT NULL, is_active BOOLEAN DEFAULT 1, FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE)',
        ]:
            name, rest = table.split(' (', 1)
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {name} ({rest}"))
        
        conn.commit()
        print("Tables created")
        
        # Now create superuser
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        result = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": "pahankov@mail.ru"})
        existing = result.fetchone()
        
        if not existing:
            hashed = pwd_context.hash("Sug@r2026!")
            conn.execute(
                text("""INSERT INTO users (name, email, phone, hashed_password, role, is_active, is_verified, created_at, updated_at) 
                        VALUES (:name, :email, :phone, :password, :role, :active, :verified, datetime('now'), datetime('now'))"""),
                {
                    "name": "Павел",
                    "email": "pahankov@mail.ru",
                    "phone": "+79615202311",
                    "password": hashed,
                    "role": "admin",
                    "active": True,
                    "verified": True,
                }
            )
            
            # Create master profile
            conn.execute(
                text("INSERT INTO master_profiles (user_id, description) VALUES (1, 'Суперпользователь')")
            )
            
            conn.commit()
            print("Superuser created: pahankov@mail.ru / Sug@r2026!")
        else:
            print("Superuser already exists")

main()
