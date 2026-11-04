from django.urls import path

from . import views

urlpatterns = [
    path("", views.thread_list, name="list"),
    path("relatorio/", views.relatorio, name="relatorio"),
    path("new/", views.new_thread, name="new"),
    path("<int:pk>/", views.thread, name="thread"),
    path("<int:pk>/send/", views.send_message, name="send"),
    path("<int:pk>/delete/", views.delete_thread, name="delete"),
]
