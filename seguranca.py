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
    "github.com/rodrigoaiosa/aiosa_ia",
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
    r"|\d{2,}\s?x\s?de|a partir de\s?r\$|\breais\b|\br\$)",
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

BLOCO_LINK_GERADOR_DADOS = (
    "📊 **Gerador de Dados para Power BI**\n"
    f"[Acessar o gerador]({LINK_GERADOR_DADOS})"
)

RESPOSTA_PADRAO_GERADOR_DADOS = (
    "Para gerar dados fictícios/de teste para usar no Power BI, use a "
    "ferramenta oficial do Rodrigo Aiosa:\n\n"
    f"{BLOCO_LINK_GERADOR_DADOS}"
)

# Gatilho: usuário perguntando sobre o currículo/CV do Rodrigo Aiosa
PADRAO_PEDIDO_CURRICULO = re.compile(
    r"(curr[íi]culo|\bcv\b.{0,20}(rodrigo|dele)|resumo profissional.{0,20}rodrigo|"
    r"trajet[óo]ria.{0,30}(rodrigo|profissional)|experi[êe]ncia.{0,20}rodrigo.{0,20}"
    r"(curr[íi]culo|cv|profissional))",
    re.IGNORECASE,
)

LINK_CURRICULO = (
    "https://github.com/RodrigoAiosa/AIOSA_IA/raw/main/"
    "_Rodrigo_Aiosa_CV%202026.docx"
)

BLOCO_LINK_CURRICULO = (
    "📄 **Currículo — Rodrigo Aiosa** (clique para baixar direto)\n"
    f"[_Rodrigo_Aiosa_CV 2026.docx]({LINK_CURRICULO})"
)


def contem_preco(texto: str) -> bool:
    return bool(PADRAO_PRECO.search(texto.lower()))


def _remover_links_permitidos(texto_lower: str) -> str:
    """
    Remove do texto qualquer trecho que corresponda a um link OFICIAL
    permitido antes de procurar termos proibidos. Necessário porque
    alguns links oficiais (ex: o currículo do Rodrigo, hospedado no
    GitHub) contêm substrings que também estão em TERMOS_PROIBIDOS
    (ex: "github.com/") — sem isso, a própria resposta legítima seria
    barrada pela rede de segurança.
    """
    resultado = texto_lower
    for link in LINKS_PERMITIDOS:
        resultado = resultado.replace(link.lower(), "")
    return resultado


def termos_externos_encontrados(texto: str) -> list:
    texto_lower = texto.lower()
    texto_lower_sem_permitidos = _remover_links_permitidos(texto_lower)
    encontrados = [t for t in TERMOS_PROIBIDOS if t in texto_lower_sem_permitidos]
    if encontrados:
        return encontrados

    # Camada 2: cola espaços entre letras isoladas — pega bypass tipo
    # "k a g g l e" → "kaggle" sem afetar frases normais.
    texto_colado = re.sub(r'(?<=\b\w)\s+(?=\w\b)', '', texto_lower_sem_permitidos)
    if texto_colado != texto_lower_sem_permitidos:
        encontrados = [t for t in TERMOS_PROIBIDOS if t in texto_colado]
        if encontrados:
            return encontrados

    # Camada 3 (fallback final): remove TODOS os espaços do texto e
    # verifica de novo. Pega bypass com quebra assimétrica tipo
    # "Kaggl e" ou "You Tube", que a camada 2 não cobre (só junta
    # letras isoladas). Pequeno risco de falso positivo em textos muito
    # longos por coincidência de junção de palavras, mas o custo de um
    # falso positivo aqui é baixo (só redireciona pros links oficiais).
    texto_sem_espacos = re.sub(r'\s+', '', texto_lower_sem_permitidos)
    if texto_sem_espacos != texto_lower_sem_permitidos:
        encontrados = [t for t in TERMOS_PROIBIDOS if t in texto_sem_espacos]
        if encontrados:
            return encontrados

    return []


def contem_link_oficial(texto: str) -> bool:
    texto_lower = texto.lower()
    return any(link in texto_lower for link in LINKS_PERMITIDOS)


def pedido_gerador_dados(historico_usuario) -> bool:
    """
    `historico_usuario` pode ser uma string única (mensagem atual) ou uma
    lista de strings (mensagens do usuário na conversa). Checa todas,
    porque o pedido pode ter sido feito 1-2 turnos atrás (ex: bot pergunta
    "qual você quer?" e o usuário só responde "sim, recomenda aí").
    Aceita também `None` (sem histórico disponível) sem quebrar.
    """
    if not historico_usuario:
        return False
    if isinstance(historico_usuario, str):
        historico_usuario = [historico_usuario]
    texto_completo = " ".join(historico_usuario).lower()
    return bool(PADRAO_PEDIDO_GERADOR_DADOS.search(texto_completo))


