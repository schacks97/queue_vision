import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .models import ChatSession, ChatMessage
from .services.groq_client import GroqClient
from .utils.prompt_builder import build_messages

logger = logging.getLogger(__name__)


class AssistantPageView(LoginRequiredMixin, TemplateView):
    """Render the AI assistant chat page."""
    template_name = "ai_assistent/assistant.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # All sessions for the sidebar
        sessions = list(
            ChatSession.objects.filter(user=user).values("id", "title", "created_at")
        )
        for s in sessions:
            s["id"] = str(s["id"])
            s["created_at"] = s["created_at"].strftime("%b %d, %H:%M")
        ctx["sessions"] = sessions

        # Load the most recent session messages
        session = ChatSession.objects.filter(user=user).first()
        if session:
            ctx["session_id"] = str(session.id)
            ctx["history"] = list(session.messages.values("role", "content"))
        else:
            ctx["session_id"] = ""
            ctx["history"] = []
        return ctx


class ChatAPIView(LoginRequiredMixin, View):
    """POST endpoint: receive user question, return assistant answer."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        question = body.get("question", "").strip()
        if not question:
            return JsonResponse({"error": "Question is required."}, status=400)

        session_id = body.get("session_id")

        # Retrieve or create a chat session
        session = None
        if session_id:
            session = ChatSession.objects.filter(pk=session_id, user=request.user).first()
        if session is None:
            session = ChatSession.objects.create(user=request.user)

        # Auto-title from the first user message
        is_first_message = not session.messages.exists()

        # Build history from DB — last 10 messages for LLM context
        recent_msgs = session.messages.order_by('-created_at')[:10]
        history = [
            {"role": m.role, "content": m.content}
            for m in reversed(recent_msgs)
        ]

        # Build prompt and call Groq
        messages = build_messages(question, history=history)
        client = GroqClient()
        logger.info("AI assistant query from user=%s: %s", request.user, question[:100])
        answer = client.chat(messages)

        # Persist messages
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=question)
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content=answer)

        # Set session title from first question
        if is_first_message:
            session.title = question[:80] + ("..." if len(question) > 80 else "")
            session.save(update_fields=["title"])

        return JsonResponse({
            "answer": answer,
            "session_id": str(session.id),
            "session_title": session.title,
        })


class NewSessionView(LoginRequiredMixin, View):
    """POST endpoint to create a new chat session."""

    def post(self, request):
        session = ChatSession.objects.create(user=request.user)
        return JsonResponse({
            "session_id": str(session.id),
            "title": session.title,
            "created_at": session.created_at.strftime("%b %d, %H:%M"),
        })


class SessionMessagesView(LoginRequiredMixin, View):
    """GET endpoint to load messages for a given session."""

    def get(self, request, session_id):
        session = ChatSession.objects.filter(pk=session_id, user=request.user).first()
        if not session:
            return JsonResponse({"error": "Session not found."}, status=404)

        messages = list(session.messages.values("role", "content"))
        return JsonResponse({
            "session_id": str(session.id),
            "title": session.title,
            "messages": messages,
        })


class DeleteSessionView(LoginRequiredMixin, View):
    """DELETE endpoint to remove a chat session."""

    def delete(self, request, session_id):
        session = ChatSession.objects.filter(pk=session_id, user=request.user).first()
        if not session:
            return JsonResponse({"error": "Session not found."}, status=404)
        session.delete()
        return JsonResponse({"ok": True})
