"""SINAN Violence (VIOL) data model.

Holds the subset of fields required to power the 12 Aurora dashboards
described in the project's first technical report.

Field names mirror the SINAN DBF column names (uppercase) so the importer
can map columns directly without translation. All categorical fields are
kept as short strings to preserve SINAN coding (e.g. ``'1'``/``'2'``/``'9'``).
"""

from django.db import models


class ImportBatch(models.Model):
    """One ingestion of a SINAN file (.dbc/.dbf/.csv)."""

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Na fila"),
        (STATUS_RUNNING, "Importando"),
        (STATUS_DONE, "Concluído"),
        (STATUS_ERROR, "Erro"),
    ]

    filename = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField(default=0)
    rows_total = models.IntegerField(default=0)
    rows_imported = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.filename} ({self.rows_imported} rows)"

    @property
    def progress_pct(self) -> float:
        if not self.rows_total:
            return 0.0
        return min(100.0, (self.rows_imported / self.rows_total) * 100.0)


class ViolenceNotification(models.Model):
    """A single SINAN VIOL notification record.

    Stores only the fields exercised by the 11 dashboards / 10 reports.
    """

    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    # --- Temporal ---
    DT_NOTIFIC = models.DateField(null=True, blank=True, db_index=True)
    DT_OCOR = models.DateField(null=True, blank=True)
    SEM_NOT = models.CharField(max_length=6, blank=True, default="")
    NU_ANO = models.CharField(max_length=4, blank=True, default="", db_index=True)
    HORA_OCOR = models.CharField(max_length=8, blank=True, default="")

    # --- Territorial: occurrence ---
    SG_UF_OCOR = models.CharField(max_length=2, blank=True, default="", db_index=True)
    ID_MN_OCOR = models.CharField(max_length=10, blank=True, default="", db_index=True)
    ID_DIS_OCOR = models.CharField(max_length=10, blank=True, default="")
    ID_BA_OCOR = models.CharField(max_length=10, blank=True, default="")
    ZONA_OCOR = models.CharField(max_length=1, blank=True, default="")
    LOCAL_OCOR = models.CharField(max_length=2, blank=True, default="")
    LOCAL_ESPE = models.CharField(max_length=60, blank=True, default="")

    # --- Territorial: residence ---
    SG_UF = models.CharField(max_length=2, blank=True, default="")
    ID_MN_RESI = models.CharField(max_length=10, blank=True, default="")
    ID_DISTRIT = models.CharField(max_length=10, blank=True, default="")
    ID_BAIRRO = models.CharField(max_length=10, blank=True, default="")
    ZONA = models.CharField(max_length=1, blank=True, default="")

    # --- Victim profile ---
    DT_NASC = models.DateField(null=True, blank=True)
    NU_IDADE_N = models.CharField(max_length=4, blank=True, default="", db_index=True)
    CS_SEXO = models.CharField(max_length=1, blank=True, default="")
    CS_RACA = models.CharField(max_length=1, blank=True, default="")
    CS_ESCOL_N = models.CharField(max_length=2, blank=True, default="")
    CS_GESTANT = models.CharField(max_length=1, blank=True, default="")

    # --- Violence type markers (1=Sim / 2=Nao / 9=Ignorado) ---
    VIOL_FISIC = models.CharField(max_length=1, blank=True, default="")
    VIOL_PSICO = models.CharField(max_length=1, blank=True, default="")
    VIOL_TORT = models.CharField(max_length=1, blank=True, default="")
    VIOL_SEXU = models.CharField(max_length=1, blank=True, default="", db_index=True)
    VIOL_TRAF = models.CharField(max_length=1, blank=True, default="", db_index=True)
    VIOL_FINAN = models.CharField(max_length=1, blank=True, default="")
    VIOL_NEGLI = models.CharField(max_length=1, blank=True, default="")
    VIOL_INFAN = models.CharField(max_length=1, blank=True, default="")
    VIOL_LEGAL = models.CharField(max_length=1, blank=True, default="")
    VIOL_OUTR = models.CharField(max_length=1, blank=True, default="")
    VIOL_ESPEC = models.CharField(max_length=30, blank=True, default="")

    # --- Sexual subtypes ---
    SEX_ASSEDI = models.CharField(max_length=1, blank=True, default="")
    SEX_ESTUPR = models.CharField(max_length=1, blank=True, default="")
    SEX_PORNO = models.CharField(max_length=1, blank=True, default="")
    SEX_EXPLO = models.CharField(max_length=1, blank=True, default="", db_index=True)
    SEX_OUTRO = models.CharField(max_length=1, blank=True, default="")

    # --- Repetition ---
    OUT_VEZES = models.CharField(max_length=1, blank=True, default="")

    # --- Probable author ---
    AUTOR_SEXO = models.CharField(max_length=1, blank=True, default="")
    AUTOR_ALCO = models.CharField(max_length=1, blank=True, default="")
    CICL_VID_AUTOR = models.CharField(max_length=1, blank=True, default="")

    # --- Protection network ---
    ENC_SAUDE = models.CharField(max_length=1, blank=True, default="")
    ASSIST_SOC = models.CharField(max_length=1, blank=True, default="")
    REDE_EDUCA = models.CharField(max_length=1, blank=True, default="")
    ATEND_MULH = models.CharField(max_length=1, blank=True, default="")
    CONS_TUTEL = models.CharField(max_length=1, blank=True, default="")
    DIR_HUMAN = models.CharField(max_length=1, blank=True, default="")
    MPU = models.CharField(max_length=1, blank=True, default="")
    DELEG_CRIA = models.CharField(max_length=1, blank=True, default="")
    DELEG_MULH = models.CharField(max_length=1, blank=True, default="")
    DELEG = models.CharField(max_length=1, blank=True, default="")
    INFAN_JUV = models.CharField(max_length=1, blank=True, default="")
    DEFEN_PUBL = models.CharField(max_length=1, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["SG_UF_OCOR", "NU_ANO"]),
            models.Index(fields=["ID_MN_OCOR", "NU_ANO"]),
            models.Index(fields=["VIOL_SEXU"]),
            models.Index(fields=["SEX_EXPLO"]),
            models.Index(fields=["VIOL_TRAF"]),
        ]

    def __str__(self) -> str:
        return f"VIOL #{self.pk} {self.SG_UF_OCOR}/{self.NU_ANO}"


