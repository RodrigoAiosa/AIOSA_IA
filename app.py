import streamlit as st
import requests
import os
import base64

# ---------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA (deve ser a primeira chamada st.)
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
@st.cache_data
def get_base64_img(img_path: str) -> str:
    try:
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""
    except Exception as e:
        st.warning(f"Erro ao carregar imagem: {e}")
        return ""


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
        "2. Seja direto, objetivo e técnico.\n"
        "3. Responda sempre em português do Brasil.\n"
        "4. Se não souber algo, diga claramente em vez de inventar.\n"
    )
    return base + reforco


def limitar_historico(messages: list) -> list:
    if len(messages) > MAX_HISTORICO:
        return messages[-MAX_HISTORICO:]
    return messages


def converter_para_gemini(messages: list, system_prompt: str) -> list:
    """
    Gemini v1beta não aceita 'system_instruction' via REST simples.
    Solução: injeta o system prompt como par user/model no início do histórico.
    """
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

    # v1beta aceita o formato completo com histórico
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"

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
# ESTILO CSS
# ---------------------------------------------------
img_base64 = get_base64_img(FOTO_PATH)

st.markdown(f"""
<style>
    header, footer, #MainMenu {{visibility: hidden;}}
    .stApp {{ background-color: #ECE5DD; }}

    .wa-header {{
        background-color: #075E54;
        padding: 10px 20px;
        display: flex;
        align-items: center;
        position: fixed;
        top: 0; left: 0; right: 0;
        z-index: 999;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }}
    .profile-pic {{
        width: 40px; height: 40px;
        background-color: #f0f0f0;
        border-radius: 50%;
        margin-right: 15px;
        display: flex; justify-content: center; align-items: center;
        overflow: hidden;
        flex-shrink: 0;
    }}
    .profile-pic img {{
        width: 100%; height: 100%;
        object-fit: cover;
    }}
    .contact-info {{ color: white; font-family: sans-serif; }}
    .contact-name {{ font-weight: bold; font-size: 14px; margin: 0; }}
    .contact-status {{ font-size: 11px; margin: 0; opacity: 0.8; }}
    .chat-space {{ margin-top: 80px; }}

    html, body, [class*="st-"], p, div, span {{ color: #000000; }}
    .bubble {{
        padding: 10px 14px;
        border-radius: 10px;
        margin-bottom: 8px;
        max-width: 75%;
        font-family: sans-serif;
        font-size: 14px;
        line-height: 1.5;
        word-wrap: break-word;
    }}
    .user {{
        background-color: #DCF8C6;
        color: #000000 !important;
        margin-left: auto;
        border-radius: 10px 0px 10px 10px;
    }}
    .bot {{
        background-color: #FFFFFF;
        color: #000000 !important;
        margin-right: auto;
        border: 1px solid #e6e6e6;
        border-radius: 0px 10px 10px 10px;
    }}

    [data-testid="stChatInput"] textarea {{
        color: #000000 !important;
        background-color: #ffffff !important;
    }}
</style>

<div class="wa-header">
    <div class="profile-pic">
        {"<img src='data:image/jpeg;base64," + img_base64 + "'>" if img_base64 else "👤"}
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
        conteudo = msg["content"].replace("\n", "<br>")
        st.markdown(f'<div class="bubble {tipo}">{conteudo}</div>', unsafe_allow_html=True)

# ---------------------------------------------------
# INPUT E RESPOSTA
# ---------------------------------------------------
if prompt := st.chat_input("Como posso ajudar em seu projeto de dados?"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Alosa analisando..."):
        resposta = perguntar_ia(st.session_state.messages, st.session_state.system_prompt)

    st.session_state.messages.append({"role": "assistant", "content": resposta})

    with chat_container:
        conteudo_user = prompt.replace("\n", "<br>")
        st.markdown(f'<div class="bubble user">{conteudo_user}</div>', unsafe_allow_html=True)
        conteudo_bot = resposta.replace("\n", "<br>")
        st.markdown(f'<div class="bubble bot">{conteudo_bot}</div>', unsafe_allow_html=True)
