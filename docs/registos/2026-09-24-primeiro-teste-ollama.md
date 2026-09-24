# Registo — primeiro teste com modelos reais (24/09/2026)

**Máquina:** portátil, Windows 11 IoT Enterprise LTSC, 32 GB RAM DDR5,
NVIDIA GeForce RTX 5070 Laptop GPU (8 GB VRAM). Ollama 0.34.4.

**Comando:** `python -m app.cli ping --provider ollama --model <modelo> --tools`
(prompt: "Apresenta-te numa frase, em português."; ferramenta `submit_answer` "forçada")

| Modelo | Sucesso | Tokens (entrada→saída) | Latência | Chamou a ferramenta? |
|--------|---------|------------------------|----------|----------------------|
| granite3.3:8b | sim | 190 → 56 | 46,8 s | **não** |
| qwen3:8b | sim | 160 → 177 | 20,2 s | **não** |

## Observações
- Os dois modelos responderam em português, corretamente, e a custo 0.
- A primeira latência inclui o **carregamento do modelo para a GPU**. As chamadas
  seguintes devem ser mais rápidas (a confirmar).
- Com 8 GB de VRAM, os dois modelos de ~5 GB **não cabem ao mesmo tempo na GPU**.
  Alternar entre eles obriga a recarregar, o que tem custo em tempo.
- **Nenhum chamou a ferramenta, apesar de `tool_choice` a exigir.** Hipóteses:
  (1) o servidor compatível do Ollama ignora `tool_choice`; (2) o prompt não
  mencionava a ferramenta.

## Ação tomada
- O provider compatível passou a repetir o pedido da ferramenta **por instrução** no
  system prompt (DT-07).
- `app.cli ping --tools` passou a usar um prompt que pede a ferramenta e avisa quando
  ela não é chamada.
- Próximo teste: repetir com estas alterações.

---

## Segundo teste (depois das alterações)

Prompt: "Qual é a capital de Portugal? Responde usando a ferramenta submit_answer."

| Modelo | Tokens | Latência | Resultado |
|--------|--------|----------|-----------|
| granite3.3:8b | 131 → 52 | 4,4 s | Escreveu a chamada **como texto JSON** (```python {"function_call": …}```), sem usar o mecanismo nativo |
| qwen3:8b | 187 → 140 | 6,6 s | ✅ Chamada **nativa**: `submit_answer({'answer': 'A capital de Portugal é Lisboa.', 'confidence': 0.99})` |
| granite3.3:8b (repetição) | 131 → 52 | 4,4 s | Igual ao primeiro: comportamento consistente |

### Conclusões
- Com o modelo já na GPU, a latência cai de ~47 s para **~4–7 s**.
- O pedido por instrução resolveu o Qwen3.
- O Granite percebe a ferramenta e produz os argumentos corretos, mas no formato
  errado. **Não é falta de capacidade, é o formato de saída.**

### Ação tomada
Nova camada de **recuperação de chamadas escritas como texto**
(`providers/text_tool_calls.py`, DT-09). O teste automático usa a resposta real do
Granite. As chamadas recuperadas ficam marcadas (`tool_calls_from_text`) para
poderem ser contadas nas experiências.
