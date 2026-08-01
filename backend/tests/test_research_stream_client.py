import asyncio
import httpx

from app.llm_client import DeepSeekSettings
from app.research_chat.stream_client import DeepSeekStreamClient


def test_stream_client_separates_reasoning_and_answer_chunks():
    async def run():
        async def handler(_request):
            return httpx.Response(200, content=(
                'data: {"choices":[{"delta":{"reasoning_content":"reason"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"answer"}}]}\n\n'
                'data: [DONE]\n\n'
            ))
        client = DeepSeekStreamClient(DeepSeekSettings(api_key="test-key"), httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        return [chunk async for chunk in client.stream_chat([{"role": "user", "content": "test"}])]

    chunks = asyncio.run(run())
    assert chunks[0]["choices"][0]["delta"]["reasoning_content"] == "reason"
    assert chunks[1]["choices"][0]["delta"]["content"] == "answer"
