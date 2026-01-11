"""
Orchestrator Agent

The central coordinator that manages the global warehouse state and delegates
tasks to specialized agents. Responsible for:
- Global warehouse state management
- Priority task queue
- Agent coordination and routing
- System reconciliation
"""

from datetime import datetime
from typing import Annotated, TypedDict, Literal
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from src.llm import get_llm


class AgentType(str, Enum):
    """Types of agents available."""
    
    TRACKING = "tracking"
    REPLENISHMENT = "replenishment"
    OPERATIONS = "operations"
    AUDIT = "audit"
    QUALITY = "quality"
    ORCHESTRATOR = "orchestrator"


class TaskPriority(int, Enum):
    """Task priority levels."""
    
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 5
    LOW = 8
    BACKGROUND = 10


class OrchestratorState(TypedDict):
    """State for the Orchestrator Agent."""
    
    messages: Annotated[list[BaseMessage], add_messages]
    user_request: str
    selected_agent: str | None
    agent_task: str | None
    agent_result: dict | None
    final_response: str | None


# Create the LLM for orchestration decisions (uses configured provider)
llm = get_llm()


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator Agent for an intelligent warehouse inventory management system.
Your role is to understand user requests and delegate them to the appropriate specialized agent.

Available agents and their capabilities:

1. **TRACKING AGENT** - Digital Twin Management
   - Stock level queries (current inventory, availability)
   - Stock movements (receiving, picking, transfers)
   - Allocation management (reserving stock for orders)
   - Location-based inventory queries
   Use for: "What's in stock?", "Update inventory", "Check location X", "Allocate for order"

2. **REPLENISHMENT AGENT** - Procurement & Planning
   - Reorder point calculations
   - Economic order quantity optimization
   - Vendor management and selection
   - Purchase order creation
   - Days of cover analysis
   Use for: "Do we need to reorder?", "Create PO", "Check vendor", "Stock forecast"

3. **OPERATIONS AGENT** - Workflow Optimization
   - Pick route generation and optimization
   - Putaway location suggestions
   - Warehouse layout analysis
   - Batch picking coordination
   Use for: "Generate pick route", "Where to store?", "Optimize picking", "Warehouse utilization"

4. **AUDIT AGENT** - Accuracy & Compliance
   - Cycle count processing
   - Inventory reconciliation
   - Discrepancy investigation
   - Shrinkage detection
   Use for: "Cycle count", "Reconcile", "Investigate variance", "Audit location"

5. **QUALITY AGENT** - Product Integrity
   - Expiration monitoring
   - Environmental sensor checks
   - Temperature/humidity alerts
   - Cold chain compliance
   Use for: "Check expiring items", "Sensor status", "Temperature alerts", "Quality issues"

When you receive a request:
1. Analyze what the user is trying to accomplish
2. Determine which agent is best suited to handle it
3. Formulate a clear task description for that agent
4. If the request spans multiple domains, prioritize the primary need

Respond with JSON in this format:
{
    "analysis": "Brief analysis of the user's request",
    "selected_agent": "tracking|replenishment|operations|audit|quality",
    "agent_task": "Clear task description for the selected agent",
    "priority": "critical|high|medium|low"
}

