import streamlit as st
import requests
import os
import base64
import re
import html
import time
import csv
from datetime import datetime
from urllib.parse import quote

from seguranca import blindar_resposta

# ---------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------
st.set_page_config(page_title="Alosa IA", page_icon="💬", layout="wide")

# ---------------------------------------------------
# CONSTANTES
# ---------------------------------------------------
MODEL = "gemini-2.5-flash"
INSTRUCOES_PATH = "instrucoes.txt"
FOTO_PATH = "eu_ia_foto.jpg"
MAX_HISTORICO = 12          # antes: 20 — menos tokens enviados por chamada
MAX_HISTORICO_EXIBICAO = 40 # limite de bolhas renderizadas na tela (perf)
MAX_OUTPUT_TOKENS = 550     # antes: 380 estava cortando respostas no meio de links
MAX_TENTATIVAS = 3          # retries em caso de 429/5xx
TIMEOUT_SEGUNDOS = 30
LOG_CONVERSAS_PATH = "conversas_log.csv"
NUMERO_WHATSAPP_RODRIGO = "5511977019335"
LIMITE_CARACTERES_TRANSCRICAO = 1500  # texto bruto; a URL final fica maior após codificar

# ---------------------------------------------------
# FUNÇÕES UTILITÁRIAS
# ---------------------------------------------------
@st.cache_data
def get_base64_img(img_path: str) -> str:
    """Cacheado: antes era recodificado a cada rerun do Streamlit (a cada mensagem)."""
    try:
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""
    except Exception:
        return ""


def markdown_para_html(texto: str) -> str:
    """
    Converte Markdown básico para HTML para renderizar nas bolhas.
    SEMPRE escapa HTML primeiro (usuário E modelo) antes de aplicar as
    substituições de markdown — html.escape() só mexe em & < > " ', não
    afeta os caracteres usados pelo nosso markdown ([ ] ( ) * ), então a
    conversão continua funcionando normalmente. Isso fecha dois riscos:
    1) usuário digitando HTML/JS no chat (XSS);
    2) o modelo (Gemini) gerando algo parecido com HTML por engano/jailbreak.
    """
    texto = html.escape(texto)

    # Links: [texto](url) → <a href="url">texto</a>
    # Aceita http(s):// e mailto: — antes só reconhecia http(s), então
    # links de e-mail ficavam exibidos como texto cru com colchetes.
    texto = re.sub(
        r'\[([^\]]+)\]\(((?:https?://|mailto:)[^\)]+)\)',
        r'<a href="\2" target="_blank" style="color:#075E54;font-weight:bold;">\1</a>',
        texto
    )
    # Negrito: **texto** → <strong>texto</strong>
    texto = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', texto)
    # Itálico: *texto* → <em>texto</em>
    texto = re.sub(r'\*(.+?)\*', r'<em>\1</em>', texto)
    # Quebras de linha
    texto = texto.replace("\n", "<br>")
    return texto


