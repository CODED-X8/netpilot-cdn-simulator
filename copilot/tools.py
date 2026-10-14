"""Tool definitions, Pydantic argument schemas, and execution dispatcher for NetPilot Copilot."""

from typing import Dict, List, Optional, Any, Union, Tuple, Literal
from pydantic import BaseModel, Field, ValidationError

import services.network_service as net_service


# ------------------ Pydantic Argument Schemas ------------------

class ShortestPathArgs(BaseModel):
    source: str = Field(..., description="ID of the user region to route from (e.g. 'user_1', 'user_3').")
    algo: Optional[Literal["bellman_ford", "floyd_warshall"]] = Field("bellman_ford", description="Shortest path algorithm: 'bellman_ford' or 'floyd_warshall'.")


class CompareAlgorithmsArgs(BaseModel):
    source: str = Field(..., description="ID of the user region to route from.")


class KillEdgeArgs(BaseModel):
    edge_id: Optional[str] = Field(None, description="Identifier of the link to sever, e.g. 'user_1<->edge_1'.")
    u: Optional[str] = Field(None, description="Source node of the edge.")
    v: Optional[str] = Field(None, description="Target node of the edge.")
    confirmed: Optional[bool] = Field(False, description="Whether the user has explicitly confirmed this destructive failure.")


class ResetNetworkArgs(BaseModel):
    confirmed: Optional[bool] = Field(False, description="Whether the user has explicitly confirmed resetting the active network.")


class WhatIfArgs(BaseModel):
    remove_nodes: Optional[List[str]] = Field(default_factory=list, description="List of node IDs to simulate removing.")
    remove_edges: Optional[List[str]] = Field(default_factory=list, description="List of edge IDs to simulate removing (e.g. ['user_1<->edge_1']).")
    source: Optional[str] = Field(None, description="Optional target user region to evaluate. Defaults to first user region.")


class MaxFlowArgs(BaseModel):
    source: Optional[str] = Field(None, description="Origin node ID. Defaults to primary origin.")
    sinks: Optional[List[str]] = Field(None, description="List of target sink node IDs. Defaults to all edge servers.")
    algo: Optional[Literal["edmonds_karp", "ford_fulkerson"]] = Field("edmonds_karp", description="Max flow algorithm: 'edmonds_karp' (BFS) or 'ford_fulkerson' (DFS).")


class FindBottleneckArgs(BaseModel):
    source: Optional[str] = Field(None, description="Origin node ID.")
    sinks: Optional[List[str]] = Field(None, description="List of target sink node IDs.")


class GetMetricsArgs(BaseModel):
    pass


class ListNodesArgs(BaseModel):
    node_type: Optional[Literal["origin", "edge_server", "user_region", "transit"]] = Field(None, description="Optional filter by node type.")


class SearchHistoryArgs(BaseModel):
    query: str = Field(..., description="Query string to search past events and operational runbooks.")
    doc_type: Optional[Literal["event", "runbook"]] = Field(None, description="Optional document type filter: 'event' or 'runbook'.")
    limit: Optional[int] = Field(3, description="Maximum number of relevant context chunks to retrieve.")


class GeneratePostmortemArgs(BaseModel):
    event_id: Optional[str] = Field(None, description="Event ID to generate postmortem for. Defaults to most recent failure.")
    time_window_minutes: Optional[int] = Field(60, description="Contextual event history time window in minutes.")


class ProposeMitigationsArgs(BaseModel):
    goal: str = Field(..., description="Goal: 'maximize throughput', 'minimize latency', or 'resolve bottleneck'.")


TOOL_SCHEMAS: Dict[str, Any] = {
    "shortest_path": ShortestPathArgs,
    "compare_algorithms": CompareAlgorithmsArgs,
    "kill_edge": KillEdgeArgs,
    "reset_network": ResetNetworkArgs,
    "what_if": WhatIfArgs,
    "max_flow": MaxFlowArgs,
    "find_bottleneck": FindBottleneckArgs,
    "get_metrics": GetMetricsArgs,
    "list_nodes": ListNodesArgs,
    "search_history": SearchHistoryArgs,
    "generate_postmortem": GeneratePostmortemArgs,
    "propose_mitigations": ProposeMitigationsArgs,
}


