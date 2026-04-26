from collections.abc import AsyncIterator

from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, base_url: str, model: str = "local", api_key: str = "none"):
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model

    def _params(self, messages: list[dict], think: bool) -> dict:
        # `extra_body.chat_template_kwargs.enable_thinking` toggles thinking on llama.cpp / Qwen.
        return {
            "model": self._model,
            "messages": messages,
            "extra_body": {"chat_template_kwargs": {"enable_thinking": think}},
        }

    async def chat(self, messages: list[dict], think: bool = True) -> dict:
        params = self._params(messages, think)
        response = await self._client.chat.completions.create(**params)
        msg = response.choices[0].message
        extra = msg.model_extra or {}
        return {"think": extra.get("reasoning_content"), "answer": msg.content}

    async def chat_stream(
        self, messages: list[dict], think: bool = True
    ) -> AsyncIterator[dict]:
        params = self._params(messages, think)
        stream = await self._client.chat.completions.create(**params, stream=True)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            extra = delta.model_extra or {}
            yield {"think": extra.get("reasoning_content"), "answer": delta.content}