def carregar_contexto() -> str:
    """
    Fonte única das regras do agente. Todo o conteúdo comercial e de
    conformidade vive em instrucoes.txt — nada de regras duplicadas aqui,
    pra não haver risco de desalinhamento entre os dois arquivos.

    SEM @st.cache_data de propósito: essa função só roda uma vez por sessão
    (ver trava mais abaixo), então cachear não ganha performance nenhuma —
    só risco de manter uma versão antiga do arquivo na memória entre
    deploys, caso o container não reinicie 100% limpo.
    """
    if os.path.exists(INSTRUCOES_PATH):
        with open(INSTRUCOES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "Você é o Alosa, assistente técnico especializado em dados do Rodrigo Aiosa."


def limitar_historico(messages: list) -> list:
    if len(messages) > MAX_HISTORICO:
        return messages[-MAX_HISTORICO:]
    return messages


def registrar_conversa(pergunta: str, resposta: str) -> None:
    """
    Log leve de conversas (mini "captura de lead"): grava cada troca num
    CSV local, pra você conseguir ver depois quais perguntas os visitantes
    fazem, mesmo que não cliquem no WhatsApp.

    LIMITAÇÃO IMPORTANTE: o sistema de arquivos do Streamlit Cloud é
    EFÊMERO — esse CSV pode ser apagado a qualquer reboot/redeploy do
    app. Isso NÃO é um banco de dados de verdade, é um "melhor esforço"
    enquanto não há uma integração externa (Google Sheets, banco de
    dados, etc.). Baixe o arquivo periodicamente se quiser guardar o
    histórico, ou peça uma integração externa como próximo passo.
    Nunca deve travar o app se falhar — por isso o try/except silencioso.
    """
    try:
        arquivo_novo = not os.path.exists(LOG_CONVERSAS_PATH)
        with open(LOG_CONVERSAS_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if arquivo_novo:
                writer.writerow(["timestamp", "pergunta_usuario", "resposta_bot"])
            writer.writerow([datetime.now().isoformat(timespec="seconds"), pergunta, resposta])
    except Exception as e:
        _log_erro_tecnico("log_conversa", f"{type(e).__name__}: {str(e)[:200]}")


def _limpar_markdown_para_texto_puro(texto: str) -> str:
    """Remove formatação Markdown (links, negrito, itálico) pra ficar
    legível como texto simples dentro da mensagem do WhatsApp."""
    texto = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', texto)  # [texto](url) → texto
    texto = texto.replace("**", "").replace("*", "")
    return texto.strip()


def montar_transcricao_conversa(mensagens: list, limite: int = LIMITE_CARACTERES_TRANSCRICAO) -> str:
    """
    Monta o histórico da conversa como texto simples, mais recente por
    último. Se ficar maior que `limite` caracteres, corta do INÍCIO
    (mantém as mensagens mais recentes, que são as mais relevantes pro
    Rodrigo ao assumir a conversa).
    """
    linhas = []
    for m in mensagens:
        remetente = "Cliente" if m["role"] == "user" else "Alosa"
        texto_limpo = _limpar_markdown_para_texto_puro(m["content"])
        if texto_limpo:
            linhas.append(f"{remetente}: {texto_limpo}")

    transcricao = "\n".join(linhas)
    if len(transcricao) > limite:
        transcricao = "(início da conversa omitido)\n" + transcricao[-limite:]
    return transcricao


def gerar_link_whatsapp_com_historico(mensagens: list) -> str:
    """Gera o link wa.me com o histórico da conversa já preenchido na
    mensagem, pra o Rodrigo ver o contexto assim que abrir o WhatsApp."""
    transcricao = montar_transcricao_conversa(mensagens)
    texto_final = (
        "Olá Rodrigo! Vim pelo Alosa (site), segue o histórico da nossa "
        f"conversa:\n\n{transcricao}"
    )
    return f"https://wa.me/{NUMERO_WHATSAPP_RODRIGO}?text={quote(texto_final)}"


def inserir_historico_no_link_whatsapp(resposta: str, mensagens: list) -> str:
    """
    Sempre que a resposta final contiver um link wa.me (venha do modelo
    ou dos textos padrão de seguranca.py), troca pela versão com o
    histórico da conversa embutido — sem precisar que o modelo saiba
    gerar esse link sozinho.
    """
    if f"wa.me/{NUMERO_WHATSAPP_RODRIGO}" not in resposta:
        return resposta
    try:
        novo_link = gerar_link_whatsapp_com_historico(mensagens)
    except Exception as e:
        _log_erro_tecnico("gerar_link_whatsapp_historico", f"{type(e).__name__}: {str(e)[:200]}")
        return resposta  # se der erro, mantém o link genérico em vez de quebrar a resposta
    return re.sub(
        rf'https://wa\.me/{NUMERO_WHATSAPP_RODRIGO}[^\s\)]*',
        novo_link,
        resposta
    )


def converter_para_gemini(messages: list, system_prompt: str) -> list:
    gemini_messages = [
        {"role": "user",  "parts": [{"text": system_prompt}]},
        {"role": "model", "parts": [{"text": "Entendido! Vou seguir todas as instruções fornecidas."}]},
    ]
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            continue
        if role == "assistant":
            role = "model"
        gemini_messages.append({
            "role": role,
            "parts": [{"text": content}]
        })
    return gemini_messages


MENSAGEM_ERRO_GENERICA = (
    "Tive um probleminha técnico agora. Pode tentar de novo em instantes? "
    "Se persistir, fala direto com o Rodrigo: "
    "[📲 WhatsApp](https://wa.me/5511977019335?text=Olá+Rodrigo!+Tive+um+problema+no+chat+do+site.)"
)


def _log_erro_tecnico(contexto: str, detalhe: str) -> None:
    """
    Erros técnicos (status HTTP, timeouts, exceções) NÃO devem aparecer
    crus pro usuário final numa conversa de vendas — isso quebra a
    experiência. Registramos no log do Streamlit Cloud (visível em
    Manage app → logs) e devolvemos uma mensagem genérica e amigável.
    """
    print(f"[ALOSA][ERRO] {contexto}: {detalhe}")


def perguntar_ia(messages: list, system_prompt: str) -> str:
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        _log_erro_tecnico("config", "GEMINI_API_KEY ausente nos secrets")
        return MENSAGEM_ERRO_GENERICA

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    historico = limitar_historico(messages)
    gemini_messages = converter_para_gemini(historico, system_prompt)

    payload = {
        "contents": gemini_messages,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
        }
    }

    ultimo_erro = None

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEGUNDOS)

            if r.ok:
                data = r.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    _log_erro_tecnico("resposta_inesperada", f"{e} | payload: {str(data)[:300]}")
                    return MENSAGEM_ERRO_GENERICA

            status = r.status_code

            # 429 (rate limit) e 5xx (erro temporário do servidor) merecem retry
            if status == 429 or status >= 500:
                ultimo_erro = f"HTTP {status}"
                if tentativa < MAX_TENTATIVAS:
                    time.sleep(2 ** tentativa)  # backoff: 2s, 4s, 8s...
                    continue
                _log_erro_tecnico("http_retry_esgotado", f"status={status}")
                if status == 429:
                    return (
                        "Muita gente conversando comigo agora 🙂 tenta de novo em "
                        "alguns segundos, por favor."
                    )
                return MENSAGEM_ERRO_GENERICA

            # Erros que não valem retry (401/403/400 etc.)
            try:
                erro_detalhe = r.json()
                msg_erro = erro_detalhe.get("error", {}).get("message", str(erro_detalhe))
            except Exception:
                msg_erro = r.text[:300]

            _log_erro_tecnico("http_sem_retry", f"status={status} | {msg_erro}")
            return MENSAGEM_ERRO_GENERICA

        except requests.exceptions.Timeout:
            ultimo_erro = "timeout"
            if tentativa < MAX_TENTATIVAS:
                time.sleep(2 ** tentativa)
                continue
            _log_erro_tecnico("timeout_esgotado", f"{TIMEOUT_SEGUNDOS}s x {MAX_TENTATIVAS} tentativas")
            return MENSAGEM_ERRO_GENERICA
        except requests.exceptions.ConnectionError as e:
            _log_erro_tecnico("conexao", str(e)[:300])
            return MENSAGEM_ERRO_GENERICA
        except Exception as e:
            _log_erro_tecnico("excecao_inesperada", f"{type(e).__name__}: {str(e)[:300]}")
            return MENSAGEM_ERRO_GENERICA

    _log_erro_tecnico("falha_final", str(ultimo_erro))
    return MENSAGEM_ERRO_GENERICA


