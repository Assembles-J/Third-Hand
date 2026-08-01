"""Strict models shared by the versioned research-chat protocol."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel): model_config = ConfigDict(extra="forbid")
class ResearchSseEventType(str, Enum):
    session="session"; phase="phase"; reasoning_delta="reasoning_delta"; answer_delta="answer_delta"; evidence="evidence"; tool_started="tool_started"; tool_completed="tool_completed"; tool_failed="tool_failed"; clarification_required="clarification_required"; decision="decision"; usage="usage"; warning="warning"; error="error"; done="done"; heartbeat="heartbeat"
class ResearchTurnStatus(str, Enum):
    pending="pending"; building_context="building_context"; streaming="streaming"; waiting_tool="waiting_tool"; waiting_user="waiting_user"; validating="validating"; completed="completed"; cancelled="cancelled"; failed="failed"; expired="expired"
class ResearchChatSessionCreate(StrictModel): primary_symbol: str|None=Field(None,min_length=1,max_length=32); title: str=Field(min_length=1,max_length=120)
class ResearchChatSession(StrictModel): id:str; title:str; primary_symbol:str|None=None; status:str="active"; created_at:datetime; updated_at:datetime
class ResearchChatMessageRequest(StrictModel): message:str=Field(min_length=1,max_length=4000); symbol:str|None=Field(None,min_length=1,max_length=32); client_request_id:str=Field(min_length=8,max_length=128)
class ClarificationAnswer(StrictModel): answers: list[str]=Field(min_length=1,max_length=3)
class ResearchChatTurn(StrictModel):
    id:str; session_id:str; client_request_id:str; status:ResearchTurnStatus; model:str; prompt_version:str; context_id:str|None=None; context_hash:str|None=None; answer_text:str=""; decision_report_id:str|None=None; error_code:str|None=None; error_message:str|None=None; prompt_tokens:int=0; completion_tokens:int=0; reasoning_tokens:int=0; latency_ms:int=0; created_at:datetime; started_at:datetime|None=None; completed_at:datetime|None=None
class ResearchModelOutput(StrictModel):
    answer_summary:str=Field(min_length=1,max_length=1600); thesis_status:str; candidate_action:str; supporting_evidence_ids:tuple[str,...]=(); contradicting_evidence_ids:tuple[str,...]=(); missing_evidence:tuple[str,...]=(); requested_followups:tuple[str,...]=(); model_uncertainty:str
class ResearchSseEvent(StrictModel): protocol:str="research-sse-v1"; event:ResearchSseEventType; data:dict[str,object]
