"""OpenAI-compatible LLM Provider Layer with Fake Provider for testing.

Configured by environment variables:
- LLM_BASE_URL (defaults to https://api.openai.com/v1)
- LLM_API_KEY (if unset, copilot features are gracefully disabled)
- LLM_MODEL (defaults to gpt-4o-mini)
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Tuple


def load_dotenv(env_path: Optional[str] = None) -> None:
    """Load key-value pairs from .env into os.environ if not already present."""
    if env_path is None:
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# Auto-load .env on module import
load_dotenv()


class LLMToolCall:
    """Represents a structured function call request from the model."""

    def __init__(self, call_id: str, function_name: str, arguments: Dict[str, Any]):
        self.id = call_id
        self.function_name = function_name
        self.arguments = arguments

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.function_name,
                "arguments": json.dumps(self.arguments),
            },
        }


class LLMResponse:
    """Standardized LLM response object."""

    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[LLMToolCall]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
    ):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.model_name = model_name
        self.provider_name = provider_name


class BaseLLMProvider:
    """Abstract base provider interface."""

    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseLLMProvider):
    """Client for any OpenAI-compatible chat completions endpoint (Groq, OpenAI)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        if tools and len(tools) > 0:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "NetPilot/1.0 (Mini CDN Simulator)",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            choice = data["choices"][0]["message"]
            content = choice.get("content")

            tool_calls = []
            if "tool_calls" in choice and choice["tool_calls"]:
                for tc in choice["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                    tool_calls.append(LLMToolCall(tc["id"], fn_name, args))

            usage = data.get("usage", {})
            provider_type = "groq" if "groq" in self.base_url.lower() else "openai"

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                model_name=self.model,
                provider_name=provider_type,
            )

        except Exception as e:
            if isinstance(e, urllib.error.HTTPError):
                err_body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"LLM API HTTP {e.code}: {err_body}")
            raise RuntimeError(f"LLM API request failed: {str(e)}")


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic Fake Provider for automated testing and offline evaluation.

    Maps common queries to deterministic tool calls and generates grounded explanations.
    """

    def __init__(self, scripted_steps: Optional[List[Any]] = None):
        self.scripted_steps = list(scripted_steps) if scripted_steps else []
        self.step_idx = 0

    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        res = self._raw_chat_complete(messages, tools)
        if res.model_name is None:
            res.model_name = "fake-llm"
        if res.provider_name is None:
            res.provider_name = "fake"
        return res

    def _raw_chat_complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        # 1. If explicit scripted steps are provided, yield them
        if self.step_idx < len(self.scripted_steps):
            step = self.scripted_steps[self.step_idx]
            self.step_idx += 1
            if isinstance(step, LLMResponse):
                return step
            elif isinstance(step, tuple):
                # tuple of (tool_name, args_dict)
                fn_name, args = step
                return LLMResponse(
                    tool_calls=[LLMToolCall("call_mock_1", fn_name, args)],
                    prompt_tokens=150,
                    completion_tokens=25,
                )
            else:
                return LLMResponse(content=str(step), prompt_tokens=100, completion_tokens=50)

        # 2. Check last message
        last_msg = messages[-1] if messages else {}

        # If last message was a tool result, generate final synthesized explanation
        if last_msg.get("role") == "tool":
            tool_name = last_msg.get("name", "tool")
            raw_content = last_msg.get("content", "{}")
            if "Metadata: " in raw_content:
                try:
                    tool_data = json.loads(raw_content.split("Metadata: ", 1)[1])
                except Exception:
                    tool_data = {}
            else:
                try:
                    tool_data = json.loads(raw_content)
                except Exception:
                    tool_data = {}

            if tool_name == "what_if":
                before_lat = tool_data.get("before", {}).get("latency", 0.0)
                after_lat = tool_data.get("after", {}).get("latency", 0.0)
                delta = tool_data.get("latency_delta_ms", 0.0)
                hops = tool_data.get("after", {}).get("hops", 0)
                content = (
                    f"Tool what_if on {tool_data.get('topology_name', 'network')} shows that if the specified link fails, "
                    f"the latency increases by {delta} ms from {before_lat} ms to {after_lat} ms with {hops} hops."
                )
            elif tool_name == "find_bottleneck":
                max_flow = tool_data.get("max_flow", 0.0)
                cap = tool_data.get("total_bottleneck_capacity", 0.0)
                count = tool_data.get("bottleneck_count", 0)
                content = (
                    f"Tool find_bottleneck reports the network bottleneck has {count} cut edges "
                    f"with total capacity {cap} Mbps and max flow {max_flow} Mbps."
                )
            elif tool_name == "shortest_path":
                edge = tool_data.get("best_edge", "none")
                lat = tool_data.get("latency", 0.0)
                hops = tool_data.get("hops", 0)
                content = (
                    f"Tool shortest_path determined the optimal edge server is {edge} "
                    f"with end-to-end latency {lat} ms across {hops} hops."
                )
            elif tool_name == "max_flow":
                flow = tool_data.get("max_flow", 0.0)
                content = f"Tool max_flow determined the maximum network throughput is {flow} Mbps."
            elif tool_name == "get_metrics":
                nodes = tool_data.get("node_count", 0)
                edges = tool_data.get("edge_count", 0)
                lat = tool_data.get("average_latency_ms", 0.0)
                content = f"Tool get_metrics reports {nodes} nodes and {edges} edges with average latency {lat} ms."
            elif tool_name == "search_history":
                count = tool_data.get("count", tool_data.get("results_count", 0))
                chunks = tool_data.get("retrieved_context", [])
                top_chunk = chunks[0] if chunks else {}
                title = top_chunk.get("title", "Runbook")
                path = top_chunk.get("chunk_path", "runbook.md")
                content = (
                    f"Tool search_history retrieved {count} relevant runbook sections. "
                    f"According to standard operational procedures in '{path}' ({title}): "
                    f"Inspect the network status, assess latency impact, and execute verified actions."
                )
            elif tool_name == "generate_postmortem":
                ev_id = tool_data.get("event_id", "incident")
                content = f"Tool generate_postmortem created the incident postmortem report for {ev_id}. All numbers and event timelines are verified."
            elif tool_name == "propose_mitigations":
                goal = tool_data.get("goal", "performance")
                cands = tool_data.get("ranked_candidates", [])
                top_cand = cands[0] if cands else {}
                action = top_cand.get("action", "upgrade")
                target = top_cand.get("target", "link")
                content = (
                    f"Tool propose_mitigations evaluated candidates on isolated graph copies for goal '{goal}'. "
                    f"Top ranked candidate is {action} on {target}. "
                    f"Rankings are strictly based on measured simulation metrics."
                )
            else:
                content = f"Tool {tool_name} executed successfully. Facts verified: {json.dumps(tool_data)}."

            return LLMResponse(content=content, prompt_tokens=220, completion_tokens=65)

        # 3. Else inspect user prompt to trigger appropriate tool call
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "").lower()
                break

        if "fails" in user_text or "what if" in user_text or "what happens if" in user_text:
            # Extract target edge or node if present
            edge = "user_1<->edge_1"
            for token in user_text.split():
                if "edge_" in token or "user_" in token:
                    edge = token.strip("?,.:;\"'")
            return LLMResponse(
                tool_calls=[LLMToolCall("call_what_if", "what_if", {"remove_edges": [edge], "source": "user_1"})],
                prompt_tokens=180,
                completion_tokens=30,
            )
        elif "mitigat" in user_text or "propose" in user_text or "optimize" in user_text:
            goal = "maximize throughput"
            if "latency" in user_text:
                goal = "minimize latency"
            elif "bottleneck" in user_text:
                goal = "resolve bottleneck"
            return LLMResponse(
                tool_calls=[LLMToolCall("call_mitigations", "propose_mitigations", {"goal": goal})],
                prompt_tokens=160,
                completion_tokens=25,
            )
        elif "bottleneck" in user_text or "min cut" in user_text or "min-cut" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_bottleneck", "find_bottleneck", {})],
                prompt_tokens=170,
                completion_tokens=25,
            )
        elif "flow" in user_text or "throughput" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_flow", "max_flow", {})],
                prompt_tokens=160,
                completion_tokens=25,
            )
        elif "compare" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_compare", "compare_algorithms", {"source": "user_1"})],
                prompt_tokens=170,
                completion_tokens=25,
            )
        elif "metric" in user_text or "status" in user_text or "how many nodes" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_metrics", "get_metrics", {})],
                prompt_tokens=150,
                completion_tokens=20,
            )
        elif "kill" in user_text:
            edge = "user_1<->edge_1"
            for token in user_text.split():
                if "edge_" in token or "user_" in token:
                    edge = token.strip("?,.:;\"'")
            return LLMResponse(
                tool_calls=[LLMToolCall("call_kill", "kill_edge", {"edge_id": edge, "confirmed": False})],
                prompt_tokens=150,
                completion_tokens=20,
            )
        elif "reset" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_reset", "reset_network", {"confirmed": False})],
                prompt_tokens=150,
                completion_tokens=20,
            )
        elif "runbook" in user_text or "procedure" in user_text or "sop" in user_text or "how do i" in user_text or "history" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_search", "search_history", {"query": user_text, "limit": 3})],
                prompt_tokens=170,
                completion_tokens=25,
            )
        elif "postmortem" in user_text:
            return LLMResponse(
                tool_calls=[LLMToolCall("call_pm", "generate_postmortem", {})],
                prompt_tokens=150,
                completion_tokens=25,
            )
        else:
            # Default to shortest_path for user_1
            return LLMResponse(
                tool_calls=[LLMToolCall("call_route", "shortest_path", {"source": "user_1"})],
                prompt_tokens=160,
                completion_tokens=25,
            )


def get_active_provider_name() -> str:
    """Detect configured provider: 'groq', 'openai', or 'offline'."""
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    llm_key = os.environ.get("LLM_API_KEY", "").strip()
    provider_pref = os.environ.get("LLM_PROVIDER", "").strip().lower()

    if groq_key or llm_key.startswith("gsk_") or provider_pref == "groq":
        return "groq"
    if llm_key:
        return "openai"
    return "offline"


def get_llm_provider(force_fake: bool = False, fake_steps: Optional[List[Any]] = None) -> Optional[BaseLLMProvider]:
    """Retrieve active LLM Provider based on env vars (Groq, OpenAI, or offline fake provider)."""
    if force_fake:
        return FakeLLMProvider(scripted_steps=fake_steps)

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    llm_key = os.environ.get("LLM_API_KEY", "").strip()
    provider_pref = os.environ.get("LLM_PROVIDER", "").strip().lower()

    api_key = groq_key or llm_key
    if not api_key:
        # Copilot features disabled when API key is not configured
        return None

    # Detect if target is Groq
    is_groq = bool(groq_key) or api_key.startswith("gsk_") or provider_pref == "groq"

    if is_groq:
        base_url = (
            os.environ.get("GROQ_BASE_URL", "").strip()
            or "https://api.groq.com/openai/v1"
        )
        groq_model = os.environ.get("GROQ_MODEL", "").strip()
        llm_model = os.environ.get("LLM_MODEL", "").strip()
        if groq_model:
            model = groq_model
        elif llm_model and not llm_model.startswith("gpt-"):
            model = llm_model
        else:
            model = "openai/gpt-oss-120b"
    else:
        base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()

    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=25,
    )
