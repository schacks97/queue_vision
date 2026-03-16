"""Build the message list for the Groq chat completions API."""

import json

from ai_assistent.services.analytics_query_engine import (
    get_analytics_summary,
    get_recent_jobs_summary,
)

SYSTEM_PROMPT = """You are Wobot.aiAssistant, an expert AI analytics assistant for the QueueVision traffic analysis platform.

Your role:
- Answer questions about traffic video analytics: vehicle counts, wait times, congestion, vehicle type distributions.
- Provide insights, comparisons, and suggestions based on the data provided.
- Be concise, helpful, and data-driven.
- Format your answers in Markdown when it helps readability (tables, bullet lists, bold).
- If you do not have enough data to answer a question, say so clearly.
- Never fabricate data. Only reference the analytics data provided below.

Platform context:
- The platform processes traffic surveillance videos using YOLO-based detecters.
- Detected vehicle types include: car, truck, bus, motorcycle (COCO classes 2, 3, 5, 7).
- Metrics tracked: total vehicles, average wait time, max wait time, vehicle type distribution.
"""


def build_messages(user_question: str, history: list[dict] | None = None) -> list[dict]:
    """
    Build the messages payload for the Groq API.

    Parameters
    ----------
    user_question : str
        The latest question from the user.
    history : list[dict] | None
        Previous conversation messages [{"role": "user"|"assistant", "content": "..."}].

    Returns
    -------
    list[dict]
        Messages list ready for the Groq chat completions API.
    """
    # Gather live analytics data
    summary = get_analytics_summary()
    recent_jobs = get_recent_jobs_summary(limit=5)

    data_context = (
        "=== ANALYTICS DATA ===\n"
        f"Overall Summary:\n{json.dumps(summary, indent=2)}\n\n"
        f"Recent Jobs:\n{json.dumps(recent_jobs, indent=2)}\n"
        "=== END DATA ===\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n" + data_context},
    ]

    # Append conversation history (last 10 messages for context)
    if history:
        messages.extend(history[-10:])

    messages.append({"role": "user", "content": user_question})
    return messages
