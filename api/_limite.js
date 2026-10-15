// Proteções do /api/chat contra abuso e gasto indevido da chave do Gemini.
// Não guarda NENHUM conteúdo de conversa: só um contador de requisições por IP, em memória.
//
// Limitação honesta: a memória é por instância da função. Em picos o Vercel pode usar várias
// instâncias, então este limite é "melhor esforço". Para um limite global, ative também
// Vercel → Firewall → Rate Limiting no painel do projeto.
"use strict";

const JANELA_MS = Number(process.env.LIMITE_JANELA_MIN || 10) * 60 * 1000;
const MAX_POR_JANELA = Number(process.env.LIMITE_MENSAGENS || 0) // 0 = sem limite (padrão);
const MAX_ENTRADAS = 5000; // evita crescer sem fim na memória

const contadores = new Map(); // ip -> [timestamps]

function ipDe(req) {
  const h = req.headers || {};
  const bruto = h["x-real-ip"] || (h["x-forwarded-for"] || "").split(",")[0] || (req.socket && req.socket.remoteAddress) || "";
  return String(bruto).trim() || "desconhecido";
}

// Retorna 0 se pode seguir, ou os segundos a esperar.
function verificarLimite(req, agora = Date.now()) {
  if (MAX_POR_JANELA <= 0) return 0; // limite desligado
  const ip = ipDe(req);
  const recentes = (contadores.get(ip) || []).filter((t) => agora - t < JANELA_MS);
  if (recentes.length >= MAX_POR_JANELA) {
    contadores.set(ip, recentes);
    return Math.max(1, Math.ceil((JANELA_MS - (agora - recentes[0])) / 1000));
  }
  recentes.push(agora);
  contadores.set(ip, recentes);
  if (contadores.size > MAX_ENTRADAS) {
    for (const [k, v] of contadores) {
      if (!v.some((t) => agora - t < JANELA_MS)) contadores.delete(k);
    }
  }
  return 0;
}

// Só aceita chamadas feitas a partir do próprio site (bloqueia outros sites usando a sua chave).
function origemPermitida(req) {
  const h = req.headers || {};
  const origem = h.origin || h.referer || "";
  if (!origem) return true; // chamadas sem cabeçalho (ex.: testes locais) passam; o limite por IP continua valendo
  let host = "";
  try {
    host = new URL(origem).host;
  } catch (_) {
    return false;
  }
  const extras = (process.env.ORIGENS_PERMITIDAS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const proprio = h.host || "";
  return (
    host === proprio ||
    host === "aiosaia.vercel.app" ||
    host.startsWith("localhost") ||
    host.startsWith("127.0.0.1") ||
    extras.includes(host)
  );
}

function _resetarParaTestes() {
  contadores.clear();
}

module.exports = { verificarLimite, origemPermitida, _resetarParaTestes, MAX_POR_JANELA };