class ViolbrExterno(models.Model):
    """Modelo *não gerenciado* mapeado à tabela bruta ``sinan.VIOLBR``.

    Quando o Aurora roda no PostgreSQL compartilhado (via ``.env``), essa tabela
    já contém os ~3 milhões de notificações VIOL do SINAN. Este modelo permite
    ler esses dados **direto**, como faz o projeto original — sem reimportar
    arquivos. Os nomes dos campos são idênticos aos de :class:`ViolenceNotification`,
    então toda a camada de analytics funciona sem alterações.

    Observações:
    - ``managed = False``: o Django nunca cria/migra/apaga esta tabela.
    - A tabela bruta não tem chave primária. Usamos ``ID_AGRAVO`` (sempre
      preenchido — 0 nulos/vazios nas ~3M linhas) como ``id`` do ORM. Ele é o
      mesmo código de agravo em todas as linhas (não é único), mas as consultas
      são sempre agregações, então unicidade é irrelevante — e ``Count("id")``
      passa a ser ``COUNT("ID_AGRAVO")`` == ``COUNT(*)``.
    - Datas são texto (``'AAAA-MM-DD'``) na origem, por isso ficam como
      ``CharField`` aqui (a série mensal usa ``Substr`` sobre o texto).
    """

    id = models.CharField(primary_key=True, db_column="ID_AGRAVO", max_length=20)

    # Temporal
    DT_NOTIFIC = models.CharField(max_length=10, blank=True, default="")
    NU_ANO = models.CharField(max_length=4, blank=True, default="")
    HORA_OCOR = models.CharField(max_length=8, blank=True, default="")

    # Territorial (ocorrência)
    SG_UF_OCOR = models.CharField(max_length=2, blank=True, default="")
    ID_MN_OCOR = models.CharField(max_length=10, blank=True, default="")
    LOCAL_OCOR = models.CharField(max_length=2, blank=True, default="")

    # Perfil da vítima
    NU_IDADE_N = models.CharField(max_length=4, blank=True, default="")
    CS_SEXO = models.CharField(max_length=1, blank=True, default="")
    CS_RACA = models.CharField(max_length=1, blank=True, default="")
    CS_ESCOL_N = models.CharField(max_length=2, blank=True, default="")

    # Tipos de violência
    VIOL_FISIC = models.CharField(max_length=1, blank=True, default="")
    VIOL_PSICO = models.CharField(max_length=1, blank=True, default="")
    VIOL_TORT = models.CharField(max_length=1, blank=True, default="")
    VIOL_SEXU = models.CharField(max_length=1, blank=True, default="")
    VIOL_TRAF = models.CharField(max_length=1, blank=True, default="")
    VIOL_FINAN = models.CharField(max_length=1, blank=True, default="")
    VIOL_NEGLI = models.CharField(max_length=1, blank=True, default="")
    VIOL_INFAN = models.CharField(max_length=1, blank=True, default="")
    VIOL_LEGAL = models.CharField(max_length=1, blank=True, default="")
    VIOL_OUTR = models.CharField(max_length=1, blank=True, default="")

    # Subtipos sexuais
    SEX_ASSEDI = models.CharField(max_length=1, blank=True, default="")
    SEX_ESTUPR = models.CharField(max_length=1, blank=True, default="")
    SEX_PORNO = models.CharField(max_length=1, blank=True, default="")
    SEX_EXPLO = models.CharField(max_length=1, blank=True, default="")
    SEX_OUTRO = models.CharField(max_length=1, blank=True, default="")

    # Rede de proteção (encaminhamentos)
    ENC_SAUDE = models.CharField(max_length=1, blank=True, default="")
    ASSIST_SOC = models.CharField(max_length=1, blank=True, default="")
    REDE_EDUCA = models.CharField(max_length=1, blank=True, default="")
    ATEND_MULH = models.CharField(max_length=1, blank=True, default="")
    CONS_TUTEL = models.CharField(max_length=1, blank=True, default="")
    DIR_HUMAN = models.CharField(max_length=1, blank=True, default="")
    MPU = models.CharField(max_length=1, blank=True, default="")
    DELEG_CRIA = models.CharField(max_length=1, blank=True, default="")
    DELEG_MULH = models.CharField(max_length=1, blank=True, default="")
    DELEG = models.CharField(max_length=1, blank=True, default="")
    INFAN_JUV = models.CharField(max_length=1, blank=True, default="")
    DEFEN_PUBL = models.CharField(max_length=1, blank=True, default="")

    class Meta:
        managed = False
        # Trick de aspas: vira FROM "sinan"."VIOLBR" (qualificado por schema).
        db_table = 'sinan"."VIOLBR'
