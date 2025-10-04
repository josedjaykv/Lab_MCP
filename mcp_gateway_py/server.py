import os, sys, asyncio
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

mcp = FastMCP("mcp-gateway")

def log(s: str):
    print(s, file=sys.stderr, flush=True)

class Backend:
    def __init__(self, command: list[str], cwd: str | None = None, env: dict | None = None):
        self.command = command
        self.cwd = cwd
        self.env = env
        self._ctx = None
        self._session: ClientSession | None = None

    async def start(self):
        params = StdioServerParameters(
            command=self.command[0],
            args=self.command[1:],
            cwd=self.cwd,
            env=self.env
        )
        self._ctx = stdio_client(params)
        read, write = await self._ctx.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        log(f"Backend started: {' '.join(self.command)} (cwd={self.cwd})")

    async def stop(self):
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._ctx is not None:
            await self._ctx.__aexit__(None, None, None)
            self._ctx = None

    async def call_tool(self, name: str, arguments: Dict[str, Any] | None = None):
        if self._session is None:
            raise RuntimeError("Backend no inicializado")
        arguments = arguments or {}
        result = await self._session.call_tool(name, arguments)
        if getattr(result, "structuredContent", None) is not None:
            return result.structuredContent
        return {"content": [c.model_dump() for c in result.content]}

async def main():
    # Log de ENV efectivo
    log("=== ENV RECIBIDO POR GATEWAY ===")
    for k in ["PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD", "PG_DATABASE"]:
        log(f"{k}={os.getenv(k)}")
    log("================================")

    py = sys.executable
    root = os.path.dirname(os.path.abspath(__file__))   # .../mcp_gateway_py
    project_root = os.path.dirname(root)                # raíz del proyecto

    ventas_path  = os.path.join(project_root, "mcp_ventas_py",  "server.py")
    pedidos_path = os.path.join(project_root, "mcp_pedidos_py", "server.py")

    env = dict(os.environ)

    ventas = Backend([py, "-u", ventas_path], cwd=os.path.dirname(ventas_path), env=env)
    pedidos = Backend([py, "-u", pedidos_path], cwd=os.path.dirname(pedidos_path), env=env)

    await ventas.start()
    await pedidos.start()

    @mcp.tool()
    async def ventas_total_mes_anterior() -> float:
        data = await ventas.call_tool("ventas_total_mes_anterior")
        if isinstance(data, dict) and "result" in data:
            return float(data["result"])
        try:
            parts = data.get("content", [])
            for p in parts:
                if p.get("type") == "text":
                    return float(p.get("text"))
        except Exception:
            pass
        return 0.0

    @mcp.tool()
    async def ventas_por_dia(n: int = 30) -> list[dict]:
        data = await ventas.call_tool("ventas_por_dia", {"n": n})
        if isinstance(data, dict) and "result" in data and isinstance(data["result"], list):
            return data["result"]
        return []

    @mcp.tool()
    async def total_ventas_ultimo_mes() -> float:
        return await ventas_total_mes_anterior()

    @mcp.tool()
    async def ventas_ultimos_ndias(n: int = 30) -> list[dict]:
        return await ventas_por_dia(n)

    @mcp.tool()
    async def pedidos_crear(cliente: str, monto: float) -> dict:
        data = await pedidos.call_tool("pedidos_crear", {"cliente": cliente, "monto": monto})
        return data.get("result", data)

    @mcp.tool()
    async def pedidos_estado_por_id(id: int) -> dict:
        data = await pedidos.call_tool("pedidos_estado_por_id", {"id": id})
        return data.get("result", data)

    log("MCP Gateway escuchando por stdio...")
    # IMPORTANTE: como ya estamos en asyncio, usamos la versión async del servidor
    await mcp.run_stdio_async()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
