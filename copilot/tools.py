"""Tool definitions, Pydantic argument schemas, and execution dispatcher for NetPilot Copilot."""

from typing import Dict, List, Optional, Any, Union, Tuple, Literal
from pydantic import BaseModel, Field, ValidationError

import services.network_service as net_service


# ------------------ Pydantic Argument Schemas ------------------

class ShortestPathArgs(BaseModel):
    source: str = Field(..., description="ID of the user region to route from (e.g. 'user_1', 'user_3').")
    algo: Literal["bellman_ford", "floyd_warshall"] = Field("bellman_ford", description="Shortest path algorithm: 'bellman_ford' or 'floyd_warshall'.")


class CompareAlgorithmsArgs(BaseModel):
    source: str = Field(..., description="ID of the user region to route from.")


class KillEdgeArgs(BaseModel):
    edge_id: Optional[str] = Field(None, description="Identifier of the link to sever, e.g. 'user_1<->edge_1'.")
    u: Optional[str] = Field(None, description="Source node of the edge.")
    v: Optional[str] = Field(None, description="Target node of the edge.")
    confirmed: bool = Field(False, description="Whether the user has explicitly confirmed this destructive failure.")


class ResetNetworkArgs(BaseModel):
    confirmed: bool = Field(False, description="Whether the user has explicitly confirmed resetting the active network.")


class WhatIfArgs(BaseModel):
    remove_nodes: Optional[List[str]] = Field(default_factory=list, description="List of node IDs to simulate removing.")
    remove_edges: Optional[List[str]] = Field(default_factory=list, description="List of edge IDs to simulate removing (e.g. ['user_1<->edge_1']).")
    source: Optional[str] = Field(None, description="Optional target user region to evaluate. Defaults to first user region.")


class MaxFlowArgs(BaseModel):
    source: Optional[str] = Field(None, description="Origin node ID. Defaults to primary origin.")
    sinks: Optional[List[str]] = Field(None, description="List of target sink node IDs. Defaults to all edge servers.")
    algo: Literal["edmonds_karp", "ford_fulkerson"] = Field("edmonds_karp", description="Max flow algorithm: 'edmonds_karp' (BFS) or 'ford_fulkerson' (DFS).")


class FindBottleneckArgs(BaseModel):
    source: Optional[str] = Field(None, description="Origin node ID.")
    sinks: Optional[List[str]] = Field(None, description="List of target sink node IDs.")


class GetMetricsArgs(BaseModel):
    pass


class ListNodesArgs(BaseModel):
    node_type: Optional[Literal["origin", "edge_server", "user_region", "transit"]] = Field(None, description="Optional filter by node type.")


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
                    "algo": {"type": "string", "enum": ["bellman_ford", "floyd_warshall"], "default": "bellman_ford"},
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
                    "remove_nodes": {"type": "array", "items": {"type": "string"}, "description": "Node IDs to simulate removing"},
                    "remove_edges": {"type": "array", "items": {"type": "string"}, "description": "Edge IDs to simulate removing (e.g. 'edge_1<->edge_2')"},
                    "source": {"type": "string", "description": "User region to evaluate before/after impact"},
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
                    "source": {"type": "string", "description": "Origin node ID"},
                    "sinks": {"type": "array", "items": {"type": "string"}, "description": "Destination sink node IDs"},
                    "algo": {"type": "string", "enum": ["edmonds_karp", "ford_fulkerson"], "default": "edmonds_karp"},
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
                    "source": {"type": "string", "description": "Origin node ID"},
                    "sinks": {"type": "array", "items": {"type": "string"}, "description": "Sink node IDs"},
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
                    "node_type": {"type": "string", "enum": ["origin", "edge_server", "user_region", "transit"]},
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
                    "edge_id": {"type": "string", "description": "Edge identifier (e.g. 'user_1<->edge_1')"},
                    "confirmed": {"type": "boolean", "default": False},
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
                    "confirmed": {"type": "boolean", "default": False},
                },
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
                algo=validated_args.get("algo", "bellman_ford"),
                session_id=session_id,
            )
        elif function_name == "compare_algorithms":
            res = net_service.compare_algorithms(
                source=validated_args["source"],
                session_id=session_id,
            )
        elif function_name == "what_if":
            res = net_service.what_if(
                remove_nodes=validated_args.get("remove_nodes"),
                remove_edges=validated_args.get("remove_edges"),
                source=validated_args.get("source"),
                session_id=session_id,
            )
        elif function_name == "max_flow":
            res = net_service.max_flow(
                source=validated_args.get("source"),
                sinks=validated_args.get("sinks"),
                algo=validated_args.get("algo", "edmonds_karp"),
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
        else:
            res = {"error": f"Unhandled tool {function_name}"}

        return res, False

    except Exception as e:
        return {"error": f"Execution of {function_name} failed: {str(e)}"}, False
