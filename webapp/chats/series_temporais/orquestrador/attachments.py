"""Extração de texto de anexos do chat "Aurora responde".

Suporta: texto (.txt/.md/.csv/.json), PDF (pypdf) e IMAGENS (.png/.jpg/...).
Imagens passam por OCR via pytesseract quando disponível; sem OCR, o anexo é
aceito mas com um aviso de que o conteúdo visual não pôde ser lido (o Qwen3 não
é multimodal). Guardamos apenas o TEXTO extraído — nada de binário em disco.

Limites (anti-abuso, já que o chat é aberto):
  * ``MAX_ATTACHMENT_BYTES`` por arquivo
  * ``MAX_ATTACHMENTS`` por envio
  * ``MAX_TEXT_CHARS`` de texto extraído por arquivo
"""
from __future__ import annotations

import io
import os

MAX_ATTACHMENT_BYTES = int(os.getenv("AURORA_MAX_ATTACHMENT_BYTES", str(10 * 1024 * 1024)))  # 10 MB
MAX_ATTACHMENTS = int(os.getenv("AURORA_MAX_ATTACHMENTS", "4"))
MAX_TEXT_CHARS = int(os.getenv("AURORA_MAX_ATTACHMENT_CHARS", "60000"))

_TEXT_EXT = (".txt", ".md", ".csv", ".json", ".log")
_PDF_EXT = (".pdf",)
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")


def kind_for(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(_IMAGE_EXT):
        return "image"
    if name.endswith(_PDF_EXT):
        return "pdf"
    return "text"


def is_supported(filename: str) -> bool:
    name = (filename or "").lower()
    return name.endswith(_TEXT_EXT + _PDF_EXT + _IMAGE_EXT)


def _extract_text_bytes(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
        if sum(len(p) for p in parts) > MAX_TEXT_CHARS:
            break
    return "\n".join(parts)


def _extract_image_ocr(data: bytes) -> str:
    """OCR de imagem via pytesseract (se instalado). Sem OCR, devolve aviso."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ("[imagem anexada — OCR indisponível no servidor (instale "
                "pytesseract + Pillow + Tesseract). O conteúdo visual não foi lido.]")
    try:
        img = Image.open(io.BytesIO(data))
        txt = pytesseract.image_to_string(img, lang=os.getenv("OCR_LANG", "por"))
        txt = (txt or "").strip()
        return txt or "[imagem anexada — nenhum texto detectado pelo OCR.]"
    except Exception as exc:  # noqa: BLE001
        return f"[imagem anexada — falha no OCR: {type(exc).__name__}: {exc}]"


def extract(filename: str, data: bytes) -> tuple[str, str]:
    """Extrai (kind, texto) de um anexo. Levanta ValueError se não suportado.

    Não valida tamanho aqui — o chamador deve checar ``MAX_ATTACHMENT_BYTES``
    antes de ler, para não carregar bytes demais em memória.
    """
    if not is_supported(filename):
        raise ValueError("Formato não suportado. Use PDF, imagem (png/jpg) ou "
                         "texto (.txt/.md/.csv/.json).")
    kind = kind_for(filename)
    if kind == "pdf":
        text = _extract_pdf(data)
    elif kind == "image":
        text = _extract_image_ocr(data)
    else:
        text = _extract_text_bytes(data)
    return kind, (text or "")[:MAX_TEXT_CHARS]


def build_context(attachments, max_chars: int = 8000) -> str:
    """Monta o bloco de contexto a partir de anexos (QuerySet/lista de ChatAttachment)."""
    out, total = [], 0
    for a in attachments:
        texto = (a.text or "").strip()
        if not texto:
            continue
        piece = f"--- Anexo: {a.name} ({a.get_kind_display()}) ---\n{texto}"
        if total + len(piece) > max_chars:
            piece = piece[: max(0, max_chars - total)]
        out.append(piece)
        total += len(piece)
        if total >= max_chars:
            break
    return "\n\n".join(out)
