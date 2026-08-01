import streamlit as st
import requests
import os
import base64
import re
import html
import time

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
MAX_OUTPUT_TOKENS = 380     # antes: 1024 — respostas devem ser curtas (BLOCO 8)
MAX_TENTATIVAS = 3          # retries em caso de 429/5xx
TIMEOUT_SEGUNDOS = 30

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


def markdown_para_html(texto: str, escapar: bool = False) -> str:
    """
    Converte Markdown básico para HTML para renderizar nas bolhas.
    `escapar=True` deve ser usado para texto vindo do USUÁRIO, para evitar
    que HTML/JS digitado no chat seja executado (XSS) quando renderizado
    com unsafe_allow_html=True.
    """
    if escapar:
        texto = html.escape(texto)

    # Links: [texto](url) → <a href="url">texto</a>
    texto = re.sub(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)',
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


def perguntar_ia(messages: list, system_prompt: str) -> str:
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        return "⚠️ Chave de API não configurada. Adicione GEMINI_API_KEY nos secrets do Streamlit."

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
                    return f"⚠️ Resposta inesperada da API. Detalhe: {str(e)}"

            status = r.status_code

            # 429 (rate limit) e 5xx (erro temporário do servidor) merecem retry
            if status == 429 or status >= 500:
                ultimo_erro = f"HTTP {status}"
                if tentativa < MAX_TENTATIVAS:
                    time.sleep(2 ** tentativa)  # backoff: 2s, 4s, 8s...
                    continue
                if status == 429:
                    return "🚦 Limite de requisições atingido. Aguarde alguns segundos e tente novamente."
                return f"❌ Erro HTTP {status} após {MAX_TENTATIVAS} tentativas."

            # Erros que não valem retry (401/403/400 etc.)
            try:
                erro_detalhe = r.json()
                msg_erro = erro_detalhe.get("error", {}).get("message", str(erro_detalhe))
            except Exception:
                msg_erro = r.text[:300]

            if status in (401, 403):
                return "🔑 Chave de API inválida ou sem permissão. Verifique o GEMINI_API_KEY nos secrets."
            return f"❌ Erro HTTP {status}: {msg_erro}"

        except requests.exceptions.Timeout:
            ultimo_erro = "timeout"
            if tentativa < MAX_TENTATIVAS:
                time.sleep(2 ** tentativa)
                continue
            return "⏱️ A requisição demorou demais. Tente novamente em instantes."
        except requests.exceptions.ConnectionError as e:
            return f"🔌 Erro de conexão: {str(e)[:300]}"
        except Exception as e:
            return f"❌ Erro inesperado: {type(e).__name__}: {str(e)[:300]}"

    return f"❌ Falha após múltiplas tentativas ({ultimo_erro})."


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
    .contact-status {{ font-size: 12px; margin: 0; opacity: 0.85; color: #a8d5a2; }}
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
        <p class="contact-status">● online</p>
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
    for msg in st.session_state.messages:
        tipo = "user" if msg["role"] == "user" else "bot"
        # Mensagens do usuário SEMPRE escapadas antes de virar HTML (evita XSS).
        # Mensagens do bot já passaram por blindar_resposta() antes de serem salvas.
        conteudo = markdown_para_html(msg["content"], escapar=(tipo == "user"))
        st.markdown(f'<div class="bubble {tipo}">{conteudo}</div>', unsafe_allow_html=True)

# ---------------------------------------------------
# INPUT E RESPOSTA
# ---------------------------------------------------
if prompt := st.chat_input("Como posso ajudar em seu projeto de dados?"):

    # 1. Adiciona e exibe mensagem do usuário imediatamente (escapada)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_container:
        conteudo_user = markdown_para_html(prompt, escapar=True)
        st.markdown(f'<div class="bubble user">{conteudo_user}</div>', unsafe_allow_html=True)

    # 2. Chama a IA
    with st.spinner("Alosa analisando..."):
        resposta_bruta = perguntar_ia(st.session_state.messages, st.session_state.system_prompt)
        # Rede de segurança em código: garante REGRA 0/REGRA 1 mesmo se o
        # modelo falhar em seguir o prompt (jailbreak, alucinação, etc.)
        resposta = blindar_resposta(resposta_bruta)

    # 3. Exibe resposta com efeito de digitação (percepção de velocidade)
    st.session_state.messages.append({"role": "assistant", "content": resposta})
    with chat_container:
        conteudo_bot = markdown_para_html(resposta)
        exibir_com_efeito_digitacao(chat_container, conteudo_bot, "bot")
