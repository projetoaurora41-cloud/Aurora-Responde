"""Clean domain model for SINAM/VIOLBR notifications + import history.

Each row = one notification of violence reported to SINAM. The raw VIOLBRxx
tables in Postgres have ~150 cryptic columns; this model carries only the ~25
fields actually useful for analysis, with codes already translated to human
labels (UF as sigla, race as text, violence types as booleans).

The ETL command `etl_violbr` populates this table from the Postgres source.
"""
from __future__ import annotations

from django.db import models


class Notificacao(models.Model):
    """One SINAM/VIOLBR notification, cleaned up for direct querying."""

    # ---- Identification ---------------------------------------------------
    source_table = models.CharField(
        max_length=10, db_index=True,
        help_text="Tabela de origem: VIOLBR20..VIOLBR24",
    )

    # ---- Dates ------------------------------------------------------------
    data_notificacao = models.DateField(db_index=True)
    data_ocorrencia = models.DateField(null=True, blank=True)
    ano = models.PositiveSmallIntegerField(db_index=True)
    semana_epi = models.PositiveSmallIntegerField(null=True, blank=True)

    # ---- Victim -----------------------------------------------------------
    SEXO_CHOICES = [("M", "Masculino"), ("F", "Feminino"), ("I", "Ignorado")]
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES, db_index=True)
    idade_anos = models.PositiveSmallIntegerField(
        null=True, blank=True, db_index=True,
        help_text="Idade em anos. Bebês <1 ano = 0.",
    )
    faixa_etaria = models.CharField(
        max_length=12, db_index=True,
        help_text="< 1 ano | 1-4 | 5-9 | 10-14 | 15-19 | 20-59 | 60+ | Ignorada",
    )
    raca_cor = models.CharField(max_length=12, blank=True, db_index=True,
                                 help_text="Branca/Preta/Amarela/Parda/Indigena/Ignorada")
    escolaridade = models.CharField(max_length=60, blank=True)
    gestante = models.CharField(max_length=40, blank=True)

    # ---- Geography --------------------------------------------------------
    uf = models.CharField(max_length=2, blank=True, db_index=True,
                          help_text="Sigla da UF de residencia (ex: SP, SE)")
    uf_ocorrencia = models.CharField(max_length=2, blank=True, db_index=True)
    municipio_codigo = models.CharField(max_length=7, blank=True, db_index=True,
                                        help_text="Codigo IBGE do municipio de residencia")
    local_ocorrencia = models.CharField(max_length=60, blank=True,
                                        help_text="Residencia / Via publica / Escola / ...")
    zona = models.CharField(max_length=15, blank=True)

    # ---- Violence flags (10) ----------------------------------------------
    violencia_fisica = models.BooleanField(null=True, db_index=True)
    violencia_psicologica = models.BooleanField(null=True, db_index=True)
    violencia_sexual = models.BooleanField(null=True, db_index=True)
    tortura = models.BooleanField(null=True, db_index=True)
    trafico_pessoas = models.BooleanField(null=True, db_index=True)
    violencia_financeira = models.BooleanField(null=True)
    negligencia = models.BooleanField(null=True, db_index=True)
    violencia_infantil = models.BooleanField(null=True, db_index=True)
    intervencao_legal = models.BooleanField(null=True)
    outras_violencias = models.BooleanField(null=True)

    # ---- Other ------------------------------------------------------------
    lesao_autoprovocada = models.BooleanField(null=True, db_index=True,
                                              help_text="Auto-mutilacao ou tentativa de suicidio")
    ocorreu_outras_vezes = models.BooleanField(null=True,
                                                help_text="Vitima reincidente")
    autor_sexo = models.CharField(max_length=1, blank=True,
                                  help_text="M / F / I (sexo do autor)")
    autor_alcool = models.CharField(max_length=12, blank=True,
                                    help_text="Sim / Nao / Ignorado")

    class Meta:
        ordering = ["-data_notificacao"]
        indexes = [
            models.Index(fields=["uf", "ano"]),
            models.Index(fields=["ano", "violencia_sexual"]),
            models.Index(fields=["ano", "violencia_fisica"]),
        ]
        verbose_name = "Notificação SINAM"
        verbose_name_plural = "Notificações SINAM"

    def __str__(self) -> str:
        return f"{self.data_notificacao} {self.uf} {self.sexo} {self.idade_anos}a"


class ImportacaoDBC(models.Model):
    """Histórico de importações de arquivos .dbc do DataSUS."""

    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("decompressing", "Descomprimindo .dbc"),
        ("inserting", "Inserindo no banco"),
        ("done", "Concluída"),
        ("error", "Erro"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="importacoes_sinam")
    file_name = models.CharField(max_length=255)
    source_table = models.CharField(max_length=20, db_index=True,
                                    help_text="Ex: VIOLBR25")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending",
                              db_index=True)
    stage_detail = models.TextField(blank=True,
                                    help_text="Última mensagem de progresso.")
    rows_inserted = models.PositiveIntegerField(default=0)
    rows_skipped = models.PositiveIntegerField(default=0)
    rows_removed = models.PositiveIntegerField(default=0,
                                                help_text="Linhas anteriores apagadas (replace).")
    decompress_seconds = models.FloatField(null=True, blank=True)
    insert_seconds = models.FloatField(null=True, blank=True)
    total_seconds = models.FloatField(null=True, blank=True)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Importação SINAM"
        verbose_name_plural = "Importações SINAM"

    def __str__(self) -> str:
        return f"{self.file_name} [{self.status}] {self.rows_inserted} linhas"


class Municipio(models.Model):
    """Dicionário IBGE de municípios (5570 entradas). Carregado por seed_municipios."""

    codigo = models.CharField(max_length=7, primary_key=True,
                              help_text="Código IBGE de 7 dígitos.")
    nome = models.CharField(max_length=100, db_index=True)
    nome_normalizado = models.CharField(max_length=100, db_index=True,
                                        help_text="Lowercase, sem acentos — para busca fuzzy.")
    uf = models.CharField(max_length=2, db_index=True)

    class Meta:
        ordering = ["uf", "nome"]
        verbose_name = "Município (IBGE)"
        verbose_name_plural = "Municípios (IBGE)"

    def __str__(self) -> str:
        return f"{self.nome}/{self.uf}"
