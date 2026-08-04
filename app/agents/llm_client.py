from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.settings import get_settings

DEFAULT_PROVIDER = "gemini"

_gemini_chat: ChatGoogleGenerativeAI | None = None


def get_providers() -> dict[str, dict[str, str]]:
    settings = get_settings()
    return {
        "gemini": {"label": "Gemini 2.5 Flash", "model": settings.gemini_model},
    }


# Kept for routes that iterate providers at import/list time.
PROVIDERS = get_providers()


def get_chat_model(provider: str = DEFAULT_PROVIDER) -> ChatGoogleGenerativeAI:
    """Return the underlying LangChain chat model, for callers that need message-list
    invocation (e.g. a LangGraph node building its own SystemMessage/HumanMessage prompt)
    rather than the flattened single-string helper below.
    """
    global _gemini_chat
    if _gemini_chat is None:
        settings = get_settings()
        _gemini_chat = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )
    return _gemini_chat


def chat_completion(prompt: str, provider: str = DEFAULT_PROVIDER) -> str:
    response = get_chat_model(provider).invoke(prompt)
    return response.content
