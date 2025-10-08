// mcp_pedidos_node/server.mjs
import {
  Server
} from "@modelcontextprotocol/sdk/server/index.js";
import {
  StdioServerTransport
} from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema
} from "@modelcontextprotocol/sdk/types.js";   // 👈 import correcto para v0.6
import { z } from "zod";
import pkg from "pg";
import fs from "fs";

const { Pool } = pkg;

/* ---------- Logging ---------- */
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync("mcp_pedidos.log", line); } catch {}
  console.error(msg); // stderr (no stdout)
}

/* ---------- PG Pool ---------- */
function makePool() {
  const {
    PG_HOST = "localhost",
    PG_PORT = "5432",
    PG_DATABASE = "mi_base",
    PG_USER = "admin",
    PG_PASSWORD = "admin",
  } = process.env;

  log(`PG config -> host=${PG_HOST} port=${PG_PORT} db=${PG_DATABASE} user=${PG_USER}`);

  return new Pool({
    host: PG_HOST,
    port: Number(PG_PORT),
    database: PG_DATABASE,
    user: PG_USER,
    password: PG_PASSWORD,
  });
}
const pool = makePool();
pool.on("error", (err) => log(`PG Pool error: ${err?.message || err}`));

/* ---------- MCP Server ---------- */
const server = new Server(
  { name: "mcp-pedidos", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

/* ---------- Definición de tools ---------- */
const TOOLS = [
  {
    name: "pedidos_estado_por_id",
    description: "Devuelve el estado del pedido por ID.",
    inputSchema: {
      type: "object",
      properties: { id: { type: "integer", minimum: 0 } },
      required: ["id"]
    }
  },
  {
    name: "pedidos_crear",
    description: "Crea un nuevo pedido y devuelve el ID generado.",
    inputSchema: {
      type: "object",
      properties: {
        cliente: { type: "string", minLength: 1 },
        monto: { type: "number", exclusiveMinimum: 0 }
      },
      required: ["cliente", "monto"]
    }
  }
];

const schemaEstadoPorId = z.object({ id: z.number().int().nonnegative() });
const schemaCrear = z.object({ cliente: z.string().min(1), monto: z.number().positive() });

/* ---------- Registrar handlers ---------- */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  log("tools/list solicitado");
  return { tools: TOOLS };
});

server.setRequestHandler(CallToolRequestSchema, async (params) => {
  // Normaliza estructura para SDK 0.6 + gateway Python
  const inner = params?.params || params || {};
  const toolName =
    inner.name ||
    inner.toolName ||
    inner.tool?.name ||
    inner.method ||
    undefined;

  const argsRaw =
    inner.arguments ||
    inner.args ||
    inner.parameters ||
    {};

  log(`tools/call RAW params=${JSON.stringify(params)}`);
  log(`tools/call inner=${JSON.stringify(inner)}`);
  log(`tools/call toolName=${toolName} args=${JSON.stringify(argsRaw)}`);

  if (!toolName) {
    const msg = `Tool no soportada: undefined (no se encontró campo "name")`;
    log(msg);
    return { content: [{ type: "text", text: msg }], isError: true };
  }

  // ---- pedidos_estado_por_id ----
  if (toolName === "pedidos_estado_por_id") {
    const args = schemaEstadoPorId.parse(argsRaw);
    const client = await pool.connect();
    try {
      const { rows } = await client.query(
        "SELECT id, cliente, monto, estado FROM pedidos WHERE id = $1",
        [args.id]
      );
      const result = rows.length
        ? { id: rows[0].id, cliente: rows[0].cliente, monto: Number(rows[0].monto), estado: rows[0].estado }
        : { id: args.id, mensaje: "Pedido no encontrado" };

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: { result }
      };
    } finally {
      client.release();
    }
  }

  // ---- pedidos_crear ----
  if (toolName === "pedidos_crear") {
    const args = schemaCrear.parse(argsRaw);
    const client = await pool.connect();
    try {
      const { rows } = await client.query(
        "INSERT INTO pedidos (cliente, monto, estado) VALUES ($1, $2, 'pendiente') RETURNING id",
        [args.cliente, args.monto]
      );
      const id = rows[0]?.id;
      const result = { id, cliente: args.cliente, monto: args.monto, estado: "pendiente" };
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        structuredContent: { result }
      };
    } finally {
      client.release();
    }
  }

  const msg = `Tool no soportada: ${toolName}`;
  log(msg);
  return { content: [{ type: "text", text: msg }], isError: true };
});



/* ---------- Start (stdio) ---------- */
try {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  log("✅ MCP Pedidos conectado por stdio y listo (SDK 0.6.1, schemas).");
} catch (e) {
  log(`❌ Fallo iniciando MCP Pedidos: ${e?.message || e}`);
  process.exit(1);
}
