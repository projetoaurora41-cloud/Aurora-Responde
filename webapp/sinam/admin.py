from django.contrib import admin

from .models import ImportacaoDBC, Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = (
        "data_notificacao", "uf", "sexo", "idade_anos", "faixa_etaria",
        "violencia_fisica", "violencia_sexual", "tortura", "local_ocorrencia",
    )
    list_filter = (
        "ano", "uf", "sexo", "faixa_etaria",
        "violencia_fisica", "violencia_sexual", "violencia_psicologica",
        "tortura", "negligencia", "violencia_infantil",
    )
    search_fields = ("municipio_codigo",)
    date_hierarchy = "data_notificacao"


@admin.register(ImportacaoDBC)
class ImportacaoDBCAdmin(admin.ModelAdmin):
    list_display = ("file_name", "source_table", "status", "rows_inserted",
                    "total_seconds", "user", "created_at")
    list_filter = ("status", "source_table")
    readonly_fields = (
        "file_name", "source_table", "rows_inserted", "rows_skipped",
        "rows_removed", "decompress_seconds", "insert_seconds",
        "total_seconds", "stage_detail", "error", "created_at", "finished_at",
    )
