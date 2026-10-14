// Função serverless do Vercel: recebe a conversa, chama o Gemini com as
// regras de instrucoes.txt e aplica a rede de segurança antes de responder.
// Equivalente em JavaScript ao fluxo de app.py (perguntar_ia + blindar_resposta).
"use strict";

const fs = require("fs");
const path = require("path");
const { blindarResposta } = require("./_seguranca");

const MODEL = "gemini-2.5-flash";
const MAX_HISTORICO = 12;
const MAX_OUTPUT_TOKENS = 550;
const MAX_TENTATIVAS = 2;
const TIMEOUT_MS = 12000;
const MAX_CHARS_MENSAGEM = 1500;
const NUMERO_WHATSAPP = "5511977019335";
const LIMITE_TRANSCRICAO = 1500;

const MENSAGEM_ERRO_GENERICA =
  "Tive um probleminha técnico agora. Pode tentar de novo em instantes? " +
  "Se persistir, fala direto com o Rodrigo: " +
  "[📲 WhatsApp](https://wa.me/5511977019335?text=Olá+Rodrigo!+Tive+um+problema+no+chat+do+site.)";

const MENSAGEM_LIMITE =
  "Muita gente conversando comigo agora 🙂 tenta de novo em alguns segundos, por favor.";

let systemPromptCache = null;
function carregarSystemPrompt() {
  if (systemPromptCache) return systemPromptCache;
  const candidatos = [
    path.join(process.cwd(), "instrucoes.txt"),
    path.join(__dirname, "..", "instrucoes.txt"),
    path.join(__dirname, "instrucoes.txt"),
  ];
  for (const c of candidatos) {
    try {
      systemPromptCache = fs.readFileSync(c, "utf-8");
      return systemPromptCache;
    } catch (_) {
      /* tenta o próximo */
    }
  }
  return "Você é o Alosa, assistente técnico especializado em dados do Rodrigo Aiosa.";
}

function logErro(contexto, detalhe) {
  console.error(`[ALOSA][ERRO] ${contexto}: ${String(detalhe).slice(0, 300)}`);
}

function limparMarkdown(texto) {
  return texto
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .trim();
}

function montarTranscricao(mensagens) {
  const linhas = [];
  for (const m of mensagens) {
    const remetente = m.role === "user" ? "Cliente" : "Alosa";
    const t = limparMarkdown(m.content);
    if (t) linhas.push(`${remetente}: ${t}`);
  }
  let transcricao = linhas.join("\n");
  if (transcricao.length > LIMITE_TRANSCRICAO) {
    transcricao = "(início da conversa omitido)\n" + transcricao.slice(-LIMITE_TRANSCRICAO);
  }
  return transcricao;
}

function inserirHistoricoNoLinkWhatsapp(resposta, mensagens) {
  if (!resposta.includes(`wa.me/${NUMERO_WHATSAPP}`)) return resposta;
  const texto =
    "Olá Rodrigo! Vim pelo Alosa (site), segue o histórico da nossa conversa:\n\n" +
    montarTranscricao(mensagens);
  // encodeURIComponent deixa ( ) ! ' * sem codificar; os parênteses quebrariam o link markdown.
  const codificado = encodeURIComponent(texto).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
  const novoLink = `https://wa.me/${NUMERO_WHATSAPP}?text=${codificado}`;
  return resposta.replace(
    new RegExp(`https://wa\\.me/${NUMERO_WHATSAPP}[^\\s)]*`, "g"),
    () => novoLink
  );
}

function validarEntrada(body) {
  if (!body || !Array.isArray(body.messages) || body.messages.length === 0) return null;
  const msgs = [];
  for (const m of body.messages.slice(-MAX_HISTORICO)) {
    if (!m || (m.role !== "user" && m.role !== "assistant") || typeof m.content !== "string") {
      return null;
    }
    msgs.push({ role: m.role, content: m.content.slice(0, MAX_CHARS_MENSAGEM) });
  }
  // Gemini exige alternância; a fatia deve começar e terminar com "user".
  while (msgs.length && msgs[0].role !== "user") msgs.shift();
  if (!msgs.length || msgs[msgs.length - 1].role !== "user") return null;
  if (!msgs[msgs.length - 1].content.trim()) return null;
  return msgs;
}

function dormir(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function perguntarGemini(mensagens, systemPrompt) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    logErro("config", "GEMINI_API_KEY ausente nas variáveis de ambiente");
    return MENSAGEM_ERRO_GENERICA;
  }
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;
  const contents = [
    { role: "user", parts: [{ text: systemPrompt }] },
    { role: "model", parts: [{ text: "Entendido! Vou seguir todas as instruções fornecidas." }] },
    ...mensagens.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    })),
  ];
  const payload = {
    contents,
    generationConfig: { temperature: 0.2, maxOutputTokens: MAX_OUTPUT_TOKENS },
  };

  for (let tentativa = 1; tentativa <= MAX_TENTATIVAS; tentativa++) {
    try {
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      if (r.ok) {
        const data = await r.json();
        const texto = data?.candidates?.[0]?.content?.parts?.[0]?.text;
        if (typeof texto === "string" && texto.trim()) return texto;
        logErro("resposta_inesperada", JSON.stringify(data));
        return MENSAGEM_ERRO_GENERICA;
      }
      if (r.status === 429 || r.status >= 500) {
        if (tentativa < MAX_TENTATIVAS) {
          await dormir(1500);
          continue;
        }
        logErro("http_retry_esgotado", `status=${r.status}`);
        return r.status === 429
          ? MENSAGEM_LIMITE
          : MENSAGEM_ERRO_GENERICA;
      }
      logErro("http_sem_retry", `status=${r.status}`);
      return MENSAGEM_ERRO_GENERICA;
    } catch (e) {
      if (tentativa < MAX_TENTATIVAS) {
        await dormir(1500);
        continue;
      }
      logErro("excecao", `${e && e.name}: ${e && e.message}`);
      return MENSAGEM_ERRO_GENERICA;
    }
  }
  return MENSAGEM_ERRO_GENERICA;
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Content-Type-Options", "nosniff");

  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ erro: "Método não permitido." });
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (_) {
      body = null;
    }
  }
  const mensagens = validarEntrada(body);
  if (!mensagens) return res.status(400).json({ erro: "Requisição inválida." });

  const bruta = await perguntarGemini(mensagens, carregarSystemPrompt());
  const recentes = mensagens.slice(-6).filter((m) => m.role === "user").map((m) => m.content);
  // Mensagens de erro nossas não passam pela blindagem (não devem ganhar link de currículo etc.).
  const ehErroNosso = bruta === MENSAGEM_ERRO_GENERICA || bruta === MENSAGEM_LIMITE;
  let resposta = ehErroNosso ? bruta : blindarResposta(bruta, recentes);
  resposta = inserirHistoricoNoLinkWhatsapp(resposta, mensagens);

  return res.status(200).json({ resposta });
};
