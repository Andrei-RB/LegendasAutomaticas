import { createServer } from "node:http";

// Processo mínimo: responde ao healthcheck até o serviço de render existir.
createServer((req, res) => {
  const ok = req.url === "/health";
  res.writeHead(ok ? 200 : 404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ status: ok ? "healthy" : "not_found" }));
}).listen(3000, "0.0.0.0");
