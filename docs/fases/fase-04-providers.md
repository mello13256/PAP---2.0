# Fase 4 — Abstração de providers e AgentRuntime

## O que foi feito

| Ficheiro | Responsabilidade |
|----------|------------------|
| `providers/base.py` | Interface `LLMProvider` e **tipos normalizados** (mensagens, ferramentas, pedido, resposta, eventos de streaming, erros). |
| `providers/fake_provider.py` | Provider **simulado e determinístico**, guiado por um "guião". |
| `providers/registry.py` | Associa nomes (`"fake"`, mais tarde `"openai"`, `"ollama"`…) a implementações. |
| `providers/pricing.py` + `pricing.json` | Estimativa de custo a partir de preços **configurados** (nunca inventados). |
| `agents/runtime.py` | `AgentRuntime` = agente + provider: system prompt, retries, timeout, métricas. |
| `metrics/recorder.py` | Guarda cada chamada em `llm_calls`. |

## As três camadas de um agente

```
AgentSpec (quem)          AgentRuntime (como se comporta)        LLMProvider (transporte)
nome, modelo, prompt  →   aplica prompt/parâmetros          →    stream() / generate()
capacidades               retries + backoff + timeout            fala com UMA API concreta
                          regista métricas (llm_calls)
```

- O **provider** não sabe o que é um agente, uma tarefa ou a base de dados.
- O **runtime** é o único ponto por onde passam todas as chamadas. É por isso que
  as métricas são fiáveis: não há chamadas "por fora".

## Interface do provider

Cada provider só tem de implementar `stream()`, que produz eventos:

```
TextDelta("Analis") → TextDelta("ando a tarefa…") → ToolCallStarted(write_file)
→ ToolCallArgumentsDelta('{"path": …') → ToolCallCompleted(...) → StreamCompleted(resultado)
```

`generate()` (resposta completa de uma vez) é construído automaticamente a partir
do stream. Um provider novo precisa de muito pouco código.

## Erros normalizados

Cada SDK tem as suas exceções. O provider converte-as num `ProviderError` com um
`kind`: `rate_limit`, `timeout`, `unavailable`, `authentication`, `bad_request`,
`invalid_output` ou `unknown`. O resto da aplicação só conhece estes tipos.

## Política de novas tentativas (retries)
- Só erros **transitórios** são repetidos: limite de pedidos, timeout, servidor indisponível.
- Espera crescente entre tentativas (*backoff exponencial*: ~1 s, ~2 s, ~4 s…).
- Máximo de 3 tentativas.
- **Não** se repete se parte da resposta já tiver sido enviada para a interface
  (o texto apareceria duplicado).
- Cada tentativa conta como uma chamada nas métricas (`failed_calls`).

## Timeout "sem atividade"
Um modelo local lento pode demorar minutos a escrever uma resposta longa, e isso é
normal. O que não é normal é ficar **calado**. Por isso o timeout mede o tempo
**entre eventos** (por defeito 120 s), e não o tempo total.

## Custos
Os preços mudam; não os escrevemos no código. `pricing.json` tem os preços por
modelo. Modelos locais/gratuitos custam 0. Sem preço conhecido o custo fica
**vazio**, em vez de um número inventado.

## Porque é que o FakeProvider não é um "mockup"
Serve para **testes automáticos** (43 testes correm em ~2 s, sem internet e sem
gastar pedidos) e para ensaiar o fluxo. Aparece sempre identificado como
"simulado". Nunca substitui os agentes reais na demonstração.

## Como verificar
```powershell
cd backend
pytest -v tests/unit/test_agent_runtime.py
```
