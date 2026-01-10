"""
Quality Agent

Monitors expiration dates and environmental sensor data. Responsible for:
- Expiry tracking and FIFO enforcement
- IoT sensor monitoring (temperature, humidity, shock)
- Fragile item alerts
- Cold chain compliance
"""

from datetime import datetime
from typing import Annotated, TypedDict, Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.config import get_settings
from src.tools.inventory_tools import get_expiring_items
from src.tools.sensor_tools import (
    get_sensor_readings,
    check_environmental_alerts,
    get_location_conditions,
)


settings = get_settings()


class QualityAgentState(TypedDict):
    """State for the Quality Agent."""
    
    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str  # "monitor", "expiry_check", "alert_review", "compliance"
    location_code: str | None
    sensor_id: str | None
    result: dict | None


# Define the tools available to this agent
quality_tools = [
    get_expiring_items,
    get_sensor_readings,
    check_environmental_alerts,
    get_location_conditions,
]


# Create the LLM with tools bound
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=0,
    api_key=settings.openai_api_key,
).bind_tools(quality_tools)


SYSTEM_PROMPT = """You are the Quality Agent for a warehouse inventory management system.
Your role is to ensure product quality through expiration monitoring and environmental compliance.

Your responsibilities:
1. Monitor expiration dates and enforce FIFO picking
2. Track environmental conditions via IoT sensors
3. Ensure cold chain compliance for temperature-sensitive items
4. Alert on conditions that could damage inventory
5. Recommend actions for at-risk inventory

Quality principles:
- PROACTIVE: Identify issues before they become problems
- FIFO ENFORCEMENT: Oldest inventory should be picked first
- TEMPERATURE CRITICAL: Cold chain breaks can be costly
- IMMEDIATE RESPONSE: Environmental alerts need quick action
- DOCUMENTATION: Track all quality incidents

Expiration management:
1. Items expiring within 30 days need attention
2. Items expiring within 7 days are critical
3. Expired items must be quarantined and reviewed
4. Consider markdowns for near-expiry items

Environmental monitoring:
1. Temperature ranges must be maintained for cold storage
2. Humidity affects many products (electronics, paper, food)
3. Shock events can damage fragile items
4. Sensor offline is itself an alert condition

Available tools:
- get_expiring_items: Find items approaching expiration
- get_sensor_readings: Get historical sensor data
- check_environmental_alerts: Scan for current issues
- get_location_conditions: Check specific location environment

Always prioritize by risk and provide clear action recommendations."""


def agent_node(state: QualityAgentState) -> dict:
    """Process the current state and decide on actions."""
    messages = state["messages"]
    
    # Add system prompt if this is a new conversation
    if len(messages) == 1:
        messages = [HumanMessage(content=SYSTEM_PROMPT)] + messages
    
    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: QualityAgentState) -> Literal["tools", "end"]:
    """Determine whether to continue with tools or end."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"


def extract_result(state: QualityAgentState) -> dict:
    """Extract the final result from the conversation."""
    messages = state["messages"]
    last_message = messages[-1]
    
    return {
        "result": {
            "agent": "quality_agent",
            "response": last_message.content if hasattr(last_message, "content") else str(last_message),
            "timestamp": datetime.utcnow().isoformat(),
        }
    }


# Build the agent graph
def create_quality_agent():
    """Create and compile the quality agent graph."""
    workflow = StateGraph(QualityAgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(quality_tools))
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
quality_agent = create_quality_agent()


async def run_quality_agent(
    task: str,
    task_type: str = "monitor",
    location_code: str | None = None,
    sensor_id: str | None = None,
) -> dict:
    """
    Run the quality agent with a specific task.
    
    Args:
        task: Natural language description of the task
        task_type: Type of task (monitor, expiry_check, alert_review, compliance)
        location_code: Optional location for context
        sensor_id: Optional sensor ID for context
        
    Returns:
        Dictionary with agent result
    """
    initial_state: QualityAgentState = {
        "messages": [HumanMessage(content=task)],
        "task_type": task_type,
        "location_code": location_code,
        "sensor_id": sensor_id,
        "result": None,
    }
    
    final_state = await quality_agent.ainvoke(initial_state)
    return final_state.get("result", {})
