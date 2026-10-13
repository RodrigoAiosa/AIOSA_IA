"""Esconde o selo "Hosted with Streamlit", a foto do dono e o botão "Manage app".

O Streamlit Cloud injeta esses itens fora da área do app, com nomes de classe
que mudam. O CSS em app.py cobre os nomes conhecidos; este script reforça,
achando os itens pelo conteúdo (texto ou link para streamlit.io/cloud) na
página que envolve o app, quando o navegador permite o acesso (mesma origem).
Mesma técnica usada no AtlasAPI e no BI Data Generator.
"""

import streamlit as st

_SCRIPT = """<script>
        (function() {
            // Documentos que tentamos limpar: o do app (parent) e, se o navegador
            // permitir (mesma origem), o da página que o envolve (top) — é nele que
            // o Streamlit Cloud costuma pôr o "Manage app". Se for outra origem o
            // acesso lança erro e simplesmente ignoramos.
            const docs = [];
            [window.parent, window.top].forEach(w => {
                try { if (w && w.document && !docs.some(d => d.w === w)) docs.push({w: w, doc: w.document}); } catch (e) {}
            });
            const TEXTOS = /^(hosted with streamlit|manage app)$/i;
            function esconder({w, doc}) {
                try {
                    const alvos = new Set();
                    doc.querySelectorAll('a[href*="streamlit.io/cloud"]').forEach(a => alvos.add(a));
                    doc.querySelectorAll('body *').forEach(el => {
                        if (el.children.length === 0 && TEXTOS.test((el.textContent || '').trim())
                            && (el.textContent || '').length < 40) alvos.add(el);
                    });
                    // foto de perfil do dono (avatar) fixa no canto inferior direito
                    doc.querySelectorAll('img').forEach(img => {
                        const r = img.getBoundingClientRect();
                        const vw = w.innerWidth, vh = w.innerHeight;
                        if (r.width > 0 && r.width <= 90 && r.height <= 90 &&
                            r.right > vw - 170 && r.bottom > vh - 130) {
                            let n = img, fixo = false;
                            for (let i = 0; i < 8 && n && n !== doc.body; i++, n = n.parentElement) {
                                if (w.getComputedStyle(n).position === 'fixed') { fixo = true; break; }
                            }
                            if (fixo) alvos.add(img);
                        }
                    });
                    alvos.forEach(el => {
                        // sobe até o contêiner posicionado (fixed) do selo/botão, sem passar do <body>
                        let alvo = el, n = el;
                        for (let i = 0; i < 8 && n && n !== doc.body; i++, n = n.parentElement) {
                            if (w.getComputedStyle(n).position === 'fixed') { alvo = n; break; }
                        }
                        alvo.style.setProperty('display', 'none', 'important');
                    });
                } catch (e) {}
            }
            docs.forEach(d => {
                try { new MutationObserver(() => esconder(d)).observe(d.doc.body, { childList: true, subtree: true }); } catch (e) {}
                esconder(d);
            });
        })();
        </script>
"""


def esconder_selo_streamlit() -> None:
    if hasattr(st, "iframe"):
        st.iframe(_SCRIPT, height=1)
    else:  # versões do Streamlit sem st.iframe
        import streamlit.components.v1 as components
        components.html(_SCRIPT, height=1)
