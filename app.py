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
# Alterado para v1beta para garantir suporte ao gemini-1.5-flash via REST
MODEL = "gemini-1.5-flash"
API_VERSION = "v1beta" 
INSTRUCOES_PATH = "instrucoes.txt"
FOTO_PATH = "eu_ia_foto.jpg"
MAX_HISTORICO = 20

# ---------------------------------------------------
# FUNÇÕES UTILITÁRIAS
# ---------------------------------------------------
def get_base64_img(img_path: str) -> str:
    try:
        if os.path.exists(img_path):
            with open(img_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
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
    # O Gemini 1.5 aceita system_instruction separadamente no payload, 
    # mas para manter a compatibilidade com a função legada de chat:
    gemini_messages = []
    
    # Adicionando o contexto como a primeira interação
    gemini_messages.append({"role": "user", "parts": [{"text": system_prompt}]})
    gemini_messages.append({"role": "model", "parts": [{"text": "Entendido. Serei direto, técnico e seguirei todas as instruções."}]})
    
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_messages.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })
    return gemini_messages

def perguntar_ia(messages: list, system_prompt: str) -> str:
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        return "⚠️ Chave de API não configurada. Adicione GEMINI_API_KEY nos secrets."

    # URL atualizada para v1beta
    url = f"https://generativelanguage.googleapis.com/{API_VERSION}/models/{MODEL}:generateContent?key={api_key}"
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
                erro_json = r.json()
                msg_erro = erro_json.get("error", {}).get("message", "Erro desconhecido")
            except:
                msg_erro = r.text
            return f"❌ Erro HTTP {status}: {msg_erro}"

        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:
        return f"❌ Erro na comunicação: {str(e)}"

# ---------------------------------------------------
# INTERFACE E ESTILIZAÇÃO
# ---------------------------------------------------
img_base64 = get_base64_img(FOTO_PATH)
foto_html = f"<img src='data:image/jpeg;base64,{img_base64}' style='width:42px;height:42px;object-fit:cover;border-radius:50%;'>" if img_base64 else "👤"

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
    .profile-pic {{ width: 42px; height: 42px; border-radius: 50%; margin-right: 12px; }}
    .contact-info {{ color: white; font-family: sans-serif; }}
    .contact-name {{ font-weight: bold; font-size: 15px; margin: 0; }}
    .contact-status {{ font-size: 12px; margin: 0; color: #a8d5a2; }}
    .chat-space {{ margin-top: 80px; }}
    .bubble {{
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        max-width: 75%;
        font-family: sans-serif;
        font-size: 14px;
        box-shadow: 0 1px 1px rgba(0,0,0,0.1);
    }}
    .user {{ background-color: #DCF8C6; margin-left: auto; border-radius: 8px 0 8px 8px; }}
    .bot {{ background-color: #FFFFFF; margin-right: auto; border-radius: 0 8px 8px 8px; }}
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
# LÓGICA DO CHAT
# ---------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = carregar_contexto()

# Exibe mensagens existentes
for msg in st.session_state.messages:
    role_class = "user" if msg["role"] == "user" else "bot"
    st.markdown(f'<div class="bubble {role_class}">{markdown_para_html(msg["content"])}</div>', unsafe_allow_html=True)

# Input do usuário
if prompt := st.chat_input("Como posso ajudar em seu projeto de dados?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(f'<div class="bubble user">{markdown_para_html(prompt)}</div>', unsafe_allow_html=True)

    with st.spinner("Alosa analisando..."):
        resposta = perguntar_ia(st.session_state.messages, st.session_state.system_prompt)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        st.markdown(f'<div class="bubble bot">{markdown_para_html(resposta)}</div>', unsafe_allow_html=True)
        st.rerun()
