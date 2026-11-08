
import sqlite3

connection = sqlite3.connect("lexvoice.db")

tables = connection.execute("""
    SELECT name FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""").fetchall()

print("\n========== LEXVOICE DATABASE STRUCTURE ==========")

for (table,) in tables:
    print(f"\nTABLE: {table}")

    columns = connection.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    for column in columns:
        print(f"  {column[1]} ({column[2]})")

connection.close()

print("\n========== CHECK COMPLETED ==========")