def exibir_com_efeito_digitacao(container, texto_html: str, tipo: str):
    """
    Efeito de "digitando" client-side: a resposta já veio pronta da API
    (não há streaming real do Gemini aqui), mas renderizar palavra por
    palavra melhora MUITO a percepção de velocidade sem custo técnico
    ou risco de parsing de stream incompleto.
    """
    placeholder = container.empty()
    partes = texto_html.split(" ")
    acumulado = ""
    passo = max(1, len(partes) // 25)  # não trava em respostas longas
    for i in range(0, len(partes), passo):
        acumulado = " ".join(partes[:i + passo])
        placeholder.markdown(f'<div class="bubble {tipo}">{acumulado}</div>', unsafe_allow_html=True)
        time.sleep(0.02)
    placeholder.markdown(f'<div class="bubble {tipo}">{texto_html}</div>', unsafe_allow_html=True)


# ---------------------------------------------------
# CARREGA FOTO E MONTA HEADER
# ---------------------------------------------------
img_base64 = get_base64_img(FOTO_PATH)

if img_base64:
    foto_html = f"<img src='data:image/jpeg;base64,{img_base64}' style='width:42px;height:42px;object-fit:cover;border-radius:50%;display:block;'>"
else:
    foto_html = "<span style='font-size:22px;color:#fff;'>👤</span>"

st.markdown(f"""
<style>
    header, footer, #MainMenu {{visibility: hidden;}}
    .stApp {{ background-color: #ECE5DD; }}

    .wa-header {{
        background-color: #075E54;
        padding: 8px 16px;
        display: flex;
        align-items: center;
        position: fixed;
        top: 0; left: 0; right: 0;
        z-index: 999;
        height: 60px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }}
    .profile-pic {{
        width: 42px;
        height: 42px;
        border-radius: 50%;
        overflow: hidden;
        margin-right: 12px;
        flex-shrink: 0;
        background-color: #aaa;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .contact-info {{ color: white; font-family: sans-serif; line-height: 1.3; }}
    .contact-name {{ font-weight: bold; font-size: 15px; margin: 0; }}
    .contact-status {{ font-size: 12px; margin: 0; opacity: 0.9; color: #a8d5a2; display: flex; align-items: center; gap: 5px; }}
    .status-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #25D366;
        flex-shrink: 0;
    }}
    .chat-space {{ margin-top: 70px; padding-bottom: 20px; }}

    html, body, [class*="st-"], p, div, span {{ color: #000000; }}
    .bubble {{
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 6px;
        max-width: 72%;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 14px;
        line-height: 1.5;
        word-wrap: break-word;
    }}
    .user {{
        background-color: #DCF8C6;
        color: #000000 !important;
        margin-left: auto;
        margin-right: 8px;
        border-radius: 8px 0px 8px 8px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.1);
    }}
    .bot {{
        background-color: #FFFFFF;
        color: #000000 !important;
        margin-left: 8px;
        margin-right: auto;
        border-radius: 0px 8px 8px 8px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.1);
    }}
    .bubble a {{
        color: #075E54 !important;
        font-weight: bold;
        text-decoration: underline;
    }}
    [data-testid="stChatInput"] textarea {{
        color: #000000 !important;
        background-color: #ffffff !important;
        caret-color: #000000 !important;
        padding-left: 10px !important;
    }}
</style>

<script>
function focusChatInput() {{
    const el = document.querySelector('[data-testid="stChatInput"] textarea');
    if (el) {{ el.focus(); }}
    else {{ setTimeout(focusChatInput, 300); }}
}}
window.addEventListener('load', focusChatInput);
</script>

<div class="wa-header">
    <div class="profile-pic">
        {foto_html}
    </div>
    <div class="contact-info">
        <p class="contact-name">Alosa — Assistente do Rodrigo Aiosa</p>
        <p class="contact-status"><span class="status-dot"></span>online</p>
    </div>
</div>
<div class="chat-space"></div>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# INICIALIZAÇÃO DO ESTADO
# ---------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = carregar_contexto()

# ---------------------------------------------------
# EXIBIÇÃO DO HISTÓRICO DE MENSAGENS
# ---------------------------------------------------
chat_container = st.container()

with chat_container:
    # Limita quantas bolhas são renderizadas de uma vez (perf em sessões
    # longas) — a API já usa um limite separado e menor (MAX_HISTORICO).
    mensagens_para_exibir = st.session_state.messages[-MAX_HISTORICO_EXIBICAO:]
    for msg in mensagens_para_exibir:
        tipo = "user" if msg["role"] == "user" else "bot"
        # Mensagens do usuário SEMPRE escapadas antes de virar HTML (evita XSS).
        # Mensagens do bot já passaram por blindar_resposta() antes de serem salvas.
        conteudo = markdown_para_html(msg["content"])
        st.markdown(f'<div class="bubble {tipo}">{conteudo}</div>', unsafe_allow_html=True)

# ---------------------------------------------------
# INPUT E RESPOSTA
# ---------------------------------------------------
if prompt := st.chat_input("Como posso ajudar em seu projeto de dados?"):

    # 1. Adiciona e exibe mensagem do usuário imediatamente (escapada)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_container:
        conteudo_user = markdown_para_html(prompt)
        st.markdown(f'<div class="bubble user">{conteudo_user}</div>', unsafe_allow_html=True)

    # 2. Chama a IA
    with st.spinner("Alosa analisando..."):
        resposta_bruta = perguntar_ia(st.session_state.messages, st.session_state.system_prompt)
        # Rede de segurança em código: garante REGRA 0/REGRA 1/link do gerador
        # de dados mesmo se o modelo falhar em seguir o prompt ou for cortado
        # no meio (ex: limite de tokens, jailbreak, alucinação).
        # Passa as últimas mensagens do USUÁRIO (não só a atual) porque o
        # pedido pode ter sido feito 1-2 turnos atrás na conversa.
        mensagens_usuario_recentes = [
            m["content"] for m in st.session_state.messages[-6:] if m["role"] == "user"
        ]
        resposta = blindar_resposta(resposta_bruta, historico_usuario=mensagens_usuario_recentes)

        # Enriquece qualquer link de WhatsApp na resposta com o histórico
        # da conversa (texto pré-preenchido) — inclui a mensagem atual do
        # usuário porque ela já foi adicionada a session_state.messages acima.
        resposta = inserir_historico_no_link_whatsapp(resposta, st.session_state.messages)

        # Log leve pra você ver o que os visitantes perguntam (ver limitação
        # de armazenamento efêmero no docstring de registrar_conversa)
        registrar_conversa(prompt, resposta)

    # 3. Exibe resposta com efeito de digitação (percepção de velocidade)
    st.session_state.messages.append({"role": "assistant", "content": resposta})
    with chat_container:
        conteudo_bot = markdown_para_html(resposta)
        exibir_com_efeito_digitacao(chat_container, conteudo_bot, "bot")
