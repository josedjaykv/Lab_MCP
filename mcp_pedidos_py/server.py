import os, psycopg2
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
mcp = FastMCP('mcp-pedidos')

def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        database=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )

@mcp.tool()
def pedidos_estado_por_id(id: int) -> dict:
    """Devuelve el estado del pedido por ID."""
    sql = "SELECT id, cliente, monto, estado FROM pedidos WHERE id = %s"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (id,))
        row = cur.fetchone()
        if not row:
            return {"id": id, "mensaje": "Pedido no encontrado"}
        return {"id": row[0], "cliente": row[1], "monto": float(row[2]), "estado": row[3]}

@mcp.tool()
def pedidos_crear(cliente: str, monto: float) -> dict:
    """Crea un nuevo pedido y devuelve el ID generado."""
    sql = "INSERT INTO pedidos (cliente, monto, estado) VALUES (%s, %s, 'pendiente') RETURNING id;"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (cliente, monto))
        (pedido_id,) = cur.fetchone()
        conn.commit()
        return {"id": pedido_id, "cliente": cliente, "monto": monto, "estado": "pendiente"}

if __name__ == "__main__":
    import datetime, sys, traceback
    try:
        with open("mcp_pedidos_boot.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] MCP Pedidos iniciado. CWD={os.getcwd()}\n")
        print("MCP Pedidos esperando cliente por stdio", file=sys.stderr, flush=True)
        mcp.run(transport="stdio")
    except Exception:
        with open("mcp_pedidos_error.log", "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
