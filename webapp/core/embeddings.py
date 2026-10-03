"""Serviço de embeddings compartilhado (sentence-transformers + pgvector).

Usado por todos os chats que precisam de busca semântica (Dados SINAN, Análise
Retrospectiva, ...). Modelo multilíngue local, 384 dimensões, bom para PT.
Sem custo/API — roda no torch que já é dependência do projeto. O modelo é
carregado uma única vez (singleton) na primeira chamada.

Importar este módulo NÃO carrega o torch (o import pesado fica em ``get_model``),
então é seguro referenciá-lo em models.py / apps.py.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Sequence

# Aceita AURORA_EMBED_* (genérico) e cai para SINAN_EMBED_* (compat. histórica).
MODEL_NAME = (os.getenv("AURORA_EMBED_MODEL")
              or os.getenv("SINAN_EMBED_MODEL")
              or "paraphrase-multilingual-MiniLM-L12-v2")
DEVICE = (os.getenv("AURORA_EMBED_DEVICE")
          or os.getenv("SINAN_EMBED_DEVICE")
          or "cpu")

# Dimensão do modelo padrão. Trocar o modelo exige migration nos VectorField.
EMBED_DIM = 384

# Em CPU, oculta a GPU ANTES de qualquer import do torch — o torch build CUDA
# inicializa o contexto da GPU no import e trava se a placa estiver instável.
if DEVICE == "cpu":
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, device=DEVICE)


def embed(texts: Sequence[str], batch_size: int = 64) -> List[List[float]]:
    """Gera embeddings normalizados (cosseno = produto interno) para uma lista."""
    model = get_model()
    vecs = model.encode(
        list(texts), batch_size=batch_size,
        normalize_embeddings=True, show_progress_bar=False,
    )
    return [v.tolist() for v in vecs]


def embed_one(text: str) -> List[float]:
    return embed([text])[0]
