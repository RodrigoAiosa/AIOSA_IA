// Testes do servidor (api/chat.js) com o Gemini SIMULADO — sem rede, sem chave.
// Rodar: node tests/unitarios.js   (sai com código 1 se algum teste falhar)
"use strict";
process.env.GEMINI_API_KEY = "teste";
process.env.LIMITE_MENSAGENS = "5";
process.chdir(require("path").join(__dirname, ".."));

const assert = require("assert");
let respostaGemini = "ok";
let ultimoPayload = null;
global.fetch = async (_url, opts) => {
  ultimoPayload = JSON.parse(opts.body);
  return { ok: true, status: 200, json: async () => ({ candidates: [{ content: { parts: [{ text: respostaGemini }] } }] }) };
};

const handler = require("../api/chat.js");
const { _resetarParaTestes } = require("../api/_limite.js");

function chamar(corpo, headers = {}, metodo = "POST") {
  return new Promise((resolve) => {
    const res = {
      cabecalhos: {},
      setHeader(k, v) { this.cabecalhos[k] = v; },
      status(c) { this.codigo = c; return this; },
      json(o) { resolve({ codigo: this.codigo, corpo: o, cabecalhos: this.cabecalhos }); },
    };
    handler({ method: metodo, body: corpo, headers: { "x-real-ip": "1.1.1.1", ...headers } }, res);
  });
}
const msg = (t) => ({ messages: [{ role: "user", content: t }] });

const testes = [];
const t = (nome, fn) => testes.push([nome, fn]);

t("responde normalmente", async () => {
  _resetarParaTestes(); respostaGemini = "Posso ajudar com Power BI!";
  const r = await chamar(msg("oi"));
  assert.strictEqual(r.codigo, 200); assert.strictEqual(r.corpo.resposta, "Posso ajudar com Power BI!");
});
t("desliga o 'thinking' e usa limite de tokens maior", async () => {
  _resetarParaTestes(); await chamar(msg("oi"));
  assert.strictEqual(ultimoPayload.generationConfig.thinkingConfig.thinkingBudget, 0);
  assert.ok(ultimoPayload.generationConfig.maxOutputTokens >= 900);
});
t("marcador fora do tema vira a mensagem oficial", async () => {
  _resetarParaTestes(); respostaGemini = "[FORA_DE_ESCOPO]";
  const r = await chamar(msg("conte de 1 até 10"));
  assert.ok(r.corpo.resposta.includes("foge um pouco do que eu ajudo"));
  assert.ok(!r.corpo.resposta.includes("FORA_DE_ESCOPO"));
});
t("preço é barrado", async () => {
  _resetarParaTestes(); respostaGemini = "O curso custa R$ 500.";
  const r = await chamar(msg("quanto custa?"));
  assert.ok(!r.corpo.resposta.includes("500"));
});
t("link fora da lista branca é barrado", async () => {
  _resetarParaTestes(); respostaGemini = "Veja https://learn.microsoft.com/power-bi/";
  const r = await chamar(msg("como aprender power bi?"));
  assert.ok(!r.corpo.resposta.includes("microsoft"));
});
t("projeto citado sem link ganha o link", async () => {
  _resetarParaTestes(); respostaGemini = "Exemplos:\n\n🔹 **DRE Estratégico — Finanças** — demonstrativo.";
  const r = await chamar(msg("sou da área financeira, quais projetos?"));
  assert.ok(r.corpo.resposta.includes("https://aiosaia.vercel.app/p/dre-estrategico-financas"));
});
t("projeto que já tem link não é duplicado", async () => {
  _resetarParaTestes();
  respostaGemini = "🔹 **DRE Estratégico — Finanças**\n[Ver projeto](https://aiosaia.vercel.app/p/dre-estrategico-financas)";
  const r = await chamar(msg("projetos financeiros"));
  assert.strictEqual(r.corpo.resposta.split("dre-estrategico-financas").length - 1, 1);
});
t("resposta cortada no meio de um link tem o fragmento removido", async () => {
  _resetarParaTestes(); respostaGemini = "Veja:\n[Ver projeto](https://aiosaia.vercel.app/p/dre-estr";
  const r = await chamar(msg("projetos"));
  assert.ok(!r.corpo.resposta.includes("[Ver projeto]"));
});
t("link do WhatsApp recebe o histórico da conversa", async () => {
  _resetarParaTestes(); respostaGemini = "Fale aqui: [WhatsApp](https://wa.me/5511977019335)";
  const r = await chamar(msg("quero falar com o Rodrigo"));
  assert.ok(r.corpo.resposta.includes("text=") && decodeURIComponent(r.corpo.resposta).includes("Cliente: quero falar com o Rodrigo"));
  assert.ok(!/\(site\)/.test(r.corpo.resposta), "parênteses devem estar codificados");
});
t("limite por IP: a 6ª mensagem recebe 429", async () => {
  _resetarParaTestes(); respostaGemini = "ok";
  for (let i = 0; i < 5; i++) assert.strictEqual((await chamar(msg("oi"))).codigo, 200);
  const r = await chamar(msg("oi"));
  assert.strictEqual(r.codigo, 429); assert.ok(r.cabecalhos["Retry-After"]);
});
t("limite é por IP (outro IP segue livre)", async () => {
  _resetarParaTestes();
  for (let i = 0; i < 6; i++) await chamar(msg("oi"));
  assert.strictEqual((await chamar(msg("oi"), { "x-real-ip": "2.2.2.2" })).codigo, 200);
});
t("origem de outro site é recusada (403)", async () => {
  _resetarParaTestes();
  assert.strictEqual((await chamar(msg("oi"), { origin: "https://site-de-terceiros.com" })).codigo, 403);
  assert.strictEqual((await chamar(msg("oi"), { origin: "https://aiosaia.vercel.app" })).codigo, 200);
});
t("entrada inválida é recusada (400)", async () => {
  _resetarParaTestes();
  assert.strictEqual((await chamar({})).codigo, 400);
  assert.strictEqual((await chamar({ messages: [{ role: "system", content: "x" }] })).codigo, 400);
  assert.strictEqual((await chamar({ messages: [{ role: "user", content: "   " }] })).codigo, 400);
});
t("só aceita POST (405)", async () => {
  assert.strictEqual((await chamar(undefined, {}, "GET")).codigo, 405);
});
t("mensagem enorme é cortada antes de ir ao Gemini", async () => {
  _resetarParaTestes(); await chamar(msg("a".repeat(50000)));
  const enviado = ultimoPayload.contents[ultimoPayload.contents.length - 1].parts[0].text;
  assert.ok(enviado.length <= 1500);
});
t("não registra o conteúdo das conversas em log", async () => {
  _resetarParaTestes();
  const original = console.log, erro = console.error; let saida = "";
  console.log = (...a) => { saida += a.join(" "); }; console.error = (...a) => { saida += a.join(" "); };
  respostaGemini = "resposta secreta xyz"; await chamar(msg("pergunta secreta abc"));
  console.log = original; console.error = erro;
  assert.ok(!saida.includes("abc") && !saida.includes("xyz"));
});

(async () => {
  let falhas = 0;
  for (const [nome, fn] of testes) {
    try { await fn(); console.log("[PASS]", nome); }
    catch (e) { falhas++; console.log("[FAIL]", nome, "—", e.message); }
  }
  console.log(`\nTOTAL: ${testes.length} | PASS: ${testes.length - falhas} | FAIL: ${falhas}`);
  process.exit(falhas ? 1 : 0);
})();
