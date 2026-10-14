// Porte fiel de seguranca.py para JavaScript (rede de segurança em código).
// Qualquer mudança de regra deve ser feita nos DOIS arquivos; o script
// tests/comparar_seguranca.js confere se ambos devolvem o mesmo resultado.
"use strict";

const LINKS_PERMITIDOS = [
  "rodrigoaiosa.streamlit.app",
  "rodrigoaiosa.vercel.app",
  "rodrigoaiosa.github.io/promocao_curso_online",
  "ai-bidatagenerator.streamlit.app",
  "wa.me/5511977019335",
  "rodrigoaiosa@gmail.com",
  "github.com/rodrigoaiosa/aiosa_ia",
];

const TERMOS_PROIBIDOS = [
  "kaggle", "youtube", "youtu.be", "udemy", "coursera", "alura",
  "wikipedia", "medium.com", "github.com/", "stackoverflow",
  "uci.edu", "data.world",
];

const PADRAO_PRECO = new RegExp(
  "(r\\$\\s?\\d|\\bpre[cç]o\\b[^\\n]{0,15}\\d|\\bvalor\\b[^\\n]{0,15}\\d|\\d+\\s?(reais|mil)\\b" +
    "|\\d{2,}\\s?x\\s?de|a partir de\\s?r\\$|\\breais\\b|\\br\\$)",
  "i"
);

const RESPOSTA_PADRAO_PRECO =
  "O investimento é personalizado de acordo com o seu objetivo e o formato " +
  "do treinamento/projeto. O próximo passo é falar diretamente com o Rodrigo " +
  "para um diagnóstico rápido:\n\n" +
  "📲 [Falar com o Rodrigo no WhatsApp](https://wa.me/5511977019335)";

const RESPOSTA_PADRAO_FONTE_EXTERNA =
  "Trabalho só com o conteúdo oficial do Rodrigo Aiosa. Você encontra tudo aqui:\n\n" +
  "🏢 [Treinamento para Empresas](https://rodrigoaiosa.streamlit.app/treinamento_empresa)\n" +
  "📊 [Projetos de Power BI](https://rodrigoaiosa.vercel.app/#powerbi)\n" +
  "🎓 [Curso Online — Promoção](https://rodrigoaiosa.github.io/promocao_curso_online/)";

const PADRAO_PEDIDO_GERADOR_DADOS = new RegExp(
  "(gerar dados|gerador de dados|dados? fict[íi]ci[oa]|dados? falsos?|" +
    "dados? de teste|dataset|base de dados|site[^\\n]{0,15}gerar|" +
    "ferramenta[^\\n]{0,15}(gerar|dados))",
  "i"
);

const LINK_GERADOR_DADOS = "https://ai-bidatagenerator.streamlit.app/";

const BLOCO_LINK_GERADOR_DADOS =
  "📊 **Gerador de Dados para Power BI**\n" + `[Acessar o gerador](${LINK_GERADOR_DADOS})`;

const RESPOSTA_PADRAO_GERADOR_DADOS =
  "Para gerar dados fictícios/de teste para usar no Power BI, use a " +
  "ferramenta oficial do Rodrigo Aiosa:\n\n" +
  BLOCO_LINK_GERADOR_DADOS;

const PADRAO_PEDIDO_CURRICULO = new RegExp(
  "(curr[íi]culo|\\bcv\\b[^\\n]{0,20}(rodrigo|dele)|resumo profissional[^\\n]{0,20}rodrigo|" +
    "trajet[óo]ria[^\\n]{0,30}(rodrigo|profissional)|experi[êe]ncia[^\\n]{0,20}rodrigo[^\\n]{0,20}" +
    "(curr[íi]culo|cv|profissional))",
  "i"
);

const LINK_CURRICULO =
  "https://github.com/RodrigoAiosa/AIOSA_IA/raw/main/" + "_Rodrigo_Aiosa_CV%202026.docx";

const BLOCO_LINK_CURRICULO =
  "📄 **Currículo — Rodrigo Aiosa** (clique para baixar direto)\n" +
  `[_Rodrigo_Aiosa_CV 2026.docx](${LINK_CURRICULO})`;

function contemPreco(texto) {
  return PADRAO_PRECO.test(texto.toLowerCase());
}

function removerLinksPermitidos(textoLower) {
  let resultado = textoLower;
  for (const link of LINKS_PERMITIDOS) {
    resultado = resultado.split(link.toLowerCase()).join("");
  }
  return resultado;
}

const L = "[\\p{L}\\p{N}_]";
const NL = "[^\\p{L}\\p{N}_]";
// Python: (?<=\b\w)\s+(?=\w\b)  — cola letras isoladas ("k a g g l e").
const RE_LETRAS_ISOLADAS = new RegExp(
  `(?<=(?<!${L})${L})\\s+(?=${L}(?!${L}))`,
  "gu"
);

