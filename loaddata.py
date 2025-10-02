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
        conn.executescript(sql_script)
    finally:
        conn.close()

def main():
    for fname in os.listdir(SQLDATA_DIR):
        if fname.endswith('.sql'):
            load_sql_file(os.path.join(SQLDATA_DIR, fname))

if __name__ == "__main__":
    main()
