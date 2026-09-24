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
