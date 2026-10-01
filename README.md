# Alosa — Agente de Vendas em IA

Chatbot em **Streamlit**, com interface simulando o WhatsApp, que atua como agente comercial automatizado de **Rodrigo Aiosa** — vendendo treinamentos, mentorias e projetos de **Power BI, Python, SQL e Excel/VBA**.

🔗 **App em produção:** https://rodrigoaiosa.streamlit.app/Alosa_IA

---

## O que o Alosa faz

- Conversa com visitantes do site em tom consultivo e comercial, sempre conduzindo para um dos produtos do Rodrigo (treinamento para empresas, projetos de Power BI ou curso online).
- Responde dúvidas técnicas pontuais de Excel/VBA, Power BI, Python e SQL — sem entregar de graça um serviço completo (aula do zero, projeto pronto etc.).
- Nunca informa preço: sempre redireciona para o WhatsApp do Rodrigo para um diagnóstico personalizado.
- Nunca cita fonte externa (Kaggle, YouTube, concorrentes, etc.) — só o conteúdo oficial do Rodrigo.
- Indica a ferramenta de geração de dados fictícios para Power BI quando o usuário pede.
- Envia todos os links de portfólio (Power BI, Python e Cases de Sucesso) juntos, quando perguntado sobre projetos.
- Envia o link de download do currículo do Rodrigo quando perguntado sobre ele.
- Ao demonstrar interesse em falar com o Rodrigo, gera um link do WhatsApp com o **histórico da conversa já preenchido** como texto, para o Rodrigo ter contexto completo ao assumir o atendimento.

---

## Arquitetura

```
app.py            → interface Streamlit (UI estilo WhatsApp) + orquestração da conversa
instrucoes.txt     → system prompt: TODAS as regras de negócio e estilo do agente
seguranca.py       → rede de segurança em código (defesa em profundidade)
teste.py           → suíte de testes automatizados (QA de conformidade)
.github/workflows/ → CI que roda teste.py a cada mudança nas regras
requirements.txt   → dependências Python
```

### Por que existe `seguranca.py` além do `instrucoes.txt`?

O modelo de IA (Gemini) segue o `instrucoes.txt` na maior parte do tempo, mas nenhum LLM obedece 100% das instruções em 100% dos casos — seja por limite de tokens cortando uma resposta no meio, alucinação, ou tentativa de jailbreak do usuário. Por isso, `seguranca.py` implementa as regras **mais críticas** (preço, fonte externa, links obrigatórios) como validação determinística em código Python, aplicada **depois** de cada resposta do modelo e **antes** de exibi-la ao usuário (`blindar_resposta()`). Se o modelo falhar em seguir uma regra, o código corrige ou substitui a resposta — o usuário nunca vê a falha.

Esse mesmo módulo é importado tanto por `app.py` (produção) quanto por `teste.py` (QA), garantindo que os dois usem exatamente os mesmos critérios.

### Fluxo de uma mensagem

1. Usuário digita no chat → mensagem é escapada (HTML) e exibida.
2. `app.py` monta o histórico + `instrucoes.txt` e chama a API do Gemini (`perguntar_ia`), com retry/backoff em caso de erro 429/5xx.
3. A resposta bruta passa por `blindar_resposta()` — valida/corrige preço, fonte externa, link do gerador de dados e link do currículo.
4. Qualquer link de WhatsApp na resposta é enriquecido com o histórico da conversa (texto pré-preenchido).
5. A troca é registrada em `conversas_log.csv` (log leve, efêmero no Streamlit Cloud).
6. A resposta é exibida com efeito de "digitando".

---

## Configuração

### Pré-requisitos

- Python 3.11+
- Uma API key do Gemini ([Google AI Studio](https://aistudio.google.com/))

### Instalação local

```bash
git clone https://github.com/RodrigoAiosa/AIOSA_IA.git
cd AIOSA_IA
pip install -r requirements.txt
```

Crie o arquivo `.streamlit/secrets.toml` com:

```toml
GEMINI_API_KEY = "sua_chave_aqui"
```

Rode o app:

```bash
streamlit run app.py
```

### Deploy

O app roda em produção no **Streamlit Community Cloud**, apontando para este repositório (branch `main`). A `GEMINI_API_KEY` é configurada nos *Secrets* do app no painel do Streamlit Cloud — nunca é commitada no código.

> ⚠️ O sistema de arquivos do Streamlit Cloud é efêmero: `conversas_log.csv` pode ser apagado a cada reboot/redeploy. Não é um banco de dados — é um log de melhor esforço.

---

## Testes (QA de conformidade)

`teste.py` roda ~15 cenários reais contra a API do Gemini (preço, fonte externa, jailbreak, intenção de compra, objeções, etc.) e valida cada resposta com os mesmos critérios de `seguranca.py`, gerando um relatório em `relatorio_testes_alosa_automatico.md`.

```bash
export GEMINI_API_KEY="sua_chave_aqui"
python teste.py
```

Cada cenário reporta dois resultados:
- a resposta **crua** do modelo (se o Gemini está seguindo o prompt);
- a resposta **final**, depois de passar por `blindar_resposta()` (o que o usuário realmente vê).

Isso evidencia se a rede de segurança está "tapando buraco" com frequência — sinal de que vale revisar `instrucoes.txt`, mesmo com a blindagem funcionando.

### CI

O workflow `.github/workflows/teste-alosa.yml` roda `teste.py` automaticamente a cada push que altera `instrucoes.txt`, `seguranca.py` ou `teste.py`, usando o secret `GEMINI_API_KEY` do repositório. O relatório fica disponível como artefato da execução, na aba *Actions*.

---

## Segurança

Principais proteções implementadas em `seguranca.py` e `app.py`:

- **Nunca revelar o prompt**: regra de prioridade máxima contra extração/engenharia reversa do system prompt.
- **Validação de preço e fonte externa** independente do LLM (regex + múltiplas camadas contra bypass por espaçamento/ofuscação).
- **Sanitização contra CSV/Formula Injection** no log de conversas (`_sanitizar_campo_csv`).
- **Escape de HTML** em toda entrada do usuário e saída do modelo antes de renderizar (proteção contra XSS).
- **Links oficiais centralizados** (`LINKS_PERMITIDOS`) como única fonte de verdade, evitando divergência entre regras.
- **Garantia de links críticos** (gerador de dados, currículo): se a resposta do modelo for cortada no meio do link por limite de tokens, o código completa ou substitui pela versão correta, sem perder o restante do conteúdo já gerado.
- **Mensagens de erro genéricas** ao usuário final — detalhes técnicos (status HTTP, exceções) só vão para o log do servidor.

---

## Stack

- [Streamlit](https://streamlit.io/) — interface web
- [Google Gemini API](https://ai.google.dev/) (`gemini-2.5-flash`) — modelo de linguagem
- Python puro para a rede de segurança e os testes (sem frameworks adicionais)

---

## Autor

**Rodrigo Aiosa** — Power BI, Python, SQL, Excel/VBA e Deep Learning.
Site: https://rodrigoaiosa.streamlit.app/
