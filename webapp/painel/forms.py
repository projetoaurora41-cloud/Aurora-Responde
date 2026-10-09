"""Filtros do painel Aurora."""

from __future__ import annotations

from django import forms


class DashboardFilterForm(forms.Form):
    """Filtros compartilhados pelos gráficos do painel."""

    SEXO_CHOICES = (("", "Todos"), ("M", "Masculino"), ("F", "Feminino"), ("I", "Ignorado"))
    FAIXA_CHOICES = (
        ("", "Todas"),
        ("00-04", "0-4 anos"),
        ("05-09", "5-9 anos"),
        ("10-13", "10-13 anos"),
        ("14-17", "14-17 anos"),
    )

    uf = forms.CharField(required=False, max_length=2, label="UF")
    municipio = forms.CharField(required=False, max_length=10, label="Município (cód. IBGE)")
    ano_inicio = forms.CharField(required=False, max_length=4, label="Ano inicial")
    ano_fim = forms.CharField(required=False, max_length=4, label="Ano final")
    sexo = forms.ChoiceField(required=False, choices=SEXO_CHOICES, label="Sexo da vítima")
    faixa_etaria = forms.ChoiceField(required=False, choices=FAIXA_CHOICES, label="Faixa etária")

    viol_sexu = forms.BooleanField(required=False, label="Apenas violência sexual")
    viol_traf = forms.BooleanField(required=False, label="Apenas tráfico")
    sex_explo = forms.BooleanField(required=False, label="Apenas exploração sexual")

    def to_filters(self) -> dict:
        if not self.is_valid():
            return {}
        data = {k: v for k, v in self.cleaned_data.items() if v not in ("", None, False)}
        if "uf" in data:
            data["uf"] = data["uf"].upper()
        return data
