# Fase 5 — Provider compatível com a API da OpenAI

## O que foi feito

| Ficheiro | Responsabilidade |
|----------|------------------|
| `providers/openai_compatible.py` | `OpenAICompatibleProvider`: streaming, ferramentas, contagem de tokens, erros. |
| `providers/setup.py` | Regista os fornecedores **configurados** no `.env`. |
| `app/cli.py` | Linha de comandos para testar um modelo real sem interface. |

## Uma classe, vários fornecedores
A API "Chat Completions" da OpenAI tornou-se um padrão de facto. Ollama, GitHub
Models, Gemini e Groq disponibilizam endpoints **compatíveis**. Por isso:

```python
OpenAICompatibleProvider("ollama", api_key="ollama", base_url="http://127.0.0.1:11434/v1")
OpenAICompatibleProvider("gemini", api_key=..., base_url=".../v1beta/openai/")
OpenAICompatibleProvider("openai", api_key=...)   # base_url por defeito
```

Um fornecedor novo compatível é uma **linha de configuração**. Um fornecedor com
protocolo diferente (ex.: Anthropic) é uma nova classe que implementa `LLMProvider`.
Em nenhum dos casos o orquestrador muda.

As diferenças entre servidores "compatíveis" tratam-se com opções:
- `max_tokens_param`: os modelos recentes da OpenAI exigem `max_completion_tokens`;
- `stream_usage`: pedir a contagem de tokens no fim do stream;
- `supports_tools`: modelos sem suporte a ferramentas.

Há também tolerância a um comportamento real: o Ollama às vezes termina com
`finish_reason="stop"` mesmo quando pediu ferramentas.

## Como funciona o streaming de ferramentas
O modelo envia os argumentos de uma ferramenta **aos bocados**:
```
chunk 1: tool_calls[0] = {id: "call_abc", name: "write_file", arguments: '{"path": "src/'}
chunk 2: tool_calls[0] = {arguments: 'api.py", "content": "x"}'}
```
O provider junta os fragmentos por `index` e emite `ToolCallArgumentsDelta` para a
interface (que pode mostrar "a escrever src/api.py…"). No fim valida o JSON
completo. Se for inválido, dá erro `invalid_output`.

## Como os testes funcionam sem internet
Os testes usam o **SDK oficial verdadeiro**. Só a camada de rede é substituída por um
`MockTransport` que responde com streams SSE no formato real da API. Assim testamos a
conversão de pedidos, o streaming, as ferramentas e todos os tipos de erro
(401, 403, 404, 429, 503, servidor desligado).

## Testar no teu PC com o Ollama

1. Instalar o Ollama (https://ollama.com/download/windows) e descarregar um modelo:
   ```powershell
   ollama pull granite3.3:2b
   ```
   Confirma o nome exato em https://ollama.com/library. Com pouca RAM usa modelos de
   2–3B parâmetros; com 16 GB ou mais já dá para modelos de 7–8B.
2. No `backend/`, com o ambiente virtual ativo:
   ```powershell
   python -m app.cli providers
   python -m app.cli models --provider ollama
   python -m app.cli ping --provider ollama --model granite3.3:2b
   python -m app.cli ping --provider ollama --model granite3.3:2b --tools
   ```
   O último comando testa se o modelo consegue usar ferramentas, algo essencial
   para os agentes. **Guarda o resultado**: é um dado útil para a documentação
   (risco R1b da análise).

## Fornecedores gratuitos na cloud (opcional)
Coloca a chave no `.env` (ex.: `GEMINI_API_KEY=...`) e reinicia. O provider aparece em
`python -m app.cli providers`. Os limites de pedidos dos planos gratuitos mudam com
frequência; confirma-os na página de cada fornecedor.
