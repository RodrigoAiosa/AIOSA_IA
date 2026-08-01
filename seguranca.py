"""
Módulo único de conformidade do agente Alosa.

Centraliza as regras que NÃO podem depender só do LLM obedecer o prompt:
- REGRA 1 (instrucoes.txt): nunca informar preço/valor.
- REGRA 0 (instrucoes.txt): nunca citar fonte externa.

É importado tanto pelo app.py (produção) quanto pelo teste.py (QA),
para garantir que os dois usem exatamente os mesmos critérios.
"""

import re

# ---------------------------------------------------------------
# Links oficiais permitidos (única fonte de verdade — REGRA 0)
# ---------------------------------------------------------------
LINKS_PERMITIDOS = [
    "rodrigoaiosa.streamlit.app",
    "rodrigoaiosa.github.io/promocao_curso_online",
    "ai-bidatagenerator.streamlit.app",
    "wa.me/5511977019335",
    "rodrigoaiosa@gmail.com",
]

# Termos de fontes externas comuns que nunca podem aparecer numa resposta
TERMOS_PROIBIDOS = [
    "kaggle", "youtube", "youtu.be", "udemy", "coursera", "alura",
    "wikipedia", "medium.com", "github.com/", "stackoverflow",
    "uci.edu", "data.world",
]

# Padrão que indica que um preço/valor numérico foi informado
PADRAO_PRECO = re.compile(
    r"(r\$\s?\d|\bpre[cç]o\b.{0,15}\d|\bvalor\b.{0,15}\d|\d+\s?(reais|mil)\b"
    r"|\d{2,}\s?x\s?de|a partir de\s?r\$)",
    re.IGNORECASE,
)

RESPOSTA_PADRAO_PRECO = (
    "O investimento é personalizado de acordo com o seu objetivo e o formato "
    "do treinamento/projeto. O próximo passo é falar diretamente com o Rodrigo "
    "para um diagnóstico rápido:\n\n"
    "📲 [Falar com o Rodrigo no WhatsApp](https://wa.me/5511977019335)"
)

RESPOSTA_PADRAO_FONTE_EXTERNA = (
    "Trabalho só com o conteúdo oficial do Rodrigo Aiosa. Você encontra tudo aqui:\n\n"
    "🏢 [Treinamento para Empresas](https://rodrigoaiosa.streamlit.app/treinamento_empresa)\n"
    "📊 [Projetos de Power BI](https://rodrigoaiosa.streamlit.app/projetos_powerbi)\n"
    "🎓 [Curso Online — Promoção](https://rodrigoaiosa.github.io/promocao_curso_online/)"
)


def contem_preco(texto: str) -> bool:
    return bool(PADRAO_PRECO.search(texto.lower()))


def termos_externos_encontrados(texto: str) -> list:
    texto_lower = texto.lower()
    return [t for t in TERMOS_PROIBIDOS if t in texto_lower]


def contem_link_oficial(texto: str) -> bool:
    texto_lower = texto.lower()
    return any(link in texto_lower for link in LINKS_PERMITIDOS)


def blindar_resposta(resposta: str) -> str:
    """
    Rede de segurança em código: aplicada DEPOIS da resposta do LLM.
    Garante REGRA 0 e REGRA 1 mesmo que o modelo falhe em segui-las.
    Sempre rode isso antes de exibir qualquer resposta ao usuário.
    """
    if contem_preco(resposta):
        return RESPOSTA_PADRAO_PRECO

    if termos_externos_encontrados(resposta):
        return RESPOSTA_PADRAO_FONTE_EXTERNA

    return resposta


def avaliar(resposta: str, checks: list) -> dict:
    """Usado pelo teste.py para reportar quais critérios passaram."""
    resultado = {}
    if "sem_preco" in checks:
        resultado["sem_preco"] = not contem_preco(resposta)
    if "sem_termo_proibido" in checks:
        encontrados = termos_externos_encontrados(resposta)
        resultado["sem_termo_proibido"] = (len(encontrados) == 0)
        if encontrados:
            resultado["termos_encontrados"] = encontrados
    if "tem_link_ou_whatsapp" in checks:
        resultado["tem_link_ou_whatsapp"] = contem_link_oficial(resposta)
    return resultado
