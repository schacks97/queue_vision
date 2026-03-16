from django.urls import path

from . import views

app_name = "ai_assistent"

urlpatterns = [
    path("", views.AssistantPageView.as_view(), name="chat_page"),
    path("chat/", views.ChatAPIView.as_view(), name="chat_api"),
    path("new-session/", views.NewSessionView.as_view(), name="new_session"),
    path("session/<uuid:session_id>/messages/", views.SessionMessagesView.as_view(), name="session_messages"),
    path("session/<uuid:session_id>/delete/", views.DeleteSessionView.as_view(), name="delete_session"),
]
