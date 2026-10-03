"""Importação de arquivos .dbc do DataSUS via UI Django.

Fluxo:
  GET  /sinam/importar/        → form + histórico
  POST /sinam/importar/        → salva arquivo + cria ImportacaoDBC + dispara thread
  GET  /sinam/importacoes/<id>/ → status de uma importação (com auto-refresh)
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import tempfile
import threading

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.db import close_old_connections
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .etl import import_dbc_file
from .forms import UploadDBCForm
from .models import ImportacaoDBC, Notificacao


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_import(imp_id: int, dbc_path: str, source_table: str, replace: bool) -> None:
    """Run in a daemon thread. Updates `ImportacaoDBC` as it progresses."""
    # Each thread needs a fresh DB connection in Django.
    close_old_connections()
    imp = ImportacaoDBC.objects.get(pk=imp_id)

    def _progress(stage: str, current: int, total, extra: dict):
        imp.status = stage if stage in dict(ImportacaoDBC.STATUS_CHOICES) else imp.status
        imp.rows_inserted = current
        if "rows_removed" in extra:
            imp.rows_removed = extra["rows_removed"]
        if "decompress_seconds" in extra:
            imp.decompress_seconds = extra["decompress_seconds"]
        if "insert_seconds" in extra:
            imp.insert_seconds = extra["insert_seconds"]
        if "total_seconds" in extra:
            imp.total_seconds = extra["total_seconds"]
        if "skipped" in extra:
            imp.rows_skipped = extra["skipped"]
        # Stage detail string
        parts = [f"{stage}"]
        if extra:
            parts.append(", ".join(f"{k}={v}" for k, v in extra.items()))
        imp.stage_detail = " | ".join(parts)
        imp.save(update_fields=[
            "status", "rows_inserted", "rows_removed", "rows_skipped",
            "decompress_seconds", "insert_seconds", "total_seconds", "stage_detail",
        ])

    try:
        result = import_dbc_file(dbc_path, source_table=source_table,
                                 progress_cb=_progress, replace=replace)
        imp.status = "done"
        imp.finished_at = timezone.now()
        imp.rows_inserted = result["inserted"]
        imp.rows_skipped = result["skipped"]
        imp.decompress_seconds = result["decompress_seconds"]
        imp.insert_seconds = result["insert_seconds"]
        imp.total_seconds = result["total_seconds"]
        imp.stage_detail = "concluida"
        imp.save()
    except Exception as exc:
        log.exception("Falha em ImportacaoDBC id=%s", imp_id)
        imp.status = "error"
        imp.error = f"{type(exc).__name__}: {exc}"
        imp.finished_at = timezone.now()
        imp.save()
    finally:
        try:
            os.unlink(dbc_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def importar(request):
    if request.method == "POST":
        form = UploadDBCForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data["arquivo"]
            source_table = form.cleaned_data["source_table"].upper()
            replace = bool(form.cleaned_data.get("replace"))

            # Save to a temp file we can stream from in a thread
            tmp = tempfile.NamedTemporaryFile(suffix=".dbc", delete=False)
            for chunk in arquivo.chunks():
                tmp.write(chunk)
            tmp.close()

            imp = ImportacaoDBC.objects.create(
                user=request.user,
                file_name=arquivo.name,
                source_table=source_table,
                status="pending",
                stage_detail="upload concluido, aguardando worker",
            )
            t = threading.Thread(
                target=_run_import,
                args=(imp.pk, tmp.name, source_table, replace),
                daemon=True,
                name=f"sinam-import-{imp.pk}",
            )
            t.start()
            flash.success(request,
                          f"Upload de {arquivo.name} iniciado em background. "
                          f"Acompanhe abaixo.")
            return redirect("sinam:importacao_detail", pk=imp.pk)
    else:
        form = UploadDBCForm()

    importacoes = ImportacaoDBC.objects.all()[:20]
    by_table = (Notificacao.objects.values("source_table")
                .order_by("source_table")
                .annotate())  # placeholder; counting below

    # Per-table counts
    from django.db.models import Count
    summary = list(Notificacao.objects.values("source_table")
                   .annotate(total=Count("id"))
                   .order_by("source_table"))

    return render(request, "sinam/importar.html", {
        "form": form,
        "importacoes": importacoes,
        "summary": summary,
        "total_geral": Notificacao.objects.count(),
    })


@login_required
def importacao_detail(request, pk: int):
    imp = get_object_or_404(ImportacaoDBC, pk=pk)
    finished = imp.status in ("done", "error")
    return render(request, "sinam/importacao_detail.html", {
        "imp": imp,
        "finished": finished,
    })