# ------------------ OpenAI Function Specifications ------------------

COPILOT_TOOLS_OPENAI_SPEC: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "shortest_path",
            "description": "Compute lowest-latency route and hops from a user region to the nearest edge server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "ID of user region (e.g. 'user_1', 'user_3')"},
                    "algo": {"type": ["string", "null"], "enum": ["bellman_ford", "floyd_warshall", None], "default": "bellman_ford"},
                },
                "required": ["source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_algorithms",
            "description": "Run both Bellman-Ford and Floyd-Warshall on the same source to cross-validate latency and path agreement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "ID of user region"},
                },
                "required": ["source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "what_if",
            "description": "Simulate a hypothetical failure (node or link outage) on a graph COPY without altering the live network.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remove_nodes": {"type": ["array", "null"], "items": {"type": "string"}, "description": "Node IDs to simulate removing"},
                    "remove_edges": {"type": ["array", "null"], "items": {"type": "string"}, "description": "Edge IDs to simulate removing (e.g. 'edge_1<->edge_2')"},
                    "source": {"type": ["string", "null"], "description": "User region to evaluate before/after impact"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "max_flow",
            "description": "Calculate maximum bandwidth throughput (Mbps) from origin to edge/user sinks using Edmonds-Karp or Ford-Fulkerson.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": ["string", "null"], "description": "Origin node ID"},
                    "sinks": {"type": ["array", "null"], "items": {"type": "string"}, "description": "Destination sink node IDs"},
                    "algo": {"type": ["string", "null"], "enum": ["edmonds_karp", "ford_fulkerson", None], "default": "edmonds_karp"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_bottleneck",
            "description": "Identify network capacity bottlenecks and min-cut edge saturated boundaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": ["string", "null"], "description": "Origin node ID"},
                    "sinks": {"type": ["array", "null"], "items": {"type": "string"}, "description": "Sink node IDs"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": "Retrieve current network health metrics (node counts, link counts, average latency, total capacity).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_nodes",
            "description": "List all active network nodes with their roles and regions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_type": {"type": ["string", "null"], "enum": ["origin", "edge_server", "user_region", "transit", None]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_edge",
            "description": "DESTRUCTIVE: Physically sever a communication link in the active network. Requires confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "edge_id": {"type": ["string", "null"], "description": "Edge identifier (e.g. 'user_1<->edge_1')"},
                    "confirmed": {"type": ["boolean", "null"], "default": False},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_network",
            "description": "DESTRUCTIVE: Reset the network topology back to default. Requires confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed": {"type": ["boolean", "null"], "default": False},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_history",
            "description": "Search past network events and incident runbooks (link failure, congestion, regional outage, latency regression, bad topology upload) using semantic vector retrieval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query describing incident, symptoms, or mitigation procedures"},
                    "doc_type": {"type": ["string", "null"], "enum": ["event", "runbook", None], "description": "Optional filter for events or runbooks"},
                    "limit": {"type": ["integer", "null"], "default": 3, "description": "Maximum number of relevant chunks to retrieve"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_postmortem",
            "description": "Generate an incident postmortem report in structured Markdown format based on recorded network failure and outage events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": ["string", "null"], "description": "Specific event ID (e.g. 'evt_abc123'). If omitted, targets most recent outage event."},
                    "time_window_minutes": {"type": ["integer", "null"], "default": 60, "description": "Contextual timeline history window in minutes."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_mitigations",
            "description": "Propose and simulate candidate topology changes (add_edge, increase_capacity, remove_edge) to achieve a network goal (e.g. 'maximize throughput', 'minimize latency', 'resolve bottleneck').",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Performance goal: 'maximize throughput', 'minimize latency', or 'resolve bottleneck'."},
                },
                "required": ["goal"],
            },
        },
    },
]