def _resposta_menciona_gerador_dados(resposta: str) -> bool:
    """
    Mesma lógica de `_resposta_menciona_curriculo`, mas para o gerador de
    dados: detecta se a PRÓPRIA RESPOSTA do modelo já entrou no assunto
    (ex: o modelo sugere a ferramenta espontaneamente dentro de uma
    resposta sobre "como praticar Power BI", sem que o USUÁRIO tenha
    usado nenhuma das palavras-gatilho de `PADRAO_PEDIDO_GERADOR_DADOS`).
    Sem essa checagem, uma resposta cortada no meio desse link passaria
    batido pela garantia sempre que o pedido, em si, não batesse com o
    padrão — foi exatamente o bug já corrigido para o currículo, só que
    ainda não generalizado para este caso.
    """
    texto_lower = resposta.lower()
    if PADRAO_PEDIDO_GERADOR_DADOS.search(texto_lower):
        return True
    return "gerador de dados" in texto_lower or "ai-bidatagenerator" in texto_lower


def _remover_link_gerador_dados_truncado(resposta: str) -> str:
    """
    Mesma lógica de `_remover_link_curriculo_truncado`: limpa o fragmento
    de markdown quebrado (link cortado no meio por limite de tokens) e o
    título duplicado do bloco, antes de anexar o link correto e completo.
    """
    resultado = re.sub(r'\[[^\]\[]*\]\([^\)]*$', '', resposta)
    resultado = re.sub(r'\[[^\]\[]*$', '', resultado)
    resultado = resultado.rstrip()

    linhas = resultado.split("\n")
    while linhas:
        ultima = linhas[-1].strip().lower()
        if not ultima:
            linhas.pop()
            continue
        eh_titulo_do_bloco = (
            ("gerador de dados" in ultima or "gerar dados" in ultima)
            and ("power bi" in ultima or "ferramenta" in ultima)
        )
        if eh_titulo_do_bloco:
            linhas.pop()
            continue
        break
    return "\n".join(linhas).rstrip()


def garantir_link_gerador_dados(historico_usuario, resposta: str) -> str:
    """
    Garantia por código (não só por prompt): se o usuário pediu, em
    qualquer ponto recente da conversa, OU a própria resposta do modelo já
    entrou no assunto do gerador de dados, o link completo TEM que
    aparecer na resposta atual. Se o modelo esqueceu, ou cortou a resposta
    no meio do link (limite de tokens), remove o fragmento quebrado e
    anexa o bloco do link correto e completo — preservando o restante do
    texto já gerado, em vez de descartar a resposta inteira.
    """
    if not (pedido_gerador_dados(historico_usuario) or _resposta_menciona_gerador_dados(resposta)):
        return resposta

    if LINK_GERADOR_DADOS in resposta:
        return resposta  # o modelo já gerou certo e completo

    resposta_sem_fragmento = _remover_link_gerador_dados_truncado(resposta)
    if not resposta_sem_fragmento:
        return RESPOSTA_PADRAO_GERADOR_DADOS

    return f"{resposta_sem_fragmento}\n\n{BLOCO_LINK_GERADOR_DADOS}"


def pedido_curriculo(historico_usuario) -> bool:
    """
    Mesma lógica de `pedido_gerador_dados`, mas para pedidos sobre o
    currículo/CV do Rodrigo Aiosa. Checa a mensagem atual e o histórico
    recente, porque o pedido pode ter sido feito 1-2 turnos atrás. Aceita
    também `None` (sem histórico disponível) sem quebrar.
    """
    if not historico_usuario:
        return False
    if isinstance(historico_usuario, str):
        historico_usuario = [historico_usuario]
    texto_completo = " ".join(historico_usuario).lower()
    return bool(PADRAO_PEDIDO_CURRICULO.search(texto_completo))


def _resposta_menciona_curriculo(resposta: str) -> bool:
    """
    Detecta se a PRÓPRIA RESPOSTA do modelo já entrou no assunto do
    currículo (ex: "...você pode ver mais no currículo dele:"), mesmo que
    a pergunta do usuário não tenha usado nenhuma palavra-gatilho (ex:
    "quais são as competências do Rodrigo?" não contém "currículo", mas o
    modelo decidiu responder citando o CV). Sem essa checagem adicional,
    uma resposta cortada no meio do link do currículo passaria batido
    pela garantia de código sempre que o pedido do usuário, em si, não
    batesse com PADRAO_PEDIDO_CURRICULO.
    """
    texto_lower = resposta.lower()
    if PADRAO_PEDIDO_CURRICULO.search(texto_lower):
        return True
    # Pega também o nome do arquivo aparecendo sozinho (ex: link cortado
    # bem no começo, antes mesmo da palavra "currículo" no texto visível).
    nome_arquivo_normalizado = texto_lower.replace(" ", "_")
    return "_rodrigo_aiosa_cv" in nome_arquivo_normalizado


