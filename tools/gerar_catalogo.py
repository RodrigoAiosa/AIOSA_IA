#!/usr/bin/env python3
"""
Gera o catálogo de projetos do Alosa a partir do index.html do MeuSite
(arrays PBI_PROJECTS e PY_PROJECTS).

Uso:  python3 tools/gerar_catalogo.py /caminho/para/MeuSite/index.html

Atualiza, sem mexer no resto:
  - instrucoes.txt   -> bloco entre [[CATALOGO]] e [[/CATALOGO]]
  - vercel.json      -> redirects /p/<id> -> link real (links curtos no chat)
  - api/_catalogo.json -> nome + link curto (usado pela garantia de links no api/chat.js)
"""
import json, re, sys, unicodedata, os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMINIO = "https://aiosaia.vercel.app"
IGNORAR = {"BI Data Generator PRO"}  # conflita com a REGRA do gerador de dados

AREA_PY = {
 "API Atlas": "Tecnologia / APIs públicas", "Jogo de Xadrez": "Jogos / entretenimento",
 "Conjectura de Collatz": "Matemática / educacional", "Calculadora ROI de Consórcio": "Financeiro",
 "Consórcio Educa": "Financeiro", "Calculadora de Honorários Advocatícios": "Jurídico / advocacia",
 "Biblioteca de Comandos para ChatGPT": "Produtividade / IA", "Big Mac Index Dashboard": "Economia / mercado financeiro",
 "Painel de Arboviroses — Brasil": "Saúde pública", "DAX 2048": "Educação / treinamento em Power BI",
 "Salário Médio por Estado": "RH / mercado de trabalho", "Olho Vivo Dashboard": "Transporte / logística (tempo real)",
 "Processador Inteligente de CEPs": "Logística / endereços / entregas", "População Brasil": "Dados públicos / demografia",
 "Renda por Município — SP": "Dados públicos / economia regional", "Simulador ENEM gratuito": "Educação",
 "Calculadora ROI de Automação": "Operações / automação / financeiro", "APP S.O.S. Mulher": "Social / dados públicos",
}

def nome_limpo(t): return re.sub(r"^[^\wÀ-ÿ]+", "", t).strip()
def slug(n):
    n = unicodedata.normalize("NFD", n.lower())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")

def ler(src, nome):
    bloco = re.search(r"const " + nome + r" = \[(.*?)\n\];", src, re.S).group(1)
    return [dict(t=m.group(1), c=m.group(2), u=m.group(3).replace("&amp;", "&"), d=m.group(4))
            for m in re.finditer(r'\{ t: "(.*?)",(?: c: "(.*?)",)? u: "(.*?)", d: "(.*?)" \}', bloco)]

def main(caminho):
    src = open(caminho, encoding="utf-8").read()
    projetos = []
    for p in ler(src, "PBI_PROJECTS"):
        projetos.append(dict(nome=nome_limpo(p["t"]), area=p["c"], tec="Power BI", d=p["d"], u=p["u"]))
    for p in ler(src, "PY_PROJECTS"):
        n = nome_limpo(p["t"])
        if n in IGNORAR: continue
        projetos.append(dict(nome=n, area=AREA_PY.get(n, "Dados / aplicações web"), tec="Python (app web)", d=p["d"], u=p["u"]))

    usados = set()
    for p in projetos:
        s = slug(p["nome"]); base = s; i = 2
        while s in usados: s = f"{base}-{i}"; i += 1
        usados.add(s); p["id"] = s; p["curto"] = f"{DOMINIO}/p/{s}"

    texto = "\n".join(
        f"- Nome: {p['nome']}\n  Área/setor: {p['area']}\n  Tecnologia: {p['tec']}\n"
        f"  O que resolve: {p['d']}\n  Link: {p['curto']}" for p in projetos)

    f = os.path.join(RAIZ, "instrucoes.txt"); s = open(f, encoding="utf-8").read()
    if "[[CATALOGO]]" not in s:
        # primeira execução: coloca marcadores ao redor das entradas já existentes
        ini = s.index("\n- Nome: ", s.index("Formato de cada bloco") + 200)
        fim = s.index("\n\n---", ini)
        s = s[:ini] + "\n[[CATALOGO]]\n[[/CATALOGO]]" + s[fim:]
    s = re.sub(r"\[\[CATALOGO\]\].*?\[\[/CATALOGO\]\]", lambda m: "[[CATALOGO]]\n" + texto + "\n[[/CATALOGO]]", s, flags=re.S)
    open(f, "w", encoding="utf-8").write(s)

    f = os.path.join(RAIZ, "vercel.json"); v = json.load(open(f, encoding="utf-8"))
    v["redirects"] = [{"source": f"/p/{p['id']}", "destination": p["u"], "permanent": False} for p in projetos]
    json.dump(v, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2); open(f, "a").write("\n")

    f = os.path.join(RAIZ, "api", "_catalogo.json")
    json.dump([{"nome": p["nome"], "link": p["curto"]} for p in projetos], open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(projetos)} projetos: instrucoes.txt, vercel.json e api/_catalogo.json atualizados")

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
