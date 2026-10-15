"""Confere se api/_seguranca.js devolve o mesmo que seguranca.py (mesmos casos)."""
import json, subprocess, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from seguranca import blindar_resposta, LINK_CURRICULO, LINK_GERADOR_DADOS

CASOS = [
 ("O curso custa R$ 500", "quanto custa"),
 ("O valor é 300 reais", ""),
 ("Veja o canal no YouTube", "me indica"),
 ("Veja o canal no Y o u T u b e", "x"),
 ("Kaggl e tem bases", "x"),
 ("k a g g l e é bom", "x"),
 ("Baixe aqui [_Rodrigo_Aiosa_CV 2026.docx](" + LINK_CURRICULO + ")", "currículo do rodrigo"),
 ("Veja o currículo dele: [_Rodrigo_Aiosa_CV 20", "tem currículo?"),
 ("Veja o currículo dele:\n📄 **Currículo — Rodrigo Aiosa** (clique para baixar direto)\n[_Rodrigo_Aiosa_CV", ["curriculo"]),
 ("Rodrigo domina Power BI e Python.", ["quais as competências e a trajetória profissional do rodrigo?"]),
 ("Rodrigo domina Power BI.", ["oi"]),
 ("Use a ferramenta [Acessar o gerad", ["quero dados fictícios"]),
 ("Claro! O gerador de dados do Rodrigo ajuda.", []),
 ("Olá! Sou o Alosa.", None),
 ("Fale no wa.me/5511977019335 ou rodrigoaiosa@gmail.com", ["oi"]),
 ("Projetos em https://github.com/RodrigoAiosa/AIOSA_IA ok", ["oi"]),
 ("Veja github.com/outrapessoa/repo", ["oi"]),
 ("Preço a combinar", ["oi"]),
 ("O preço é 99", ["oi"]),
 ("São 10 x de 50", ["oi"]),
 ("Treinamento de ação e acentuação — preço justo? não", ["oi"]),
 ("Você pode ver o CV dele aqui:", ["cv dele?"]),
 ("Dataset de vendas", "me dá uma base de dados fictícia"),
 ("[texto](", ["dados falsos"]),
 ("", ["oi"]),
 ("[FORA_DE_ESCOPO]", ["conte de 1 até 10"]),
 ("1, 2, 3 [fora_de_escopo] texto extra", ["conte"]),
 ("Claro! O curso custa R$ 300 [FORA_DE_ESCOPO]", ["x"]),
]
saida = subprocess.run(
    ["node", "-e", """
const {blindarResposta}=require('./api/_seguranca.js');
const casos=JSON.parse(require('fs').readFileSync(0,'utf8'));
console.log(JSON.stringify(casos.map(([r,h])=>blindarResposta(r,h))));
"""], input=json.dumps(CASOS), capture_output=True, text=True,
    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if saida.returncode: print(saida.stderr); sys.exit(1)
js = json.loads(saida.stdout)
falhas = 0
for (r, h), j in zip(CASOS, js):
    p = blindar_resposta(r, h)
    if p != j:
        falhas += 1
        print("DIVERGE:", repr(r)[:70], h, "\n  py:", repr(p)[:90], "\n  js:", repr(j)[:90])
print(f"{len(CASOS)-falhas}/{len(CASOS)} casos idênticos entre Python e JS")
sys.exit(1 if falhas else 0)
