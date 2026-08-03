"""Research Chat HTTP boundary.  All action remains server-side and feature-gated."""
from __future__ import annotations
import os
from fastapi import APIRouter,HTTPException,status
from fastapi.responses import StreamingResponse
from .models import ResearchChatSessionCreate,ResearchChatMessageRequest,ClarificationAnswer
from .repository import ResearchChatRepository
from .context_builder import ResearchContextBuilder
from .orchestrator import ResearchChatOrchestrator
from .sse import SSE_CONTENT_TYPE,SSE_HEADERS
from .metrics import snapshot

def build_router(store,decision_context_builder,decision_orchestrator):
 router=APIRouter(prefix="/v1/research-chat",tags=["research-chat"]);repo=ResearchChatRepository(store);engine=ResearchChatOrchestrator(repo,ResearchContextBuilder(decision_context_builder),store,decision_orchestrator)
 def enabled():return os.getenv("RESEARCH_CHAT_ENABLED","false").lower() in {"1","true","yes","on"}
 def require():
  if not enabled():raise HTTPException(404,"research chat is disabled")
 @router.post("/sessions",status_code=status.HTTP_201_CREATED)
 def create(payload:ResearchChatSessionCreate):require();return repo.create_session(payload.title,payload.primary_symbol)
 @router.get("/sessions")
 def list_sessions():require();return repo.sessions()
 @router.get("/sessions/{session_id}")
 def get_session(session_id:str):
  require();item=repo.session(session_id)
  if not item:raise HTTPException(404,"session_not_found")
  return item
 @router.get("/sessions/{session_id}/messages")
 def session_messages(session_id:str):
  require()
  if not repo.session(session_id):raise HTTPException(404,"session_not_found")
  return repo.messages(session_id)
 @router.post("/sessions/{session_id}/messages/stream")
 async def stream(session_id:str,payload:ResearchChatMessageRequest):
  require()
  if os.getenv("RESEARCH_CHAT_SSE_ENABLED","false").lower() not in {"1","true","yes","on"}:raise HTTPException(409,"research SSE is disabled")
  session=repo.session(session_id)
  if not session:raise HTTPException(404,"session_not_found")
  turn,is_new=repo.create_turn(session_id,payload.client_request_id,engine.stream_client.settings.reasoning_model,"research-chat-v1")
  if not is_new:
   if turn.status.value in {"completed","waiting_user","failed","cancelled"}:return {"turn_id":turn.id,"status":turn.status.value,"idempotent":True}
   raise HTTPException(409,{"code":"turn_conflict","turn_id":turn.id})
  return StreamingResponse(engine.stream(session,turn,payload.message,payload.symbol),media_type=SSE_CONTENT_TYPE,headers=SSE_HEADERS)
 @router.get("/turns/{turn_id}")
 def get_turn(turn_id:str):
  require();item=repo.turn(turn_id)
  if not item:raise HTTPException(404,"turn_not_found")
  return item
 @router.post("/turns/{turn_id}/cancel")
 def cancel(turn_id:str):
  require();item=repo.turn(turn_id)
  if not item:raise HTTPException(404,"turn_not_found")
  if item.status.value not in {"pending","building_context","streaming","waiting_tool","waiting_user"}:raise HTTPException(409,"turn_not_cancellable")
  repo.update_turn(turn_id,status="cancelled");return {"turn_id":turn_id,"status":"cancelled"}
 @router.post("/turns/{turn_id}/clarification")
 def clarify(turn_id:str,payload:ClarificationAnswer):
  require();turn=repo.turn(turn_id)
  if not turn or turn.status.value!="waiting_user":raise HTTPException(409,"turn_not_waiting_user")
  item=repo.answer_clarification(turn_id,payload.answers)
  if not item:raise HTTPException(409,"invalid_clarification")
  repo.add_message(turn.session_id,turn_id,"user","clarification_answer","\n".join(payload.answers));repo.update_turn(turn_id,status="completed",completed_at=__import__('app.time_utils',fromlist=['beijing_now']).beijing_now().isoformat())
  return {"turn_id":turn_id,"status":"completed","notice":"请创建新的研究轮次继续分析"}
 @router.get("/metrics")
 def metrics():
  require();return snapshot()
 return router
