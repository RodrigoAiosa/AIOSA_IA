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

# Gatilho: usuário pedindo ferramenta/site pra gerar dados fictícios para Power BI
PADRAO_PEDIDO_GERADOR_DADOS = re.compile(
    r"(gerar dados|gerador de dados|dados? fict[íi]ci[oa]|dados? falsos?|"
    r"dados? de teste|dataset|base de dados|site.{0,15}gerar|"
    r"ferramenta.{0,15}(gerar|dados))",
    re.IGNORECASE,
)

LINK_GERADOR_DADOS = "https://ai-bidatagenerator.streamlit.app/"

RESPOSTA_PADRAO_GERADOR_DADOS = (
    "Para gerar dados fictícios/de teste para usar no Power BI, use a "
    "ferramenta oficial do Rodrigo Aiosa:\n\n"
    "📊 **Gerador de Dados para Power BI**\n"
    f"[Acessar o gerador]({LINK_GERADOR_DADOS})"
)


def contem_preco(texto: str) -> bool:
    return bool(PADRAO_PRECO.search(texto.lower()))


def termos_externos_encontrados(texto: str) -> list:
    texto_lower = texto.lower()
    return [t for t in TERMOS_PROIBIDOS if t in texto_lower]


def contem_link_oficial(texto: str) -> bool:
    texto_lower = texto.lower()
    return any(link in texto_lower for link in LINKS_PERMITIDOS)


def pedido_gerador_dados(historico_usuario) -> bool:
    """
    `historico_usuario` pode ser uma string única (mensagem atual) ou uma
    lista de strings (mensagens do usuário na conversa). Checa todas,
    porque o pedido pode ter sido feito 1-2 turnos atrás (ex: bot pergunta
    "qual você quer?" e o usuário só responde "sim, recomenda aí").
    """
    if isinstance(historico_usuario, str):
        historico_usuario = [historico_usuario]
    texto_completo = " ".join(historico_usuario).lower()
    return bool(PADRAO_PEDIDO_GERADOR_DADOS.search(texto_completo))


def garantir_link_gerador_dados(historico_usuario, resposta: str) -> str:
    """
    Garantia por código (não só por prompt): se o usuário pediu, em
    qualquer ponto recente da conversa, uma ferramenta pra gerar dados de
    Power BI, o link completo TEM que aparecer na resposta atual quando
    fizer sentido (ex: resposta de confirmação tipo "sim, pode recomendar").
    Se o modelo esqueceu, cortou a resposta no meio, ou gerou o link
    quebrado (truncado por limite de tokens), substitui pela resposta
    padrão já pronta e correta.
    """
    if not pedido_gerador_dados(historico_usuario):
        return resposta

    if LINK_GERADOR_DADOS in resposta:
        return resposta  # o modelo já gerou certo e completo

    return RESPOSTA_PADRAO_GERADOR_DADOS


def blindar_resposta(resposta: str, historico_usuario=None) -> str:
    """
    Rede de segurança em código: aplicada DEPOIS da resposta do LLM.
    Garante REGRA 0, REGRA 1 e a REGRA do Gerador de Dados mesmo que o
    modelo falhe em segui-las (ou corte a resposta no meio, ex: limite
    de tokens). Sempre rode isso antes de exibir qualquer resposta ao usuário.

    `historico_usuario`: string (mensagem atual) ou lista de strings
    (mensagens do usuário na conversa). Deve ser sempre passado em
    produção para a checagem do gerador de dados funcionar em conversas
    de vários turnos.
    """
    if contem_preco(resposta):
        return RESPOSTA_PADRAO_PRECO

    if termos_externos_encontrados(resposta):
        return RESPOSTA_PADRAO_FONTE_EXTERNA

    if historico_usuario:
        resposta = garantir_link_gerador_dados(historico_usuario, resposta)

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
