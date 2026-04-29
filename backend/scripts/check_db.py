"""Check database status and create admin if needed"""
import sqlite3
import os

db_path = "./dev.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    print("Run: alembic upgrade head")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables ({len(tables)}):", tables[:20])

# Check users
if 'users' in tables:
    cursor.execute("SELECT id, email, role, is_active FROM users LIMIT 10")
    users = cursor.fetchall()
    print(f"\nUsers ({len(users)}):")
    for u in users:
        print(f"  {u[1]} | role={u[2]} | active={u[3]}")
else:
    print("\nNo users table - run migrations first!")

# Check tenants
if 'tenants' in tables:
    cursor.execute("SELECT id, name, plan FROM tenants LIMIT 5")
    tenants = cursor.fetchall()
    print(f"\nTenants ({len(tenants)}):")
    for t in tenants:
        print(f"  {t[1]} | plan={t[2]}")

conn.close()