function termosExternosEncontrados(texto) {
  const textoLower = texto.toLowerCase();
  const semPermitidos = removerLinksPermitidos(textoLower);
  let encontrados = TERMOS_PROIBIDOS.filter((t) => semPermitidos.includes(t));
  if (encontrados.length) return encontrados;

  const colado = semPermitidos.replace(RE_LETRAS_ISOLADAS, "");
  if (colado !== semPermitidos) {
    encontrados = TERMOS_PROIBIDOS.filter((t) => colado.includes(t));
    if (encontrados.length) return encontrados;
  }

  const semEspacos = semPermitidos.replace(/\s+/gu, "");
  if (semEspacos !== semPermitidos) {
    encontrados = TERMOS_PROIBIDOS.filter((t) => semEspacos.includes(t));
    if (encontrados.length) return encontrados;
  }
  return [];
}

function juntarHistorico(historicoUsuario) {
  if (!historicoUsuario || (Array.isArray(historicoUsuario) && historicoUsuario.length === 0)) {
    return null;
  }
  if (typeof historicoUsuario === "string") return historicoUsuario.toLowerCase();
  return historicoUsuario.join(" ").toLowerCase();
}

function pedidoGeradorDados(historicoUsuario) {
  const t = juntarHistorico(historicoUsuario);
  return t === null ? false : PADRAO_PEDIDO_GERADOR_DADOS.test(t);
}

function respostaMencionaGeradorDados(resposta) {
  const t = resposta.toLowerCase();
  if (PADRAO_PEDIDO_GERADOR_DADOS.test(t)) return true;
  return t.includes("gerador de dados") || t.includes("ai-bidatagenerator");
}

function removerFragmentoTruncado(resposta) {
  let r = resposta.replace(/\[[^\]\[]*\]\([^)]*$/, "");
  r = r.replace(/\[[^\]\[]*$/, "");
  return r.replace(/\s+$/u, "");
}

function removerLinkGeradorTruncado(resposta) {
  const resultado = removerFragmentoTruncado(resposta);
  const linhas = resultado.split("\n");
  while (linhas.length) {
    const ultima = linhas[linhas.length - 1].trim().toLowerCase();
    if (!ultima) {
      linhas.pop();
      continue;
    }
    const ehTitulo =
      (ultima.includes("gerador de dados") || ultima.includes("gerar dados")) &&
      (ultima.includes("power bi") || ultima.includes("ferramenta"));
    if (ehTitulo) {
      linhas.pop();
      continue;
    }
    break;
  }
  return linhas.join("\n").replace(/\s+$/u, "");
}

function garantirLinkGeradorDados(historicoUsuario, resposta) {
  if (!(pedidoGeradorDados(historicoUsuario) || respostaMencionaGeradorDados(resposta))) {
    return resposta;
  }
  if (resposta.includes(LINK_GERADOR_DADOS)) return resposta;
  const semFragmento = removerLinkGeradorTruncado(resposta);
  if (!semFragmento) return RESPOSTA_PADRAO_GERADOR_DADOS;
  return `${semFragmento}\n\n${BLOCO_LINK_GERADOR_DADOS}`;
}

function pedidoCurriculo(historicoUsuario) {
  const t = juntarHistorico(historicoUsuario);
  return t === null ? false : PADRAO_PEDIDO_CURRICULO.test(t);
}

function respostaMencionaCurriculo(resposta) {
  const t = resposta.toLowerCase();
  if (PADRAO_PEDIDO_CURRICULO.test(t)) return true;
  return t.split(" ").join("_").includes("_rodrigo_aiosa_cv");
}

function removerLinkCurriculoTruncado(resposta) {
  const resultado = removerFragmentoTruncado(resposta);
  const linhas = resultado.split("\n");
  while (linhas.length) {
    const ultima = linhas[linhas.length - 1].trim().toLowerCase();
    if (!ultima) {
      linhas.pop();
      continue;
    }
    const ehTitulo =
      (ultima.includes("currículo") || ultima.includes("curriculo") || ` ${ultima} `.includes(" cv ")) &&
      ultima.includes("rodrigo") &&
      (ultima.includes("baixar") || ultima.includes("download"));
    if (ehTitulo) {
      linhas.pop();
      continue;
    }
    break;
  }
  return linhas.join("\n").replace(/\s+$/u, "");
}

function garantirLinkCurriculo(historicoUsuario, resposta) {
  if (!(pedidoCurriculo(historicoUsuario) || respostaMencionaCurriculo(resposta))) {
    return resposta;
  }
  if (resposta.includes(LINK_CURRICULO)) return resposta;
  const semFragmento = removerLinkCurriculoTruncado(resposta);
  return `${semFragmento}\n\n${BLOCO_LINK_CURRICULO}`;
}

function blindarResposta(resposta, historicoUsuario) {
  if (contemPreco(resposta)) return RESPOSTA_PADRAO_PRECO;
  if (termosExternosEncontrados(resposta).length) return RESPOSTA_PADRAO_FONTE_EXTERNA;
  resposta = garantirLinkGeradorDados(historicoUsuario, resposta);
  resposta = garantirLinkCurriculo(historicoUsuario, resposta);
  return resposta;
}

module.exports = { blindarResposta, contemPreco, termosExternosEncontrados };
