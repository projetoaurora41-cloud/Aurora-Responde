from __future__ import annotations

import re

from django import forms


class UploadDBCForm(forms.Form):
    """Upload de um arquivo .dbc do DataSUS para importação na base limpa."""

    arquivo = forms.FileField(
        label="Arquivo .dbc",
        help_text="Baixe em https://datasus.saude.gov.br/transferencia-de-arquivos/ "
                  "(formato proprietario do DataSUS).",
    )
    source_table = forms.CharField(
        label="Tabela de origem",
        max_length=20,
        help_text="Ex: VIOLBR25. Sera detectado do nome do arquivo se em branco.",
        required=False,
    )
    replace = forms.BooleanField(
        label="Substituir importacao anterior desta tabela",
        required=False, initial=True,
    )

    def clean_arquivo(self):
        f = self.cleaned_data["arquivo"]
        name = (f.name or "").lower()
        if not name.endswith(".dbc"):
            raise forms.ValidationError("O arquivo precisa ter extensao .dbc")
        # 200 MB hard cap
        if f.size > 200 * 1024 * 1024:
            raise forms.ValidationError("Arquivo maior que 200 MB.")
        return f

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("source_table") and cleaned.get("arquivo"):
            stem = (cleaned["arquivo"].name or "").rsplit(".", 1)[0]
            m = re.match(r"^([A-Z]+\d+)", stem.upper())
            if m:
                cleaned["source_table"] = m.group(1)
        if not cleaned.get("source_table"):
            raise forms.ValidationError("Nao consegui detectar a tabela de origem; informe.")
        return cleaned
