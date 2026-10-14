// Servidor local de teste: serve o index.html e /api/chat com o Gemini SIMULADO.
const http = require("http"), fs = require("fs"), path = require("path");
process.env.GEMINI_API_KEY = "teste";
const respostas = [];
global.fetch = async (url, opts) => {
  const body = JSON.parse(opts.body);
  const ultima = body.contents[body.contents.length - 1].parts[0].text.toLowerCase();
  let t = "Posso ajudar com Power BI. <script>alert(1)</script> **Fale com o Rodrigo**: [WhatsApp](https://wa.me/5511977019335)";
  if (ultima.includes("preço")) t = "O curso custa R$ 500.";
  if (ultima.includes("currículo")) t = "Claro! Veja o currículo dele: [_Rodrigo_Aiosa_CV 20";
  if (ultima.includes("erro")) return { ok: false, status: 400, json: async () => ({}) };
  return { ok: true, status: 200, json: async () => ({ candidates: [{ content: { parts: [{ text: t }] } }] }) };
};
const handler = require("../api/chat.js");
http.createServer((req, res) => {
  if (req.url.startsWith("/api/chat")) {
    let b = ""; req.on("data", d => b += d); req.on("end", () => {
      req.body = b ? JSON.parse(b) : undefined;
      res.status = c => { res.statusCode = c; return res; };
      res.json = o => { res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(o)); };
      handler(req, res);
    });
  } else {
    const f = req.url === "/" ? "index.html" : req.url.slice(1);
    const p = path.join(__dirname, "..", f);
    if (fs.existsSync(p)) { res.setHeader("Content-Type", f.endsWith(".jpg") ? "image/jpeg" : "text/html; charset=utf-8"); res.end(fs.readFileSync(p)); }
    else { res.statusCode = 404; res.end(); }
  }
}).listen(3111, () => console.log("ok"));
