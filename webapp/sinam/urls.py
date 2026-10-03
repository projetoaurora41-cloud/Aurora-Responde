from django.urls import path

from . import views

urlpatterns = [
    path("importar/", views.importar, name="importar"),
    path("importacoes/<int:pk>/", views.importacao_detail, name="importacao_detail"),
]
