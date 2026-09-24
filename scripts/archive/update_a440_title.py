import sqlite3

conn = sqlite3.connect('data/tta_ratings.db')
conn.execute("UPDATE players SET title = 'WC' WHERE LOWER(name) = 'a440'")
conn.commit()
row = conn.execute("SELECT name, title FROM players WHERE LOWER(name) = 'a440'").fetchone()
print("Updated a440 row:", row)
conn.close()
