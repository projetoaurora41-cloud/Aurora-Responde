from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from chats.series_temporais.orquestrador import views as orq_views
from core import views as core_views
from mapas import views as mapas_views
from painel import views as painel_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # `/` = Início. O painel Aurora e o chat ficam em rotas próprias.
    path("", painel_views.inicio, name="home"),
    path("aurora/", painel_views.dashboards, name="dashboards"),
    path("aurora/distribuicao-geografica/", painel_views.distribuicao_geografica, name="distribuicao_geografica"),
    path("aurora/api/filters/", painel_views.filter_options, name="filter_options"),
    path("aurora/api/dashboard/<str:key>/", painel_views.dashboard_data, name="dashboard_data"),
    path("aurora/api/mapa/municipios/<str:uf>/", painel_views.map_municipalities, name="map_municipalities"),
    path("aurora/api/sipiact/filtros/", mapas_views.sipiact_filtros, name="sipiact_filtros"),
    path("aurora/api/sipiact/uf/", mapas_views.sipiact_uf, name="sipiact_uf"),
    path("aurora-responde/", orq_views.aurora_home, name="aurora_responde"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", core_views.signup, name="signup"),

    # Endpoints do chat (nova conversa, enviar mensagem, excluir, relatório).
    path("series-temporais/chat/", include(
        ("chats.series_temporais.orquestrador.urls", "chat"), namespace="chat")),
]
