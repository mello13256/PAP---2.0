# Registo de Decisões Técnicas

> O MultiMind tem um *Decision Log* para as decisões dos agentes. Este ficheiro é o
> equivalente para as decisões **do projeto**: o que se decidiu, porquê, e o que
> mudou em relação ao plano inicial (`00-analise-tecnica.md`).
>
> Formato: contexto → decisão → justificação → consequências.

---

## DT-01 — Orçamento zero para APIs

**Contexto.** O orçamento para chamadas a APIs pagas é **0 €**. A API da OpenAI e a
API da Anthropic são pagas (não têm plano gratuito). O Claude Code, usado para
*desenvolver* o projeto, não pode ser usado como agente *dentro* da aplicação.

**Decisão.**
1. Os providers `OpenAIProvider` e `AnthropicProvider` **são implementados na mesma**
   (são parte do conceito e da arquitetura), testados com respostas simuladas, e
   funcionam no dia em que existir uma chave.
2. Para correr agentes reais a custo zero, usamos fornecedores **gratuitos**:
   - **Ollama** (local, no próprio PC): modelos abertos como **IBM Granite**, Llama, Qwen, Gemma.
   - **Planos gratuitos na cloud** com API compatível com OpenAI (sem cartão de
     crédito, com limites de pedidos): GitHub Models, Google Gemini, Groq, OpenRouter.
     Os limites exatos mudam e têm de ser confirmados na altura.
3. O `OpenAIProvider` aceita um `base_url` configurável. Como Ollama, GitHub Models,
   Gemini e Groq expõem APIs **compatíveis com a da OpenAI**, uma única classe serve
   vários fornecedores, cada um registado com o seu nome, URL e chave.

**Justificação.** Mantém o objetivo da PAP (vários LLMs de fornecedores diferentes a
colaborar) sem custos. Mostra também a extensibilidade: um fornecedor novo passa a
ser uma **entrada de configuração**, sem código novo.

**Consequências.**
- A demo pode usar, por exemplo, *Granite (local)* + *um modelo GPT via GitHub
  Models* ou + *Gemini*: continuam a ser famílias de modelos diferentes a colaborar.
- Modelos locais pequenos são **menos fiáveis** a usar ferramentas (tool calling).
  O desenho passa a prever um **modo de fallback**: pedir JSON estruturado no texto
  e validá-lo, quando o modelo não suporta ferramentas de forma fiável.
- As métricas de custo mostram 0 para modelos locais/gratuitos. O custo estimado
  continua calculado pela tabela de preços, que fica disponível para modelos pagos.
- Os limites de pedidos dos planos gratuitos tornam-se o recurso escasso. Os
  `Guards` (limite de chamadas por run) passam a ser ainda mais importantes.

---

## DT-02 — SQLite em vez de PostgreSQL

**Contexto.** Windows 11 IoT Enterprise LTSC, **sem Docker**. A análise inicial
propunha PostgreSQL via Docker Compose.

**Decisão.** A base de dados por defeito passa a ser **SQLite**, em modo **WAL**
(Write-Ahead Logging), com `busy_timeout` e chaves estrangeiras ativas. O código
continua compatível com PostgreSQL: basta mudar `DATABASE_URL`.

**Justificação.**
- O SQLite não precisa de instalação nem de serviço: é um ficheiro. Ideal para
  instalar no Windows e para levar para a defesa.
- O argumento contra o SQLite era o bloqueio em escritas concorrentes. Com WAL,
  as leituras não bloqueiam as escritas. A aplicação corre num único processo,
  com pouca concorrência. O `busy_timeout` faz as escritas esperarem em vez de falharem.
- O SQLAlchemy abstrai as diferenças. Evitámos tipos exclusivos do PostgreSQL
  (`ARRAY`, `JSONB`) e usamos `JSON` genérico.

**Consequências.** Relações circulares entre tabelas foram eliminadas do modelo:
- `artifacts.current_version_id` passa a `artifacts.current_version` (número);
- `decisions.chosen_proposal_id` passa a `decision_proposals.is_chosen`.

Fica mais simples e evita problemas de migração no SQLite.

---

## DT-03 — Sem sandbox de execução de código

**Contexto.** A execução segura de código gerado exigia contentores Docker.

**Decisão.** A execução automática de código fica **fora do âmbito** da PAP. Os
testes gerados pelos agentes são **revistos** por outro agente, não executados.
Fica documentado como trabalho futuro.

---

## DT-04 — Interface bilingue (PT/EN)

**Decisão.** Interface em português e inglês, com seletor de idioma. Usamos um
dicionário de traduções próprio e tipado em TypeScript. Uma chave em falta é um
erro de compilação. Não usamos biblioteca de i18n. O conteúdo gerado pelos agentes
é mostrado no idioma em que foi escrito.

**Justificação.** Com duas línguas e um número moderado de textos, um dicionário
tipado é suficiente, não tem dependências e é fácil de explicar.

---

## DT-05 — Replaneamento do âmbito (≈ 6 h/semana)

**Contexto.** Cerca de 6 horas por semana disponíveis.

**Decisão.**
- O código é produzido com o apoio do Claude Code. As horas do aluno vão sobretudo
  para **compreender, testar no Windows, experimentar e documentar**, que é o que
  conta na defesa.
- Prioridade absoluta: **Marco 1** (núcleo demonstrável). Marco 2 a seguir. Do
  Marco 3 fica apenas "terceiro provider" (já coberto por DT-01) e exportação ZIP/Git.
- Cada fase fica num commit próprio, com testes e uma explicação em `docs/fases/`,
  para poder ser estudada ao ritmo de cada semana.

---

## DT-06 — Instalação sem `winget`

**Contexto.** As edições LTSC do Windows não trazem a Microsoft Store, pelo que o
`winget` pode não estar disponível.

**Decisão.** O guia de instalação (`docs/guia-instalacao-windows.md`) usa os
instaladores oficiais: python.org, nodejs.org, git-scm.com e ollama.com.
Usamos `pip` + `venv` (ferramentas padrão do Python) em vez de gestores extra.

---

## DT-07 — Ferramenta "obrigatória" pedida por instrução

**Contexto.** Para obter respostas estruturadas (plano, revisão, resultado), o
orquestrador pede ao modelo que chame uma ferramenta específica (`submit_plan`, …).
Alguns modelos recentes da Anthropic rejeitam forçar uma ferramenta, e os modelos
locais pequenos nem sempre obedecem.

**Decisão.** A abstração continua a ter `ToolChoice.force(nome)`. Cada provider
traduz como puder: o compatível-OpenAI envia `tool_choice`, e o da Anthropic envia
`auto` e uma instrução explícita. **O orquestrador nunca assume que a ferramenta foi
chamada**: verifica, e se não foi, pede de novo (com limite) ou usa o modo de
fallback JSON (DT-01).

---

## DT-08 — Campo opaco `provider_payload`

**Contexto.** A Anthropic exige que os blocos de "thinking" sejam reenviados intactos
no histórico de uma conversa com ferramentas.

**Decisão.** `GenerationResult` e `ChatMessage` têm um campo `provider_payload` opaco.
Só o provider que o criou o interpreta; os outros ignoram-no. A abstração continua
genérica e não fica a conhecer os detalhes da Anthropic.
