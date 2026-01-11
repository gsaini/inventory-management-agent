"""
Tracking Agent

Manages the "Digital Twin" of physical stock. Responsible for:
- RFID/Barcode synchronization
- Bin mapping and sub-location tracking
- Lot/Serial number tracking
- Virtual inventory management (allocated vs available)
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
    update_stock_quantity,
    get_inventory_by_location,
    allocate_stock,
    deallocate_stock,
)


class TrackingAgentState(TypedDict):
    """State for the Tracking Agent."""
    
    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str  # "query", "update", "allocate", "transfer"
    sku: str | None
    location_code: str | None
    result: dict | None


# Define the tools available to this agent
tracking_tools = [
    get_stock_level,
    update_stock_quantity,
    get_inventory_by_location,
    allocate_stock,
    deallocate_stock,
]


# Create the LLM with tools bound (uses configured provider)
llm = get_llm_with_tools(tracking_tools)


SYSTEM_PROMPT = """You are the Tracking Agent for a warehouse inventory management system.
Your role is to maintain the "Digital Twin" of physical stock - ensuring that digital records
accurately reflect the physical inventory in the warehouse.

Your responsibilities:
1. Track inventory levels across all locations
2. Process stock movements (receiving, picking, transfers)
3. Manage stock allocation for pending orders
4. Maintain lot and serial number traceability
5. Report discrepancies between expected and actual stock

When handling requests:
- Always verify current stock levels before making changes
- Use FIFO (First-In-First-Out) for perishable items
- Ensure allocated stock doesn't exceed available stock
- Log all movements for audit trail

Available tools:
- get_stock_level: Get current stock for a SKU
- update_stock_quantity: Add or remove stock at a location
- get_inventory_by_location: See all items at a location
- allocate_stock: Reserve stock for an order
- deallocate_stock: Release reserved stock

Be precise and report all results clearly."""


def agent_node(state: TrackingAgentState) -> dict:
    """Process the current state and decide on actions."""
    messages = state["messages"]
    
    # Add system prompt if this is a new conversation
    if len(messages) == 1:
        messages = [HumanMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: TrackingAgentState) -> Literal["tools", "end"]:
    """Determine whether to continue with tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


def extract_result(state: TrackingAgentState) -> dict:
    """Extract the final result from the conversation."""
    messages = state["messages"]
    last_message = messages[-1]
    
    return {
        "result": {
            "agent": "tracking_agent",
            "response": last_message.content if hasattr(last_message, "content") else str(last_message),
            "timestamp": datetime.utcnow().isoformat(),
        }
    }


# Build the agent graph
def create_tracking_agent():
    """Create and compile the tracking agent graph."""
    workflow = StateGraph(TrackingAgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tracking_tools))
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
tracking_agent = create_tracking_agent()


async def run_tracking_agent(
    task: str,
    task_type: str = "query",
    sku: str | None = None,
    location_code: str | None = None,
) -> dict:
    """
    Run the tracking agent with a specific task.
    
    Args:
        task: Natural language description of the task
        task_type: Type of task (query, update, allocate, transfer)
        sku: Optional SKU for context
        location_code: Optional location for context
        
    Returns:
        Dictionary with agent result
    """
    initial_state: TrackingAgentState = {
        "messages": [HumanMessage(content=task)],
        "task_type": task_type,
        "sku": sku,
        "location_code": location_code,
        "result": None,
    }
    
    final_state = await tracking_agent.ainvoke(initial_state)
    return final_state.get("result", {})
