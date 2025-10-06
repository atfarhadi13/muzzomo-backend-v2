import os
import sqlite3

SQLDATA_DIR = os.path.join(os.path.dirname(__file__), 'SQLDATA')
DB_PATH = os.path.join(os.path.dirname(__file__), 'db.sqlite3')

def load_sql_file(sql_file):
    print(f"Loading {sql_file}...")
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            conn.executescript(sql_script)
    except sqlite3.Error as e:
        print(f"SQL error: {e}")
    finally:
        conn.close()

def print_table_counts():
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        for table in [
            "professional_professional",
            "professional_professionalservice"
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"{table}: {count} rows")
            except sqlite3.Error as e:
                print(f"Error counting rows in {table}: {e}")
    finally:
        conn.close()

def check_prerequisites():
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM user_customuser")
        user_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM service_service")
        service_count = cursor.fetchone()[0]
        print(f"Found {service_count} services")
        
        return user_count > 0 and service_count > 0
    except sqlite3.Error as e:
        print(f"Error checking prerequisites: {e}")
        return False
    finally:
        conn.close()

def main():
    files_order = [
        'service_seed_data.sql',
        'insert_users.sql',
        'insert_professional.sql'
    ]
    
    if not check_prerequisites():
        print("Warning: Required tables are empty!")

    for fname in files_order:
        fpath = os.path.join(SQLDATA_DIR, fname)
        if os.path.exists(fpath):
            load_sql_file(fpath)
    
    print_table_counts()

if __name__ == "__main__":
    main()
