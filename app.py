import streamlit as st
import requests
import os
import base64
import re

# ---------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------
st.set_page_config(page_title="Alosa IA", page_icon="💬", layout="wide")

# ---------------------------------------------------
# CONSTANTES
# ---------------------------------------------------
MODEL = "gemini-1.5-flash"
INSTRUCOES_PATH = "instrucoes.txt"
FOTO_PATH = "eu_ia_foto.jpg"
MAX_HISTORICO = 20

# ---------------------------------------------------
# FUNÇÕES UTILITÁRIAS
# ---------------------------------------------------
def get_base64_img(img_path: str) -> str:
    try:
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""
    except Exception:
        return ""


def markdown_para_html(texto: str) -> str:
    """Converte Markdown básico para HTML para renderizar nas bolhas."""
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


@st.cache_data
def carregar_contexto() -> str:
    if os.path.exists(INSTRUCOES_PATH):
        with open(INSTRUCOES_PATH, "r", encoding="utf-8") as f:
            base = f.read()
    else:
        base = "Você é o Alosa, assistente técnico especializado em dados do Rodrigo Aiosa."

    reforco = (
        "\n\n### REGRAS IMPORTANTES:\n"
        "1. LINK DE CURSOS: Sempre que o usuário mencionar cursos online, "
        "inclua este link no texto: https://rodrigoaiosa.streamlit.app/cursos_online\n"
        "2. LINK DO WHATSAPP: Sempre que o usuário demonstrar interesse em contratar, "
        "treinar equipe, falar com o Rodrigo ou pedir contato, exiba o link abaixo "
        "como hiperlink clicável em Markdown:\n"
        "[📲 Falar com o Rodrigo no WhatsApp](https://wa.me/5511977019335)\n"
        "3. Seja direto, objetivo e técnico.\n"
        "4. Responda sempre em português do Brasil.\n"
        "5. Se não souber algo, diga claramente em vez de inventar.\n"
    )
    return base + reforco


def limitar_historico(messages: list) -> list:
    if len(messages) > MAX_HISTORICO:
        return messages[-MAX_HISTORICO:]
    return messages


def converter_para_gemini(messages: list, system_prompt: str) -> list:
    gemini_messages = [
        {"role": "user",  "parts": [{"text": system_prompt}]},
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

    url = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    historico = limitar_historico(messages)
    gemini_messages = converter_para_gemini(historico, system_prompt)

    payload = {
        "contents": gemini_messages,
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        }
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)

        if not r.ok:
            status = r.status_code
            try:
                erro_detalhe = r.json()
                msg_erro = erro_detalhe.get("error", {}).get("message", str(erro_detalhe))
            except Exception:
                msg_erro = r.text[:300]
            if status in (401, 403):
                return "🔑 Chave de API inválida ou sem permissão. Verifique o GEMINI_API_KEY nos secrets."
            elif status == 429:
                return "🚦 Limite de requisições atingido. Aguarde alguns segundos e tente novamente."
            else:
                return f"❌ Erro HTTP {status}: {msg_erro}"

        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.Timeout:
        return "⏱️ A requisição demorou demais. Tente novamente em instantes."
    except requests.exceptions.ConnectionError as e:
        return f"🔌 Erro de conexão: {str(e)[:300]}"
    except (KeyError, IndexError) as e:
        return f"⚠️ Resposta inesperada da API. Detalhe: {str(e)}"
    except Exception as e:
        return f"❌ Erro inesperado: {type(e).__name__}: {str(e)[:300]}"


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
        conteudo = markdown_para_html(msg["content"])
        st.markdown(f'<div class="bubble {tipo}">{conteudo}</div>', unsafe_allow_html=True)

# ---------------------------------------------------
# INPUT E RESPOSTA
# ---------------------------------------------------
if prompt := st.chat_input("Como posso ajudar em seu projeto de dados?"):

    # 1. Adiciona e exibe mensagem do usuário imediatamente
    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_container:
        conteudo_user = markdown_para_html(prompt)
        st.markdown(f'<div class="bubble user">{conteudo_user}</div>', unsafe_allow_html=True)

    # 2. Chama a IA
    with st.spinner("Alosa analisando..."):
        resposta = perguntar_ia(st.session_state.messages, st.session_state.system_prompt)

    # 3. Exibe resposta com Markdown convertido para HTML
    st.session_state.messages.append({"role": "assistant", "content": resposta})
    with chat_container:
        conteudo_bot = markdown_para_html(resposta)
        st.markdown(f'<div class="bubble bot">{conteudo_bot}</div>', unsafe_allow_html=True)
