"""
Operations Agent

Optimizes warehouse workflows including picking, packing, and receiving. Responsible for:
- Pick path optimization (Traveling Salesman Problem)
- A/B/C item velocity prioritization
- Congestion monitoring and re-routing
- Batch picking logic
"""

from datetime import datetime
from typing import Annotated, TypedDict, Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.config import get_settings
from src.tools.inventory_tools import (
    get_stock_level,
    get_inventory_by_location,
    allocate_stock,
)
from src.tools.operations_tools import (
    generate_pick_route,
    get_optimal_putaway_location,
    get_warehouse_layout,
    calculate_route_distance,
)


settings = get_settings()


class OperationsAgentState(TypedDict):
    """State for the Operations Agent."""
    
    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str  # "pick", "putaway", "layout", "optimize"
    order_items: list[dict] | None
    location_code: str | None
    result: dict | None


# Define the tools available to this agent
operations_tools = [
    get_stock_level,
    get_inventory_by_location,
    allocate_stock,
    generate_pick_route,
    get_optimal_putaway_location,
    get_warehouse_layout,
    calculate_route_distance,
]


# Create the LLM with tools bound
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=0,
    api_key=settings.openai_api_key,
).bind_tools(operations_tools)


SYSTEM_PROMPT = """You are the Operations Agent for a warehouse inventory management system.
Your role is to optimize warehouse workflows for maximum efficiency and minimum travel time.

Your responsibilities:
1. Generate optimized pick routes using the nearest-neighbor algorithm
2. Suggest optimal putaway locations for incoming inventory
3. Analyze warehouse layout and utilization
4. Recommend location re-arrangements based on item velocity (A/B/C analysis)
5. Batch multiple orders for efficient picking

Optimization principles:
- MINIMIZE TRAVEL: Use shortest path algorithms to reduce picker walking distance
- VELOCITY-BASED PLACEMENT: Keep high-velocity (A) items near shipping docks
- FIFO COMPLIANCE: Pick oldest stock first for perishables
- ZONE PICKING: Group picks by zone when beneficial
- CONSOLIDATION: Store same SKU together when possible

When generating pick routes:
1. Identify all items needed and their locations
2. Find the optimal visiting sequence
3. Estimate time based on distance and pick complexity
4. Provide clear, step-by-step instructions

For putaway decisions:
1. Consider product characteristics (cold storage, hazmat, fragility)
2. Check for existing stock to consolidate
3. Match velocity class to zone (A items in fast zones)
4. Verify capacity constraints

Available tools:
- get_stock_level: Check inventory for a SKU
- get_inventory_by_location: See what's at a location
- allocate_stock: Reserve stock for picking
- generate_pick_route: Create optimized picking path
- get_optimal_putaway_location: Suggest where to store incoming goods
- get_warehouse_layout: View warehouse zones and utilization
- calculate_route_distance: Measure a specific route

Always provide actionable instructions with clear sequences and locations."""


def agent_node(state: OperationsAgentState) -> dict:
    """Process the current state and decide on actions."""
    messages = state["messages"]
    
    # Add system prompt if this is a new conversation
    if len(messages) == 1:
        messages = [HumanMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: OperationsAgentState) -> Literal["tools", "end"]:
    """Determine whether to continue with tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


def extract_result(state: OperationsAgentState) -> dict:
    """Extract the final result from the conversation."""
    messages = state["messages"]
    last_message = messages[-1]
    
    return {
        "result": {
            "agent": "operations_agent",
            "response": last_message.content if hasattr(last_message, "content") else str(last_message),
            "timestamp": datetime.utcnow().isoformat(),
        }
    }


# Build the agent graph
def create_operations_agent():
    """Create and compile the operations agent graph."""
    workflow = StateGraph(OperationsAgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(operations_tools))
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
operations_agent = create_operations_agent()


async def run_operations_agent(
    task: str,
    task_type: str = "pick",
    order_items: list[dict] | None = None,
    location_code: str | None = None,
) -> dict:
    """
    Run the operations agent with a specific task.
    
    Args:
        task: Natural language description of the task
        task_type: Type of task (pick, putaway, layout, optimize)
        order_items: Optional list of items for pick orders
        location_code: Optional location for context
        
    Returns:
        Dictionary with agent result
    """
    initial_state: OperationsAgentState = {
        "messages": [HumanMessage(content=task)],
        "task_type": task_type,
        "order_items": order_items,
        "location_code": location_code,
        "result": None,
    }
    
    final_state = await operations_agent.ainvoke(initial_state)
    return final_state.get("result", {})