If you cannot determine the appropriate agent or the request is unclear, ask for clarification."""


def analyze_request(state: OrchestratorState) -> dict:
    """Analyze the user request and determine routing."""
    user_request = state["user_request"]
    
    messages = [
        SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"User request: {user_request}\n\nAnalyze this request and determine which agent should handle it."),
    ]
    
    response = llm.invoke(messages)
    content = response.content
    
    # Parse the response to extract routing information
    # In production, you'd use structured output or JSON mode
    import json
    import re
    
    # Try to extract JSON from the response
    json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
    if json_match:
        try:
            routing = json.loads(json_match.group())
            return {
                "selected_agent": routing.get("selected_agent"),
                "agent_task": routing.get("agent_task"),
                "messages": [AIMessage(content=content)],
            }
        except json.JSONDecodeError:
            pass
    
    # Fallback: try to determine agent from keywords
    request_lower = user_request.lower()
    
    if any(kw in request_lower for kw in ["stock", "inventory", "quantity", "allocate", "location"]):
        selected_agent = "tracking"
    elif any(kw in request_lower for kw in ["reorder", "purchase", "vendor", "buy", "po", "supplier"]):
        selected_agent = "replenishment"
    elif any(kw in request_lower for kw in ["pick", "route", "putaway", "store", "layout", "optimize"]):
        selected_agent = "operations"
    elif any(kw in request_lower for kw in ["count", "audit", "reconcile", "discrepancy", "variance"]):
        selected_agent = "audit"
    elif any(kw in request_lower for kw in ["expir", "temperature", "sensor", "quality", "humidity"]):
        selected_agent = "quality"
    else:
        selected_agent = "tracking"  # Default to tracking
    
    return {
        "selected_agent": selected_agent,
        "agent_task": user_request,
        "messages": [AIMessage(content=content)],
    }


async def execute_agent(state: OrchestratorState) -> dict:
    """Execute the selected agent with the task."""
    selected_agent = state["selected_agent"]
    agent_task = state["agent_task"]
    
    if not selected_agent or not agent_task:
        return {
            "agent_result": {"error": "No agent selected or task defined"},
        }
    
    # Import and run the appropriate agent
    if selected_agent == "tracking":
        from src.agents.tracking_agent import run_tracking_agent
        result = await run_tracking_agent(agent_task)
    elif selected_agent == "replenishment":
        from src.agents.replenishment_agent import run_replenishment_agent
        result = await run_replenishment_agent(agent_task)
    elif selected_agent == "operations":
        from src.agents.operations_agent import run_operations_agent
        result = await run_operations_agent(agent_task)
    elif selected_agent == "audit":
        from src.agents.audit_agent import run_audit_agent
        result = await run_audit_agent(agent_task)
    elif selected_agent == "quality":
        from src.agents.quality_agent import run_quality_agent
        result = await run_quality_agent(agent_task)
    else:
        result = {"error": f"Unknown agent: {selected_agent}"}
    
    return {"agent_result": result}


def synthesize_response(state: OrchestratorState) -> dict:
    """Synthesize the final response from agent results."""
    agent_result = state.get("agent_result", {})
    selected_agent = state.get("selected_agent", "unknown")
    user_request = state.get("user_request", "")
    
    if "error" in agent_result:
        final_response = f"I encountered an error: {agent_result['error']}"
    else:
        # Use LLM to create a natural response
        response_content = agent_result.get("response", str(agent_result))
        
        synthesis_prompt = f"""Based on the user's request and the agent's response, provide a clear, 
helpful summary for the user.

User Request: {user_request}
Agent Used: {selected_agent}
Agent Response: {response_content}

Provide a concise, helpful response that addresses the user's original request."""
        
        messages = [
            SystemMessage(content="You are a helpful warehouse management assistant. Summarize agent responses clearly and concisely."),
            HumanMessage(content=synthesis_prompt),
        ]
        
        synthesis = llm.invoke(messages)
        final_response = synthesis.content
    
    return {
        "final_response": final_response,
        "messages": [AIMessage(content=final_response)],
    }


def create_orchestrator_graph():
    """Create the orchestrator workflow graph."""
    workflow = StateGraph(OrchestratorState)
    
    # Add nodes
    workflow.add_node("analyze", analyze_request)
    workflow.add_node("execute", execute_agent)
    workflow.add_node("synthesize", synthesize_response)
    
    # Set entry point
    workflow.set_entry_point("analyze")
    
    # Add edges
    workflow.add_edge("analyze", "execute")
    workflow.add_edge("execute", "synthesize")
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()


# Create the compiled orchestrator
orchestrator_graph = create_orchestrator_graph()


async def process_request(user_request: str) -> dict:
    """
    Process a user request through the orchestrator.
    
    Args:
        user_request: Natural language request from the user
        
    Returns:
        Dictionary with the final response and metadata
    """
    initial_state: OrchestratorState = {
        "messages": [],
        "user_request": user_request,
        "selected_agent": None,
        "agent_task": None,
        "agent_result": None,
        "final_response": None,
    }
    
    final_state = await orchestrator_graph.ainvoke(initial_state)
    
    return {
        "response": final_state.get("final_response", ""),
        "agent_used": final_state.get("selected_agent", ""),
        "agent_result": final_state.get("agent_result", {}),
        "timestamp": datetime.utcnow().isoformat(),
    }
