from django.contrib import admin

from .models import ChatMessage, ChatThread


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "forecaster", "model", "updated_at")
    list_filter = ("forecaster", "model")
    search_fields = ("title", "user__username")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "role", "tool_name", "elapsed_seconds", "created_at")
    list_filter = ("role",)
