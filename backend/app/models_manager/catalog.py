"""Modelos recomendados para o MultiMind (a correr localmente com o Ollama).

Os tamanhos são aproximados (versões quantizadas por defeito do Ollama). Qualquer
outro modelo da biblioteca do Ollama pode ser descarregado pelo nome.
"""

CATALOG: list[dict] = [
    {
        "name": "granite3.3:8b",
        "family": "IBM Granite",
        "size_gb": 4.9,
        "recommended": True,
        "description_pt": "Equilibrado; bom a planear, organizar e rever. Agente Granite.",
        "description_en": "Balanced; good at planning, organising and reviewing. Granite agent.",
    },
    {
        "name": "qwen3:8b",
        "family": "Alibaba Qwen",
        "size_gb": 5.2,
        "recommended": True,
        "description_pt": "Forte em código e a usar ferramentas. Agente Qwen.",
        "description_en": "Strong at code and tool use. Qwen agent.",
    },
    {
        "name": "llama3.1:8b",
        "family": "Meta Llama",
        "size_gb": 4.9,
        "recommended": False,
        "description_pt": "Generalista popular; bom terceiro agente para experiências.",
        "description_en": "Popular generalist; a good third agent for experiments.",
    },
    {
        "name": "qwen2.5-coder:7b",
        "family": "Alibaba Qwen",
        "size_gb": 4.7,
        "recommended": False,
        "description_pt": "Especializado em programação.",
        "description_en": "Specialised in programming.",
    },
    {
        "name": "gemma3:4b",
        "family": "Google Gemma",
        "size_gb": 3.3,
        "recommended": False,
        "description_pt": "Leve e rápido; bom para PCs com menos memória.",
        "description_en": "Light and fast; good for PCs with less memory.",
    },
    {
        "name": "granite3.3:2b",
        "family": "IBM Granite",
        "size_gb": 1.5,
        "recommended": False,
        "description_pt": "Muito leve; para testes rápidos ou PCs modestos.",
        "description_en": "Very light; for quick tests or modest PCs.",
    },
    {
        "name": "qwen3:4b",
        "family": "Alibaba Qwen",
        "size_gb": 2.6,
        "recommended": False,
        "description_pt": "Versão leve do Qwen3.",
        "description_en": "Light version of Qwen3.",
    },
]
