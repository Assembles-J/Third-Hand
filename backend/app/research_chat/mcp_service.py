"""MCP-shaped facade for Third-Hand's bounded research tools.

It lets an agent discover and call the same tools without giving it direct
database mutation. CRUD writes are represented as confirmation-required proposals.
"""
from .tool_executor import ToolExecutor
from .tool_registry import definitions

class ThirdHandMcpService:
 def __init__(self,store):self.executor=ToolExecutor(store)
 def list_tools(self):
  return [{"name":item["function"]["name"],"description":item["function"]["description"],"inputSchema":item["function"]["parameters"]} for item in definitions()]
 def call_tool(self,name,arguments,context):return self.executor.execute(name,arguments,context)
