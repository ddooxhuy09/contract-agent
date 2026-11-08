from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.llm_client import get_chat_model


def _model() -> ChatGoogleGenerativeAI:
    # Shared with the agents so key rotation on a per-day quota applies here too.
    return get_chat_model()


class GeminiChatModel:
    def complete(self, prompt: str) -> str:
        return _model().invoke(prompt).content

    async def acomplete(self, prompt: str) -> str:
        result = await _model().ainvoke(prompt)
        return result.content