def execute_tool_call(
    function_name: str,
    raw_arguments: Dict[str, Any],
    session_id: str = "default",
) -> Tuple[Dict[str, Any], bool]:
    """Validate arguments with Pydantic and execute the corresponding service function.

    Returns:
        (result_dict, requires_confirmation_boolean)
    """
    schema_cls = TOOL_SCHEMAS.get(function_name)
    if not schema_cls:
        return {"error": f"Tool '{function_name}' is not recognized."}, False

    # 1. Pydantic argument validation
    try:
        validated_args = schema_cls(**raw_arguments).model_dump()
    except ValidationError as ve:
        return {"error": f"Invalid arguments for {function_name}: {str(ve)}"}, False

    # 2. Check destructive confirmation gate
    if function_name in ("kill_edge", "reset_network"):
        if not validated_args.get("confirmed", False):
            return {
                "confirmation_required": True,
                "tool": function_name,
                "arguments": validated_args,
                "message": f"Destructive operation '{function_name}' requires explicit user confirmation.",
            }, True

    # 3. Dispatch to service layer
    try:
        if function_name == "shortest_path":
            res = net_service.shortest_path(
                source=validated_args["source"],
                algo=validated_args.get("algo") or "bellman_ford",
                session_id=session_id,
            )
        elif function_name == "compare_algorithms":
            res = net_service.compare_algorithms(
                source=validated_args["source"],
                session_id=session_id,
            )
        elif function_name == "what_if":
            res = net_service.what_if(
                remove_nodes=validated_args.get("remove_nodes") or [],
                remove_edges=validated_args.get("remove_edges") or [],
                source=validated_args.get("source"),
                session_id=session_id,
            )
        elif function_name == "max_flow":
            res = net_service.max_flow(
                source=validated_args.get("source"),
                sinks=validated_args.get("sinks"),
                algo=validated_args.get("algo") or "edmonds_karp",
                session_id=session_id,
            )
        elif function_name == "find_bottleneck":
            res = net_service.find_bottleneck(
                source=validated_args.get("source"),
                sinks=validated_args.get("sinks"),
                session_id=session_id,
            )
        elif function_name == "get_metrics":
            res = net_service.get_metrics(session_id=session_id)
        elif function_name == "list_nodes":
            res = net_service.list_nodes(
                node_type=validated_args.get("node_type"),
                session_id=session_id,
            )
        elif function_name == "kill_edge":
            res = net_service.kill_edge(
                edge_id=validated_args.get("edge_id"),
                u=validated_args.get("u"),
                v=validated_args.get("v"),
                session_id=session_id,
            )
        elif function_name == "reset_network":
            res = net_service.reset_network(session_id=session_id)
        elif function_name == "search_history":
            from rag.vector_store import get_vector_store
            vs = get_vector_store()
            vs.sync_events(limit=25)
            hits = vs.search(
                query=validated_args["query"],
                doc_type=validated_args.get("doc_type"),
                limit=validated_args.get("limit") or 3,
            )
            res = {
                "query": validated_args["query"],
                "results_count": len(hits),
                "retrieved_context": [
                    {
                        "id": h["id"],
                        "doc_type": h["doc_type"],
                        "title": h["title"],
                        "chunk_path": h["chunk_path"],
                        "similarity": h["similarity"],
                        "content": h["content"],
                    }
                    for h in hits
                ],
            }
        elif function_name == "generate_postmortem":
            from services.postmortem_service import generate_postmortem as gen_pm
            res = gen_pm(
                event_id=validated_args.get("event_id"),
                session_id=session_id,
                time_window_minutes=validated_args.get("time_window_minutes") or 60,
            )
        elif function_name == "propose_mitigations":
            from services.mitigation_service import propose_and_simulate_mitigations
            res = propose_and_simulate_mitigations(
                goal=validated_args["goal"],
                session_id=session_id,
            )
        else:
            res = {"error": f"Unhandled tool {function_name}"}

        return res, False

    except Exception as e:
        return {"error": f"Execution of {function_name} failed: {str(e)}"}, False
