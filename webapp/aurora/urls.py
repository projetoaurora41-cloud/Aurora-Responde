from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from chats.series_temporais.orquestrador import views as orq_views
from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # `/` = Aurora Responde (chat único: só Jurema + RAG + dados ao vivo).
    path("", orq_views.aurora_home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", core_views.signup, name="signup"),

    # Endpoints do chat (nova conversa, enviar mensagem, excluir, relatório).
    path("series-temporais/chat/", include(
        ("chats.series_temporais.orquestrador.urls", "chat"), namespace="chat")),
]
