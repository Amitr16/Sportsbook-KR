
# smoke_pg.py — minimal check the shim works end-to-end
from db_compat import connect
import os

dsn = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/goalserve_sportsbook")
conn = connect(dsn, autocommit=True)

conn.execute("DROP TABLE IF EXISTS shim_demo")
conn.execute("CREATE TABLE shim_demo(id SERIAL PRIMARY KEY, enabled BOOLEAN, name TEXT)")
conn.execute("INSERT INTO shim_demo(enabled, name) VALUES(?, ?)", (1, "a"))
conn.execute("INSERT INTO shim_demo(enabled, name) VALUES(?, ?)", (0, "b"))
cur = conn.execute("SELECT * FROM shim_demo WHERE enabled = ?", (1,))
print("Rows with enabled=1:", cur.fetchall())
print("OK")
