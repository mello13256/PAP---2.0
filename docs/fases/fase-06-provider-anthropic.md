# Fase 6 — Provider Anthropic (Claude)

## O que foi feito
- `providers/anthropic_provider.py`: `AnthropicProvider`, com o **SDK oficial** da
  Anthropic (API Messages), streaming, ferramentas, contagem de tokens e erros.
- Registado automaticamente quando `ANTHROPIC_API_KEY` está definida.
- Modelo sugerido para um agente Claude: `claude-opus-5` (configurável por agente).

> Com orçamento zero (DT-01) este provider não é usado nas experiências, mas está
> implementado e testado. Mostra que a arquitetura suporta protocolos diferentes e
> fica pronto a usar no dia em que houver uma chave.

## Porque é que a Anthropic precisa de uma classe própria
A API Messages não é compatível com a Chat Completions. As diferenças ficam todas
**dentro** deste ficheiro:

| Aspeto | Compatível OpenAI | Anthropic |
|--------|-------------------|-----------|
| System prompt | mensagem `role: system` | parâmetro `system` |
| Pedido de ferramenta | `tool_calls` na mensagem | bloco `tool_use` no conteúdo |
| Resultado de ferramenta | mensagem `role: tool` | bloco `tool_result` numa mensagem `user` (todos juntos) |
| Esquema da ferramenta | `function.parameters` | `input_schema` |
| Tokens no stream | último chunk (`include_usage`) | eventos `message_start` / `message_delta` |

O orquestrador nunca vê estas diferenças: recebe sempre `TextDelta`,
`ToolCallStarted`, `ToolCallCompleted`, `StreamCompleted`…

## Três detalhes que só se descobrem lendo a documentação atual

1. **"Thinking" tem de ser devolvido intacto.** Os modelos Claude atuais pensam antes
   de responder (blocos `thinking`, com uma assinatura). Numa sequência "pede
   ferramenta → recebe resultado → continua", esses blocos têm de ser reenviados
   **exatamente como vieram**. Solução: a abstração ganhou um campo opaco
   `provider_payload`. O provider guarda lá o conteúdo original e volta a usá-lo
   quando a mensagem regressa no histórico. O resto da aplicação não sabe o que
   lá está dentro. (Teste: `test_thinking_blocks_are_sent_back_unchanged_in_tool_loops`.)
2. **Sem `temperature`.** Os modelos atuais rejeitam-na e o SDK 1.x já nem aceita o
   parâmetro. A temperatura configurada num agente Claude é ignorada.
3. **Forçar uma ferramenta é rejeitado por alguns modelos.** Em vez de
   `tool_choice = "usa a ferramenta X"`, enviamos `tool_choice = auto` e uma instrução
   no system prompt. Funciona em todos os modelos. O orquestrador vai verificar se
   a ferramenta foi realmente chamada, o que será necessário também para os modelos
   locais pequenos.

## Novos casos na abstração comum
- `StopReason.REFUSAL`: o modelo recusou responder.
- `ProviderErrorKind.QUOTA`: sem créditos (erro 402), não vale a pena repetir.
- `GenerationResult.provider_payload` / `ChatMessage.from_result()`.

## Como verificar
```powershell
cd backend
pytest -v tests/unit/test_anthropic_provider.py
# com chave (opcional, pago):
python -m app.cli ping --provider anthropic --model claude-opus-5
```
