"""
Audit Agent

Handles periodic cycle counts and discrepancy resolution. Responsible for:
- Cycle count scheduling and execution
- Shrinkage detection and investigation
- Error correction and reconciliation
- Variance analysis and reporting
"""

from datetime import datetime
from typing import Annotated, TypedDict, Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.llm import get_llm_with_tools
from src.tools.inventory_tools import (
    get_stock_level,
    get_inventory_by_location,
    reconcile_inventory,
)


class AuditAgentState(TypedDict):
    """State for the Audit Agent."""
    
    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str  # "cycle_count", "reconcile", "investigate", "report"
    locations_to_audit: list[str]
    discrepancies: list[dict]
    result: dict | None


# Define the tools available to this agent
audit_tools = [
    get_stock_level,
    get_inventory_by_location,
    reconcile_inventory,
]


# Create the LLM with tools bound (uses configured provider)
llm = get_llm_with_tools(audit_tools)


SYSTEM_PROMPT = """You are the Audit Agent for a warehouse inventory management system.
Your role is to ensure inventory accuracy through regular audits and discrepancy resolution.

Your responsibilities:
1. Conduct cycle counts on scheduled or random basis
2. Identify and investigate inventory discrepancies
3. Reconcile physical counts with system records
4. Detect patterns that may indicate shrinkage or theft
5. Generate variance reports and recommendations

Audit principles:
- ACCURACY FIRST: The goal is to match physical reality to digital records
- ROOT CAUSE ANALYSIS: Don't just fix numbers, understand why they're wrong
- ABC ANALYSIS: High-value items need more frequent audits
- ZONE ROTATION: Ensure all areas get audited regularly
- DOCUMENTATION: Every adjustment needs a clear reason

When conducting cycle counts:
1. Get the current system quantity for the location/SKU
2. Compare with the reported physical count
3. Calculate variance (both units and value)
4. If variance exists, investigate possible causes:
   - Picking errors
   - Receiving errors
   - Damage/spoilage
   - Theft/shrinkage
   - System entry errors
5. Reconcile with documented reason

Shrinkage indicators to watch:
- Consistent shortages in specific locations
- High-value items with frequent variances
- Patterns by time of day or shift
- Unusual access patterns

Available tools:
- get_stock_level: Get current system quantity for a SKU
- get_inventory_by_location: See all items at a location
- reconcile_inventory: Adjust inventory to match physical count

Always document findings and provide actionable recommendations."""


def agent_node(state: AuditAgentState) -> dict:
    """Process the current state and decide on actions."""
    messages = state["messages"]
    
    # Add system prompt if this is a new conversation
    if len(messages) == 1:
        messages = [HumanMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AuditAgentState) -> Literal["tools", "end"]:
    """Determine whether to continue with tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


def extract_result(state: AuditAgentState) -> dict:
    """Extract the final result from the conversation."""
    messages = state["messages"]
    last_message = messages[-1]
    
    return {
        "result": {
            "agent": "audit_agent",
            "response": last_message.content if hasattr(last_message, "content") else str(last_message),
            "timestamp": datetime.utcnow().isoformat(),
            "discrepancies_found": state.get("discrepancies", []),
        }
    }


# Build the agent graph
def create_audit_agent():
    """Create and compile the audit agent graph."""
    workflow = StateGraph(AuditAgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(audit_tools))
    workflow.add_node("extract_result", extract_result)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": "extract_result",
        }
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("extract_result", END)
    
    return workflow.compile()


# Create the compiled agent
audit_agent = create_audit_agent()


async def run_audit_agent(
    task: str,
    task_type: str = "cycle_count",
    locations_to_audit: list[str] | None = None,
) -> dict:
    """
    Run the audit agent with a specific task.
    
    Args:
        task: Natural language description of the task
        task_type: Type of task (cycle_count, reconcile, investigate, report)
        locations_to_audit: Optional list of location codes to audit
        
    Returns:
        Dictionary with agent result
    """
    initial_state: AuditAgentState = {
        "messages": [HumanMessage(content=task)],
        "task_type": task_type,
        "locations_to_audit": locations_to_audit or [],
        "discrepancies": [],
        "result": None,
    }
    
    final_state = await audit_agent.ainvoke(initial_state)
    return final_state.get("result", {})
