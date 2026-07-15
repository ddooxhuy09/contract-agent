from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

PROVIDERS = {
    "gemini": {"label": "Gemini 2.5 Flash", "model": GEMINI_MODEL},
}
DEFAULT_PROVIDER = "gemini"

_gemini_chat: ChatGoogleGenerativeAI | None = None


def get_chat_model(provider: str = DEFAULT_PROVIDER) -> ChatGoogleGenerativeAI:
    """Return the underlying LangChain chat model, for callers that need message-list
    invocation (e.g. a LangGraph node building its own SystemMessage/HumanMessage prompt)
    rather than the flattened single-string helper below.
    """
    global _gemini_chat
    if _gemini_chat is None:
        _gemini_chat = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY, temperature=0)
    return _gemini_chat


def chat_completion(prompt: str, provider: str = DEFAULT_PROVIDER) -> str:
    response = get_chat_model(provider).invoke(prompt)
    return response.content
