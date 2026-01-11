"""
Replenishment Agent

The decision-maker for procurement and vendor purchase orders. Responsible for:
- JIT (Just-In-Time) logic
- Vendor scorecarding and selection
- Economic Order Quantity (EOQ) optimization
- Automatic PO generation
"""

from datetime import datetime
from typing import Annotated, TypedDict, Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.llm import get_llm_with_tools
from src.tools.inventory_tools import get_stock_level
from src.tools.replenishment_tools import (
    calculate_reorder_point,
    calculate_economic_order_quantity,
    get_vendor_info,
    create_purchase_order,
    get_pending_purchase_orders,
    calculate_days_of_cover,
)


class ReplenishmentAgentState(TypedDict):
    """State for the Replenishment Agent."""
    
    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str  # "analyze", "reorder", "vendor_review", "forecast"
    skus_to_check: list[str]
    vendor_code: str | None
    result: dict | None


# Define the tools available to this agent
replenishment_tools = [
    get_stock_level,
    calculate_reorder_point,
    calculate_economic_order_quantity,
    get_vendor_info,
    create_purchase_order,
    get_pending_purchase_orders,
    calculate_days_of_cover,
]


# Create the LLM with tools bound (uses configured provider)
llm = get_llm_with_tools(replenishment_tools)


SYSTEM_PROMPT = """You are the Replenishment Agent for a warehouse inventory management system.
Your role is to ensure optimal inventory levels through intelligent procurement decisions.

Your responsibilities:
1. Monitor stock levels and identify items needing replenishment
2. Calculate optimal reorder points based on demand and lead times
3. Determine Economic Order Quantities (EOQ) to minimize costs
4. Evaluate vendors based on quality, delivery, and pricing
5. Generate purchase orders when stock reaches reorder point

Key principles:
- JIT (Just-In-Time): Order exactly when needed to minimize carrying costs
- Safety Stock: Maintain buffer to prevent stockouts during demand spikes
- Days of Cover: Track how many days of inventory remain
- Vendor Diversification: Don't over-rely on single vendors

When analyzing replenishment needs:
1. First check current stock levels
2. Calculate days of cover based on demand
3. If below reorder point, calculate optimal order quantity
4. Select best vendor based on ratings and lead time
5. Create purchase order with recommended quantities

Available tools:
- get_stock_level: Check current inventory
- calculate_reorder_point: Determine when to reorder
- calculate_economic_order_quantity: Optimize order size
- get_vendor_info: Evaluate vendor performance
- create_purchase_order: Generate PO
- get_pending_purchase_orders: Check incoming orders
- calculate_days_of_cover: Assess inventory runway

Always explain your reasoning and recommendations clearly."""


def agent_node(state: ReplenishmentAgentState) -> dict:
    """Process the current state and decide on actions."""
    messages = state["messages"]
    
    # Add system prompt if this is a new conversation
    if len(messages) == 1:
        messages = [HumanMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: ReplenishmentAgentState) -> Literal["tools", "end"]:
    """Determine whether to continue with tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


def extract_result(state: ReplenishmentAgentState) -> dict:
    """Extract the final result from the conversation."""
    messages = state["messages"]
    last_message = messages[-1]
    
    return {
        "result": {
            "agent": "replenishment_agent",
            "response": last_message.content if hasattr(last_message, "content") else str(last_message),
            "timestamp": datetime.utcnow().isoformat(),
        }
    }


# Build the agent graph
def create_replenishment_agent():
    """Create and compile the replenishment agent graph."""
    workflow = StateGraph(ReplenishmentAgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(replenishment_tools))
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
replenishment_agent = create_replenishment_agent()


async def run_replenishment_agent(
    task: str,
    task_type: str = "analyze",
    skus_to_check: list[str] | None = None,
    vendor_code: str | None = None,
) -> dict:
    """
    Run the replenishment agent with a specific task.
    
    Args:
        task: Natural language description of the task
        task_type: Type of task (analyze, reorder, vendor_review, forecast)
        skus_to_check: Optional list of SKUs to analyze
        vendor_code: Optional vendor to focus on
        
    Returns:
        Dictionary with agent result
    """
    initial_state: ReplenishmentAgentState = {
        "messages": [HumanMessage(content=task)],
        "task_type": task_type,
        "skus_to_check": skus_to_check or [],
        "vendor_code": vendor_code,
        "result": None,
    }
    
    final_state = await replenishment_agent.ainvoke(initial_state)
    return final_state.get("result", {})
