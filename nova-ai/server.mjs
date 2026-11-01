import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 3000);
const API_KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5-5";
const API_VERSION = process.env.ANTHROPIC_VERSION || "2023-06-01";
const WINDOW_MS = 10 * 60 * 1000;
const MAX_REQUESTS = 20;
const hits = new Map();
const SYSTEM_PROMPT = `Ты — NOVA AI, дружелюбный ИИ-ассистент. Отвечай понятно и полезно на языке пользователя. Помогай с программированием на Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, PHP, Ruby, Swift, Kotlin, HTML, CSS, SQL и других языках. При написании кода указывай язык, используй блоки кода, объясняй важные части и не утверждай, что код проверен или запущен, если это не так.`;
function send(res, status, data) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
  res.end(JSON.stringify(data));
}
function rateLimited(req) {
  const ip = req.socket.remoteAddress || "unknown";
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < WINDOW_MS);
  if (recent.length >= MAX_REQUESTS) { hits.set(ip, recent); return true; }
  recent.push(now); hits.set(ip, recent); return false;
}
async function readJson(req) {
  let body = "";
  for await (const chunk of req) { body += chunk; if (body.length > 100_000) throw new Error("Слишком большой запрос."); }
  return JSON.parse(body || "{}");
}
const mime = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml" };
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://" + (req.headers.host || "localhost"));
    if (req.method === "POST" && url.pathname === "/api/chat") {
      if (!API_KEY) return send(res, 503, { error: "На сервере не настроен ANTHROPIC_API_KEY. Добавь ключ в .env и перезапусти сервер." });
      if (rateLimited(req)) return send(res, 429, { error: "Слишком много запросов. Подожди несколько минут." });
      const body = await readJson(req);
      if (!Array.isArray(body.messages) || body.messages.length === 0) return send(res, 400, { error: "Добавь сообщение и попробуй снова." });
      const messages = body.messages.slice(-20).map(m => {
        if (!m || !["user", "assistant"].includes(m.role) || typeof m.content !== "string") throw new Error("Некорректный формат истории чата.");
        return { role: m.role, content: m.content.slice(0, 12000) };
      });
      if (messages[messages.length - 1].role !== "user") return send(res, 400, { error: "Последнее сообщение должно быть от пользователя." });
      const upstream = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST", headers: { "x-api-key": API_KEY, "anthropic-version": API_VERSION, "content-type": "application/json" },
        body: JSON.stringify({ model: MODEL, max_tokens: 3000, system: SYSTEM_PROMPT, messages }), signal: AbortSignal.timeout(90000)
      });
      const result = await upstream.json().catch(() => ({}));
      if (!upstream.ok) {
        console.error("Anthropic API error:", upstream.status, result?.error?.type || "unknown");
        const message = upstream.status === 401 ? "Claude не принял API-ключ. Проверь ключ." : upstream.status === 429 ? "У API достигнут лимит запросов. Попробуй позже." : "Claude API вернул ошибку. Проверь модель, доступ и лимиты.";
        return send(res, upstream.status === 429 ? 429 : 502, { error: message });
      }
      const reply = (result.content || []).filter(b => b.type === "text").map(b => b.text).join("\n").trim();
      return send(res, 200, { reply });
    }
    if (req.method !== "GET" && req.method !== "HEAD") return send(res, 405, { error: "Метод не поддерживается." });
    const requested = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
    const publicDir = path.resolve(__dirname, "public");
    const filePath = path.resolve(publicDir, "." + requested);
    if (!filePath.startsWith(publicDir + path.sep)) return send(res, 403, { error: "Доступ запрещён." });
    const data = await readFile(filePath);
    res.writeHead(200, { "Content-Type": mime[path.extname(filePath)] || "application/octet-stream", "X-Content-Type-Options": "nosniff" });
    if (req.method === "HEAD") return res.end();
    return res.end(data);
  } catch (error) { console.error("Server error:", error.message); return send(res, 400, { error: error.message || "Ошибка сервера." }); }
});
server.listen(PORT, () => { console.log("NOVA AI запущен: http://localhost:" + PORT); if (!API_KEY) console.log("Добавь ANTHROPIC_API_KEY в .env перед использованием чата."); });
