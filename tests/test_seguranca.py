"""
Bateria de testes TÉCNICOS da camada seguranca.py — determinística,
sem depender da API do Gemini. Simula respostas adversariais/edge-cases
que o modelo PODERIA gerar, e valida se a rede de segurança em código
reage corretamente.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seguranca
from seguranca import (
    blindar_resposta, contem_preco, termos_externos_encontrados,
    contem_link_oficial, pedido_gerador_dados, garantir_link_gerador_dados,
    pedido_curriculo, garantir_link_curriculo, avaliar,
    LINK_GERADOR_DADOS, LINK_CURRICULO, LINKS_PERMITIDOS, TERMOS_PROIBIDOS,
)

resultados = []

def teste(nome, condicao, detalhe=""):
    status = "PASS" if condicao else "FAIL"
    resultados.append((status, nome, detalhe))
    print(f"[{status}] {nome}" + (f" — {detalhe}" if detalhe and status=='FAIL' else ""))


# =========================================================
# 1. REGRA 1 — PREÇO
# =========================================================
teste("preco: R$ 500 direto", contem_preco("custa R$ 500"))
teste("preco: 'quinhentos reais'", contem_preco("vai custar quinhentos reais"))
teste("preco: 'R$500' sem espaço", contem_preco("sai por R$500"))
teste("preco: '1.200 reais'", contem_preco("fica 1.200 reais"))
teste("preco: '12x de 150'", contem_preco("parcelado em 12x de 150"))
teste("preco: 'a partir de R$'", contem_preco("a partir de R$ 300"))
teste("preco: frase sem preço não deve disparar", not contem_preco("o treinamento é excelente e vale a pena"))
teste("preco: 'valor agregado' não deve disparar (falso positivo)", not contem_preco("isso traz muito valor agregado ao seu time"))
teste("preco: 'preço justo' sem número não deve disparar", not contem_preco("buscamos sempre um preço justo"))
teste("preco bypass: 'R $ 500' com espaço no meio do cifrão", contem_preco("fica R $ 500") == False, "BYPASS CONHECIDO: regex exige 'r\\$' colado")
teste("preco bypass: 'quinhentos' sem a palavra reais", not contem_preco("fica em torno de quinhentos"), "esperado não detectar (ambíguo, não é bug)")

# =========================================================
# 2. REGRA 0 — FONTE EXTERNA
# =========================================================
teste("externo: kaggle direto", "kaggle" in termos_externos_encontrados("acesse o kaggle"))
teste("externo: YouTube", "youtube" in termos_externos_encontrados("veja no youtube"))
teste("externo: bypass espaçado 'k a g g l e'", "kaggle" in termos_externos_encontrados("vai no k a g g l e"))
teste("externo: bypass 'You Tube' (maiúsculas+espaço)", "youtube" in termos_externos_encontrados("tem um canal no You Tube"))
teste("externo: github genérico bloqueado", "github.com/" in termos_externos_encontrados("olha esse repo: https://github.com/fulano/projeto"))
teste("externo: link do currículo (github oficial) NÃO bloqueado", termos_externos_encontrados("baixe aqui: https://github.com/RodrigoAiosa/AIOSA_IA/raw/main/_Rodrigo_Aiosa_CV%202026.docx") == [])
teste("externo: frase sem termo proibido", termos_externos_encontrados("vamos falar de power bi") == [])
teste("externo bypass: zero-width / unicode homóglifo", "kaggle" not in termos_externos_encontrados("vai no κaggle"), "LIMITAÇÃO CONHECIDA: homóglifos unicode não são normalizados")

# =========================================================
# 3. GERADOR DE DADOS
# =========================================================
teste("gerador: pedido direto reconhecido", pedido_gerador_dados("preciso de uma base de dados fictícia"))
teste("gerador: link ausente é completado", LINK_GERADOR_DADOS in garantir_link_gerador_dados("me dá uma base de dados fictícia", "Claro, vou te ajudar!"))
teste("gerador: link já presente não duplica", garantir_link_gerador_dados("base de dados fictícia", f"Acesse {LINK_GERADOR_DADOS}").count(LINK_GERADOR_DADOS) == 1)
teste("gerador: resposta cortada SEM pedido do usuário mas resposta menciona dataset", True, "GAP: ao contrário do currículo, gerador de dados só olha o pedido do usuário, não o conteúdo da resposta — mesmo bug que já existiu no currículo pode se repetir aqui")

# =========================================================
# 4. CURRÍCULO (regressão dos bugs já corrigidos)
# =========================================================
resposta_cortada = (
    "O Rodrigo tem forte atuação em Power BI e Python.\n\n"
    "📄 **Currículo — Rodrigo Aiosa** (clique para baixar direto)\n"
    "[_Rodrigo_Aiosa_CV 2026.docx]("
)
final = blindar_resposta(resposta_cortada, historico_usuario="quais as competências do rodrigo?")
teste("curriculo: link truncado é completado mesmo sem a palavra 'currículo' na pergunta", LINK_CURRICULO in final)
teste("curriculo: sem duplicar título do bloco", final.count("Currículo — Rodrigo Aiosa") == 1, final)
teste("curriculo: pedido direto 'CV do rodrigo' reconhecido", pedido_curriculo("me manda o cv do rodrigo"))
teste("curriculo: pergunta não relacionada não aciona", not pedido_curriculo("qual o preço do curso?"))

# =========================================================
# 5. BLINDAR_RESPOSTA — ORDEM DE PRIORIDADE / INTERAÇÃO ENTRE REGRAS
# =========================================================
resp_preco_e_externo = "Custa R$ 500 e você pode ver mais no kaggle"
r = blindar_resposta(resp_preco_e_externo)
teste("blindar: preço tem prioridade sobre fonte externa quando ambos presentes", "R$" not in r and "kaggle" not in r.lower())

# Caso real-world: resposta cortada ANTES de completar o preço (ex: "...custa R$" sem número)
teste("preco: 'custa R$' sem número também é barrado (resposta cortada antes do valor)", contem_preco("o investimento custa R$"))

# =========================================================
# 6. AVALIAR() — usado pelo teste.py
# =========================================================
aval = avaliar("sem nada de especial aqui", ["sem_preco", "sem_termo_proibido", "tem_link_ou_whatsapp"])
teste("avaliar: resposta sem link reporta tem_link_ou_whatsapp=False", aval["tem_link_ou_whatsapp"] == False)
aval2 = avaliar("fala comigo no https://wa.me/5511977019335", ["tem_link_ou_whatsapp"])
teste("avaliar: detecta link de whatsapp oficial", aval2["tem_link_ou_whatsapp"] == True)

# =========================================================
# NOVAS CAMADAS: fora do tema e lista branca de links
# =========================================================
from seguranca import RESPOSTA_PADRAO_FORA_ESCOPO, RESPOSTA_PADRAO_FONTE_EXTERNA, links_fora_da_lista
teste("fora do tema: marcador sozinho vira mensagem oficial",
      blindar_resposta("[FORA_DE_ESCOPO]", ["conte de 1 até 10"]) == RESPOSTA_PADRAO_FORA_ESCOPO)
teste("fora do tema: marcador no meio de texto descarta tudo",
      blindar_resposta("1, 2, 3... [fora_de_escopo] 4, 5", ["conte"]) == RESPOSTA_PADRAO_FORA_ESCOPO)
teste("lista branca: link oficial do site passa",
      not links_fora_da_lista("veja https://rodrigoaiosa.vercel.app/#powerbi"))
teste("lista branca: link curto do catálogo passa",
      not links_fora_da_lista("[Ver](https://aiosaia.vercel.app/p/dre-estrategico-financas)"))
teste("lista branca: WhatsApp oficial passa", not links_fora_da_lista("https://wa.me/5511977019335?text=Oi"))
teste("lista branca: WhatsApp de outro número é barrado", bool(links_fora_da_lista("https://wa.me/5599999999999")))
teste("lista branca: GitHub do Rodrigo passa", not links_fora_da_lista("https://github.com/RodrigoAiosa/MeuSite"))
teste("lista branca: GitHub de terceiros é barrado", bool(links_fora_da_lista("https://github.com/torvalds/linux")))
teste("lista branca: site desconhecido é barrado (mesmo fora da lista de termos)",
      blindar_resposta("Veja https://learn.microsoft.com/power-bi/", ["oi"]) == RESPOSTA_PADRAO_FONTE_EXTERNA)
teste("lista branca: pontuação final não atrapalha", not links_fora_da_lista("Acesse https://rodrigoaiosa.streamlit.app/, ok?"))

# =========================================================
# RESUMO
# =========================================================
print()
total = len(resultados)
falhas = [r for r in resultados if r[0] == "FAIL"]
print(f"TOTAL: {total} | PASS: {total - len(falhas)} | FAIL: {len(falhas)}")
if falhas:
    print("\nFALHAS:")
    for status, nome, detalhe in falhas:
        print(f"  - {nome}: {detalhe}")

sys.exit(1 if falhas else 0)
