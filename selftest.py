import os, psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.getenv("PG_HOST"),
    port=os.getenv("PG_PORT"),
    user=os.getenv("PG_USER"),
    password=os.getenv("PG_PASSWORD"),
    dbname=os.getenv("PG_DATABASE")
)
cur=conn.cursor()
cur.execute("""
            SELECT COALESCE(SUM(monto),0) as Total 
            FROM ventas
            WHERE fecha >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
            AND fecha < date_trunc('month', CURRENT_DATE);
            """)
print("Total ventas del mes pasado:", cur.fetchone()[0])
cur.close()
conn.close()