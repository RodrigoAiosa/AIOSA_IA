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
API_VERSION = "v1beta" # Alterado para garantir compatibilidade com o modelo
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
    except Exception:
        return ""

def markdown_para_html(texto: str) -> str:
    """Converte Markdown básico para HTML para renderizar nas bolhas."""
    texto = re.sub(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" target="_blank" style="color:#075E54;font-weight:bold;">\1</a>',
        texto
    )
    texto = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', texto)
    texto = re.sub(r'\*(.+?)\*', r'<em>\1</em>', texto)
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
        "1. LINK DE CURSOS: https://rodrigoaiosa.streamlit.app/cursos_online\n"
        "2. LINK DO WHATSAPP: [📲 Falar com o Rodrigo no WhatsApp](https://wa.me/5511977019335)\n"
        "3. Seja direto, objetivo e técnico.\n"
        "4. Responda sempre em português do Brasil.\n"
    )
    return base + reforco

def limitar_historico(messages: list) -> list:
    return messages[-MAX_HISTORICO:] if len(messages) > MAX_HISTORICO else messages

def converter_para_gemini(messages: list, system_prompt: str) -> list:
    gemini_messages = [
        {"role": "user", "parts": [{"text": system_prompt}]},
        {"role": "model", "parts": [{"text": "Entendido! Vou seguir todas as instruções."}]},
    ]
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})
    return gemini_messages

def perguntar_ia(messages: list, system_prompt: str) -> str:
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Chave de API não configurada."

    url = f"https://generativelanguage.googleapis.com/{API_VERSION}/models/{MODEL}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": converter_para_gemini(limitar_historico(messages), system_prompt),
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if not r.ok:
            return f"❌ Erro HTTP {r.status_code}: {r.text[:200]}"
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# ---------------------------------------------------
# HEADER E CSS ORIGINAL (RESTAURADO)
# ---------------------------------------------------
img_base64 = get_base64_img(FOTO_PATH)
foto_html = f"<img src='data:image/jpeg;base64,{img_base64}' style='width:42px;height:42px;object-fit:cover;border-radius:50%;'>" if img_base64 else "👤"

st.markdown(f"""
<style>
    header, footer, #MainMenu {{visibility: hidden;}}
    .stApp {{ background-color: #0E1117; }} /* Fundo escuro original */

    .wa-header {{
        background-color: #075E54;
        padding: 8px 16px;
        display: flex;
        align-items: center;
        position: fixed;
        top: 0; left: 0; right: 0;
        z-index: 999;
        height: 60px;
    }}
    .profile-pic {{ width: 42px; height: 42px; border-radius: 50%; overflow: hidden; margin-right: 12px; }}
    .contact-info {{ color: white; font-family: sans-serif; }}
    .contact-name {{ font-weight: bold; font-size: 15px; margin: 0; }}
    .contact-status {{ font-size: 12px; margin: 0; opacity: 0.85; color: #a8d5a2; }}
    .chat-space {{ margin-top: 70px; padding-bottom: 20px; }}

    /* Mantendo as cores das bolhas originais */
    .bubble {{
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 6px;
        max-width: 72%;
        font-family: sans-serif;
        font-size: 14px;
    }}
    .user {{ background-color: #DCF8C6; color: #000 !important; margin-left: auto; }}
    .bot {{ background-color: #FFFFFF; color: #000 !important; margin-right: auto; }}
    
    /* Input Style */
    [data-testid="stChatInput"] textarea {{
        color: #ffffff !important;
    }}
</style>

<div class="wa-header">
    <div class="profile-pic">{foto_html}</div>
    <div class="contact-info">
        <p class="contact-name">Alosa — Assistente do Rodrigo Aiosa</p>
        <p class="contact-status">● online</p>
    </div>
</div>
<div class="chat-space"></div>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# LÓGICA DE EXIBIÇÃO
# ---------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    tipo = "user" if msg["role"] == "user" else "bot"
    st.markdown(f'<div class="bubble {tipo}">{markdown_para_html(msg["content"])}</div>', unsafe_allow_html=True)

if prompt := st.chat_input("Como posso ajudar em seu projeto de dados?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(f'<div class="bubble user">{markdown_para_html(prompt)}</div>', unsafe_allow_html=True)

    with st.spinner(""):
        resposta = perguntar_ia(st.session_state.messages, carregar_contexto())
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        st.markdown(f'<div class="bubble bot">{markdown_para_html(resposta)}</div>', unsafe_allow_html=True)
        st.rerun()
