import os, psycopg2
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
mcp = FastMCP('mcp-ventas')

def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        database=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )

@mcp.tool()
def ventas_total_mes_anterior() -> float:
    """Suma total de ventas del mes calendario anterior."""
    sql = """
    SELECT COALESCE(SUM(monto),0) AS total
      FROM ventas
     WHERE fecha >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
       AND fecha <  date_trunc('month', CURRENT_DATE);
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        (total,) = cur.fetchone()
        return float(total)

@mcp.tool()
def ventas_por_dia(n: int = 30) -> list[dict]:
    """Serie diaria de ventas para los últimos n días."""
    sql = """
    SELECT fecha, SUM(monto) AS total_dia
      FROM ventas
     WHERE fecha >= CURRENT_DATE - INTERVAL %s
     GROUP BY fecha
     ORDER BY fecha;
    """
    interval = f'{n} days'
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (interval,))
        rows = cur.fetchall()
        return [{'fecha': str(r[0]), 'total_dia': float(r[1])} for r in rows]

# Aliases opcionales para compatibilidad
@mcp.tool()
def total_ventas_ultimo_mes() -> float:
    return ventas_total_mes_anterior()

@mcp.tool()
def ventas_ultimos_ndias(n: int = 30) -> list[dict]:
    return ventas_por_dia(n)

if __name__ == "__main__":
    import datetime, sys, traceback
    try:
        with open("mcp_ventas_boot.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] MCP Ventas iniciado. CWD={os.getcwd()}\n")
        print("MCP Ventas esperando cliente por stdio", file=sys.stderr, flush=True)
        mcp.run(transport="stdio")
    except Exception:
        with open("mcp_ventas_error.log", "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
