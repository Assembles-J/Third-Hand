"""Auditable persistence for the user-visible transcript and tool-call context."""
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
  with self._connect() as c: rows=c.execute("SELECT * FROM research_chat_sessions ORDER BY updated_at DESC, created_at DESC, id DESC").fetchall()
  return [ResearchChatSession.model_validate(dict(x)) for x in rows]
 def session(self,session_id):
  with self._connect() as c:r=c.execute("SELECT * FROM research_chat_sessions WHERE id=?",(session_id,)).fetchone()
  return ResearchChatSession.model_validate(dict(r)) if r else None
 def update_session_title(self,session_id,title):
  with self._connect() as c:c.execute("UPDATE research_chat_sessions SET title=?, updated_at=? WHERE id=?",(title[:120],beijing_now().isoformat(),session_id))
 def create_turn(self,session_id,request_id,model,prompt_version):
  with self._connect() as c:
   row=c.execute("SELECT * FROM research_chat_turns WHERE client_request_id=?",(request_id,)).fetchone()
   if row:return ResearchChatTurn.model_validate(dict(row)),False
   now=beijing_now(); item=ResearchChatTurn(id=str(uuid4()),session_id=session_id,client_request_id=request_id,status=ResearchTurnStatus.pending,model=model,prompt_version=prompt_version,created_at=now)
   c.execute("INSERT INTO research_chat_turns (id,session_id,client_request_id,status,model,prompt_version,created_at) VALUES (?,?,?,?,?,?,?)",(item.id,session_id,request_id,item.status.value,model,prompt_version,now.isoformat()))
   c.execute("UPDATE research_chat_sessions SET updated_at=? WHERE id=?",(now.isoformat(),session_id))
  return item,True
 def turn(self,turn_id):
  with self._connect() as c:r=c.execute("SELECT * FROM research_chat_turns WHERE id=?",(turn_id,)).fetchone()
  return ResearchChatTurn.model_validate(dict(r)) if r else None
 def update_turn(self,turn_id,**updates):
  if not updates:return
  columns=','.join(f"{key}=?" for key in updates); values=[value.value if hasattr(value,'value') else value for value in updates.values()]
  with self._connect() as c:c.execute(f"UPDATE research_chat_turns SET {columns} WHERE id=?",(*values,turn_id))
 def add_message(self,session_id,turn_id,role,content_type,content,metadata=None):
  now=beijing_now().isoformat()
  with self._connect() as c:
   c.execute("INSERT INTO research_chat_messages VALUES (?,?,?,?,?,?,?,?)",(str(uuid4()),session_id,turn_id,role,content_type,content,json.dumps(metadata or {},ensure_ascii=False),now))
   c.execute("UPDATE research_chat_sessions SET updated_at=? WHERE id=?",(now,session_id))
 def history(self,session_id,limit=20):
  # DeepSeek requires reasoning_content from an assistant tool-call message and
  # its tool results to be replayed in later user turns.  These records are not
  # exposed by messages(), but must remain in the model-facing transcript.
  with self._connect() as c: rows=c.execute("SELECT role,content FROM research_chat_messages WHERE session_id=? AND content_type IN ('user_text','assistant_answer','clarification_answer','assistant_tool_context','tool_result_context') ORDER BY created_at DESC, rowid DESC LIMIT ?",(session_id,limit)).fetchall()
  return [dict(x) for x in reversed(rows)]
 def messages(self,session_id,limit=100):
  with self._connect() as c: rows=c.execute("SELECT role,content,content_type,created_at FROM research_chat_messages WHERE session_id=? AND content_type IN ('user_text','assistant_answer','clarification_answer') ORDER BY created_at ASC LIMIT ?",(session_id,max(1,min(limit,200)))).fetchall()
  return [dict(x) for x in rows]
 def sources(self,session_id):
  with self._connect() as c: rows=c.execute("SELECT source_key,title,detail,added_at FROM research_chat_session_sources WHERE session_id=? ORDER BY added_at ASC",(session_id,)).fetchall()
  return [dict(x) for x in rows]
 def save_sources(self,session_id,sources):
  now=beijing_now().isoformat()
  with self._connect() as c:
   for item in sources:
    c.execute("INSERT INTO research_chat_session_sources (session_id,source_key,title,detail,added_at) VALUES (?,?,?,?,?) ON CONFLICT(session_id,source_key) DO UPDATE SET title=excluded.title,detail=excluded.detail,added_at=excluded.added_at",(session_id,item['source_key'],item['title'],item.get('detail',''),now))
   c.execute("UPDATE research_chat_sessions SET updated_at=? WHERE id=?",(now,session_id))
  return self.sources(session_id)
 def save_tool_call(self,turn_id,name,args,status,result=None,error=None,duration=0):
  with self._connect() as c:c.execute("INSERT INTO research_tool_calls (id,turn_id,tool_name,tool_version,arguments_json,result_summary_json,status,duration_ms,error_code,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),turn_id,name,"v1",json.dumps(args,ensure_ascii=False),json.dumps(result,ensure_ascii=False,default=str) if result else None,status,duration,error,beijing_now().isoformat(),beijing_now().isoformat()))
 def daily_history_refresh(self,session_id):
  with self._connect() as c:r=c.execute("SELECT * FROM research_daily_history_refreshes WHERE session_id=?",(session_id,)).fetchone()
  return dict(r) if r else None
 def request_daily_history_refresh(self,session_id,symbol,required_days=60):
  now=beijing_now().isoformat(); bar_count=len(self.store.daily_prices(symbol,required_days))
  item={"session_id":session_id,"symbol":symbol,"required_days":required_days,"status":"completed" if bar_count>=required_days else "queued","bar_count":bar_count,"error_message":None,"created_at":now,"updated_at":now}
  with self._connect() as c:c.execute("INSERT INTO research_daily_history_refreshes (session_id,symbol,required_days,status,bar_count,error_message,created_at,updated_at) VALUES (:session_id,:symbol,:required_days,:status,:bar_count,:error_message,:created_at,:updated_at) ON CONFLICT(session_id) DO UPDATE SET symbol=excluded.symbol,required_days=excluded.required_days,status=excluded.status,bar_count=excluded.bar_count,error_message=NULL,updated_at=excluded.updated_at",item)
  return self.daily_history_refresh(session_id)
 def update_daily_history_refresh(self,session_id,**updates):
  if not updates:return
  updates["updated_at"]=beijing_now().isoformat();columns=','.join(f"{key}=?" for key in updates);values=list(updates.values())
  with self._connect() as c:c.execute(f"UPDATE research_daily_history_refreshes SET {columns} WHERE session_id=?",(*values,session_id))
  return self.daily_history_refresh(session_id)
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