def _remover_link_curriculo_truncado(resposta: str) -> str:
    """
    Se a resposta foi cortada no meio do markdown do link do currículo
    (ex: limite de tokens cortou bem no "[_Rodrigo_Aiosa_CV 2026.docx](" ou
    até antes disso, sem fechar o "]"), remove esse fragmento quebrado do
    final do texto antes de anexar o link correto e completo. Sem isso, o
    usuário veria o fragmento truncado duplicado ou solto no meio da resposta.
    """
    # Fragmento truncado com "[texto](" no final, sem ")" de fechamento
    resultado = re.sub(r'\[[^\]\[]*\]\([^\)]*$', '', resposta)
    # Fragmento truncado ainda mais cedo, com só "[texto" e sem "]"
    resultado = re.sub(r'\[[^\]\[]*$', '', resultado)
    resultado = resultado.rstrip()

    # A resposta pode também ter escrito o TÍTULO do bloco do link antes de
    # ser cortada (ex: "📄 **Currículo — Rodrigo Aiosa** (clique para
    # baixar direto)"), que já vai ser reincluído no BLOCO_LINK_CURRICULO
    # anexado a seguir. Remove essas linhas soltas do final pra não duplicar
    # o título. Para não apagar uma frase legítima de transição (ex: "...
    # no currículo:"), só remove linhas que claramente SÃO o título do
    # bloco (menção a "currículo"/"cv" + "rodrigo" + "baixar"/"download"),
    # e para no primeiro final de linha que não bater com esse padrão.
    linhas = resultado.split("\n")
    while linhas:
        ultima = linhas[-1].strip().lower()
        if not ultima:
            linhas.pop()
            continue
        eh_titulo_do_bloco = (
            ("currículo" in ultima or "curriculo" in ultima or " cv " in f" {ultima} ")
            and "rodrigo" in ultima
            and ("baixar" in ultima or "download" in ultima)
        )
        if eh_titulo_do_bloco:
            linhas.pop()
            continue
        break
    return "\n".join(linhas).rstrip()


def garantir_link_curriculo(historico_usuario, resposta: str) -> str:
    """
    Garantia por código: se o usuário perguntou sobre o currículo do
    Rodrigo em qualquer ponto recente da conversa OU a própria resposta
    do modelo já entrou nesse assunto (ex: o modelo decidiu citar o CV
    numa resposta sobre competências, sem que o usuário tenha usado a
    palavra "currículo"), o link de download completo TEM que aparecer
    na resposta atual. Se o modelo esqueceu, ou (caso mais comum) cortou
    a resposta no meio do link por limite de tokens, remove o fragmento
    quebrado e anexa o bloco do link correto e completo — preservando o
    restante do texto já gerado (ex: lista de competências), em vez de
    descartar a resposta inteira.
    """
    if not (pedido_curriculo(historico_usuario) or _resposta_menciona_curriculo(resposta)):
        return resposta

    if LINK_CURRICULO in resposta:
        return resposta  # o modelo já gerou certo e completo

    resposta_sem_fragmento = _remover_link_curriculo_truncado(resposta)
    return f"{resposta_sem_fragmento}\n\n{BLOCO_LINK_CURRICULO}"


def blindar_resposta(resposta: str, historico_usuario=None) -> str:
    """
    Rede de segurança em código: aplicada DEPOIS da resposta do LLM.
    Garante REGRA 0, REGRA 1, a REGRA do Gerador de Dados e a REGRA do
    Currículo mesmo que o modelo falhe em segui-las (ou corte a resposta
    no meio, ex: limite de tokens). Sempre rode isso antes de exibir
    qualquer resposta ao usuário.

    `historico_usuario`: string (mensagem atual) ou lista de strings
    (mensagens do usuário na conversa). Deve ser sempre passado em
    produção para as checagens de gerador de dados e currículo
    funcionarem em conversas de vários turnos.
    """
    if contem_preco(resposta):
        return RESPOSTA_PADRAO_PRECO

    if termos_externos_encontrados(resposta):
        return RESPOSTA_PADRAO_FONTE_EXTERNA

    # Nota: NÃO usamos "if historico_usuario:" aqui de propósito — uma
    # lista vazia é "falsy" em Python, e isso bloquearia as checagens
    # baseadas no CONTEÚDO DA RESPOSTA (_resposta_menciona_*), que devem
    # funcionar mesmo sem histórico de usuário disponível. As funções
    # abaixo já tratam historico_usuario=None/[] com segurança.
    resposta = garantir_link_gerador_dados(historico_usuario, resposta)
    resposta = garantir_link_curriculo(historico_usuario, resposta)

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
