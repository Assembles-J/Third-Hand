"""Independent async DeepSeek stream client; does not modify ``chat_json``."""
from __future__ import annotations
import json, time
from collections.abc import AsyncIterator
import httpx
from app.llm_client import DeepSeekSettings, LlmClientError

class DeepSeekStreamClient:
 def __init__(self,settings:DeepSeekSettings|None=None,http_client:httpx.AsyncClient|None=None): self.settings=settings or DeepSeekSettings.from_env();self._http=http_client
 @property
 def enabled(self):return bool(self.settings.api_key)
 async def stream_chat(self,messages:list[dict[str,object]],*,tools:list[dict[str,object]]|None=None,max_tokens:int=12000)->AsyncIterator[dict[str,object]]:
  if not self.enabled:raise LlmClientError("未配置 DEEPSEEK_API_KEY。",code="not_configured",retryable=False)
  payload={"model":self.settings.reasoning_model,"messages":messages,"stream":True,"stream_options":{"include_usage":True},"max_tokens":max_tokens,"thinking":{"type":"enabled"},"reasoning_effort":"high"}
  if tools:payload["tools"]=tools
  timeout=httpx.Timeout(connect=10,read=90,write=10,pool=10)
  client=self._http or httpx.AsyncClient(trust_env=self.settings.trust_environment_proxy,timeout=timeout)
  own=self._http is None
  try:
   async with client.stream("POST",f"{self.settings.base_url}/chat/completions",json=payload,headers={"Authorization":f"Bearer {self.settings.api_key}","Content-Type":"application/json"}) as response:
    if response.status_code>=400:raise LlmClientError("DeepSeek 流请求失败。",code="upstream_rate_limited" if response.status_code==429 else "upstream_connect_error",retryable=response.status_code>=500 or response.status_code==429,status_code=response.status_code)
    async for line in response.aiter_lines():
     if not line.startswith("data:"):continue
     raw=line[5:].strip()
     if raw=="[DONE]":break
     try: yield json.loads(raw)
     except json.JSONDecodeError: continue
  except httpx.TimeoutException as exc:raise LlmClientError("DeepSeek 流超时。",code="upstream_timeout",retryable=True) from exc
  except httpx.TransportError as exc:raise LlmClientError("DeepSeek 流中断。",code="upstream_stream_interrupted",retryable=True) from exc
  finally:
   if own:await client.aclose()
