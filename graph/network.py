"""Graph data model for Mini CDN Routing Simulator.

Supports directed weighted edges, node classification (origin, edge_server, user_region),
dynamic edge insertion/removal (network failure simulation), and weight updates
(congestion simulation).
"""

from typing import Dict, List, Optional, Any, Tuple
import copy


class Node:
    """Represents a network node in the CDN topology."""

    VALID_TYPES = {"origin", "edge_server", "user_region", "transit"}

    def __init__(
        self,
        node_id: str,
        node_type: str = "edge_server",
        label: Optional[str] = None,
        **metadata: Any
    ):
        if node_type not in self.VALID_TYPES:
            raise ValueError(
                f"Invalid node_type '{node_type}'. Must be one of {self.VALID_TYPES}"
            )
        self.id = str(node_id)
        self.node_type = node_type
        self.label = label if label is not None else self.id
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            **self.metadata,
        }

    def __repr__(self) -> str:
        return f"Node(id='{self.id}', type='{self.node_type}', label='{self.label}')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Node):
            return self.id == other.id and self.node_type == other.node_type
        return False

    def __hash__(self) -> int:
        return hash(self.id)


class Edge:
    """Represents a directed communication link with latency and capacity."""

    def __init__(
        self,
        u: str,
        v: str,
        latency: float,
        bandwidth_capacity: float = 1000.0,
        **metadata: Any
    ):
        self.u = str(u)
        self.v = str(v)
        self.latency = float(latency)
        self.bandwidth_capacity = float(bandwidth_capacity)
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to a JSON-serializable dictionary."""
        return {
            "u": self.u,
            "v": self.v,
            "latency": self.latency,
            "bandwidth_capacity": self.bandwidth_capacity,
            **self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"Edge({self.u} -> {self.v}, latency={self.latency}ms, "
            f"bw={self.bandwidth_capacity}Mbps)"
        )


class Graph:
    """Directed weighted graph representing CDN topology."""

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        # Adjacency map: u -> {v: Edge}
        self.adj: Dict[str, Dict[str, Edge]] = {}

    def add_node(
        self,
        node_id: str,
        node_type: str = "edge_server",
        label: Optional[str] = None,
        **metadata: Any
    ) -> Node:
        """Add a node to the network."""
        node_id = str(node_id)
        if node_id not in self.nodes:
            node = Node(node_id, node_type, label, **metadata)
            self.nodes[node_id] = node
            self.adj[node_id] = {}
            return node
        return self.nodes[node_id]

    def has_node(self, node_id: str) -> bool:
        """Check if node exists in graph."""
        return str(node_id) in self.nodes

    def get_node(self, node_id: str) -> Optional[Node]:
        """Retrieve a node by its ID."""
        return self.nodes.get(str(node_id))

    def add_edge(
        self,
        u: str,
        v: str,
        latency: float,
        bandwidth_capacity: float = 1000.0,
        bidirectional: bool = False,
        **metadata: Any
    ) -> Edge:
        """Add a directed edge (u -> v).

        If bidirectional is True, also adds (v -> u) with identical attributes.
        Missing nodes will be added with default type 'edge_server'.
        """
        u_str, v_str = str(u), str(v)
        if u_str not in self.nodes:
            self.add_node(u_str)
        if v_str not in self.nodes:
            self.add_node(v_str)

        edge = Edge(u_str, v_str, latency, bandwidth_capacity, **metadata)
        self.adj[u_str][v_str] = edge

        if bidirectional:
            reverse_edge = Edge(v_str, u_str, latency, bandwidth_capacity, **metadata)
            self.adj[v_str][u_str] = reverse_edge

        return edge

    def remove_edge(self, u: str, v: str, bidirectional: bool = False) -> bool:
        """Remove directed edge (u -> v) to simulate link failure."""
        u_str, v_str = str(u), str(v)
        removed = False
        if u_str in self.adj and v_str in self.adj[u_str]:
            del self.adj[u_str][v_str]
            removed = True

        if bidirectional and v_str in self.adj and u_str in self.adj[v_str]:
            del self.adj[v_str][u_str]
            removed = True

        return removed

    def has_edge(self, u: str, v: str) -> bool:
        """Check if directed edge (u -> v) exists."""
        u_str, v_str = str(u), str(v)
        return u_str in self.adj and v_str in self.adj[u_str]

    def get_edge(self, u: str, v: str) -> Optional[Edge]:
        """Retrieve edge (u -> v)."""
        u_str, v_str = str(u), str(v)
        return self.adj.get(u_str, {}).get(v_str)

    def update_edge_weight(
        self,
        u: str,
        v: str,
        latency: float,
        bandwidth_capacity: Optional[float] = None,
        bidirectional: bool = False
    ) -> bool:
        """Update latency/bandwidth on edge (u -> v) to simulate congestion."""
        u_str, v_str = str(u), str(v)
        if not self.has_edge(u_str, v_str):
            return False

        edge = self.adj[u_str][v_str]
        edge.latency = float(latency)
        if bandwidth_capacity is not None:
            edge.bandwidth_capacity = float(bandwidth_capacity)

        if bidirectional and self.has_edge(v_str, u_str):
            rev = self.adj[v_str][u_str]
            rev.latency = float(latency)
            if bandwidth_capacity is not None:
                rev.bandwidth_capacity = float(bandwidth_capacity)

        return True

    def get_adjacency(self) -> Dict[str, Dict[str, float]]:
        """Get adjacency map with latency weights: {u: {v: latency}}."""
        return {
            u: {v: edge.latency for v, edge in neighbors.items()}
            for u, neighbors in self.adj.items()
        }

    def get_nodes(self) -> List[Node]:
        """Return list of all nodes."""
        return list(self.nodes.values())

    def get_edges(self) -> List[Edge]:
        """Return list of all directed edges."""
        edges = []
        for neighbors in self.adj.values():
            edges.extend(neighbors.values())
        return edges

    def get_nodes_by_type(self, node_type: str) -> List[Node]:
        """Filter nodes by node_type."""
        return [node for node in self.nodes.values() if node.node_type == node_type]

    def clone(self) -> "Graph":
        """Create a deep copy of the graph."""
        return copy.deepcopy(self)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph to dictionary for frontend visualization & REST APIs."""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.get_edges()],
        }

    def __len__(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return sum(len(neighbors) for neighbors in self.adj.values())

    def __repr__(self) -> str:
        return f"Graph(nodes={len(self.nodes)}, edges={self.edge_count()})"
