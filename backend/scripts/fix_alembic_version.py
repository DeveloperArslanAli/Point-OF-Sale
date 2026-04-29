import psycopg2
import sys

# Connection details from .env
DB_USER = "postgres"
DB_PASS = "1234"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "retail_pos_db"

def fix_alembic_version_table():
    try:
        con = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = con.cursor()
        
        print("Checking/Creating alembic_version table...")
        # Check if table exists
        cur.execute("SELECT to_regclass('public.alembic_version')")
        if cur.fetchone()[0] is None:
            print("Table does not exist. Creating it with VARCHAR(255)...")
            cur.execute("CREATE TABLE alembic_version (version_num VARCHAR(255) NOT NULL, PRIMARY KEY (version_num))")
        else:
            print("Table exists. Altering it...")
            cur.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")
            
        con.commit()
        print("Successfully fixed alembic_version table.")
            
        cur.close()
        con.close()
        
    except Exception as e:
        print(f"Error altering table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fix_alembic_version_table()
