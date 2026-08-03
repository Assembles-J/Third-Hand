"""Auditable persistence; deliberately never stores raw reasoning text."""
from __future__ import annotations
import json, sqlite3
from datetime import datetime
from uuid import uuid4
from app.time_utils import beijing_now
from .models import ResearchChatSession, ResearchChatTurn, ResearchTurnStatus

class ResearchChatRepository:
 def __init__(self, store): self.store=store
 def _connect(self): return self.store._connect()
 def create_session(self,title,primary_symbol):
  now=beijing_now(); item=ResearchChatSession(id=str(uuid4()),title=title,primary_symbol=primary_symbol,created_at=now,updated_at=now)
  with self._connect() as c:c.execute("INSERT INTO research_chat_sessions VALUES (?,?,?,?,?,?)",(item.id,item.title,item.primary_symbol,item.status,item.created_at.isoformat(),item.updated_at.isoformat()))
  return item
 def sessions(self):
  with self._connect() as c: rows=c.execute("SELECT * FROM research_chat_sessions ORDER BY updated_at DESC").fetchall()
  return [ResearchChatSession.model_validate(dict(x)) for x in rows]
 def session(self,session_id):
  with self._connect() as c:r=c.execute("SELECT * FROM research_chat_sessions WHERE id=?",(session_id,)).fetchone()
  return ResearchChatSession.model_validate(dict(r)) if r else None
 def create_turn(self,session_id,request_id,model,prompt_version):
  with self._connect() as c:
   row=c.execute("SELECT * FROM research_chat_turns WHERE client_request_id=?",(request_id,)).fetchone()
   if row:return ResearchChatTurn.model_validate(dict(row)),False
   now=beijing_now(); item=ResearchChatTurn(id=str(uuid4()),session_id=session_id,client_request_id=request_id,status=ResearchTurnStatus.pending,model=model,prompt_version=prompt_version,created_at=now)
   c.execute("INSERT INTO research_chat_turns (id,session_id,client_request_id,status,model,prompt_version,created_at) VALUES (?,?,?,?,?,?,?)",(item.id,session_id,request_id,item.status.value,model,prompt_version,now.isoformat()))
  return item,True
 def turn(self,turn_id):
  with self._connect() as c:r=c.execute("SELECT * FROM research_chat_turns WHERE id=?",(turn_id,)).fetchone()
  return ResearchChatTurn.model_validate(dict(r)) if r else None
 def update_turn(self,turn_id,**updates):
  if not updates:return
  columns=','.join(f"{key}=?" for key in updates); values=[value.value if hasattr(value,'value') else value for value in updates.values()]
  with self._connect() as c:c.execute(f"UPDATE research_chat_turns SET {columns} WHERE id=?",(*values,turn_id))
 def add_message(self,session_id,turn_id,role,content_type,content,metadata=None):
  with self._connect() as c:c.execute("INSERT INTO research_chat_messages VALUES (?,?,?,?,?,?,?,?)",(str(uuid4()),session_id,turn_id,role,content_type,content,json.dumps(metadata or {},ensure_ascii=False),beijing_now().isoformat()))
 def history(self,session_id,limit=20):
  with self._connect() as c: rows=c.execute("SELECT role,content FROM research_chat_messages WHERE session_id=? AND content_type IN ('user_text','assistant_answer','clarification_answer') ORDER BY created_at DESC LIMIT ?",(session_id,limit)).fetchall()
  return [dict(x) for x in reversed(rows)]
 def messages(self,session_id,limit=100):
  with self._connect() as c: rows=c.execute("SELECT role,content,content_type,created_at FROM research_chat_messages WHERE session_id=? AND content_type IN ('user_text','assistant_answer','clarification_answer') ORDER BY created_at ASC LIMIT ?",(session_id,max(1,min(limit,200)))).fetchall()
  return [dict(x) for x in rows]
 def save_tool_call(self,turn_id,name,args,status,result=None,error=None,duration=0):
  with self._connect() as c:c.execute("INSERT INTO research_tool_calls (id,turn_id,tool_name,tool_version,arguments_json,result_summary_json,status,duration_ms,error_code,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),turn_id,name,"v1",json.dumps(args,ensure_ascii=False),json.dumps(result,ensure_ascii=False,default=str) if result else None,status,duration,error,beijing_now().isoformat(),beijing_now().isoformat()))
 def clarification(self,turn_id):
  with self._connect() as c:r=c.execute("SELECT * FROM research_clarifications WHERE turn_id=? AND status='waiting' ORDER BY created_at DESC LIMIT 1",(turn_id,)).fetchone()
  return dict(r) if r else None
 def create_clarification(self,turn_id,reason,questions):
  from datetime import timedelta
  now=beijing_now(); cid=str(uuid4()); expires=now+timedelta(hours=24)
  with self._connect() as c:c.execute("INSERT INTO research_clarifications VALUES (?,?,?,?,?,?,?,?,?)",(cid,turn_id,"waiting",reason,json.dumps(questions,ensure_ascii=False),None,expires.isoformat(),now.isoformat(),None))
  return {"id":cid,"reason":reason,"questions":questions,"expires_at":expires.isoformat()}
 def answer_clarification(self,turn_id,answers):
  item=self.clarification(turn_id)
  if not item:return None
  with self._connect() as c:c.execute("UPDATE research_clarifications SET status='answered',answers_json=?,answered_at=? WHERE id=?",(json.dumps(answers,ensure_ascii=False),beijing_now().isoformat(),item['id']))
  return item
