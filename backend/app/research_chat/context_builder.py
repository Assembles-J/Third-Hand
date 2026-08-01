from __future__ import annotations
class ResearchContextBuilder:
 def __init__(self,builder):self.builder=builder
 def build(self,symbol):return self.builder.build(symbol.strip().upper())
