from __future__ import annotations
class ResearchChatError(RuntimeError):
 def __init__(self,code,message):super().__init__(message);self.code=code
