from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.settings import get_settings


@lru_cache
def _model() -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )


class GeminiChatModel:
    def complete(self, prompt: str) -> str:
        return _model().invoke(prompt).content

    async def acomplete(self, prompt: str) -> str:
        result = await _model().ainvoke(prompt)
        return result.content
