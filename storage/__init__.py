"""Storage layer package for Mini CDN Simulator."""

from .event_store import EventStore, NetworkEvent, get_event_store

__all__ = ["EventStore", "NetworkEvent", "get_event_store"]
