"""Number grounding verification for NetPilot responses.

Verifies that every numeric claim in the model's generated explanation is strictly
grounded in the output of the executed tools. If an ungrounded number is detected,
flags the response to protect against model hallucinations.
"""

import re
from typing import Dict, List, Set, Any, Tuple, Optional


NUMBER_REGEX = re.compile(r"(?<![a-zA-Z0-9_])[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?(?![a-zA-Z0-9_])")


def extract_numbers_from_text(text: str) -> List[float]:
    """Extract standalone numeric tokens from text."""
    matches = NUMBER_REGEX.findall(text)
    numbers = []
    for m in matches:
        # Filter out empty or lone decimal dots
        if m in ("", ".", "-", "+"):
            continue
        try:
            val = float(m)
            numbers.append(val)
        except ValueError:
            pass
    return numbers


def extract_numbers_from_tool_results(tool_results: Any) -> Set[float]:
    """Recursively harvest all numeric values from structured tool outputs."""
    found: Set[float] = set()

    def _walk(item: Any):
        if isinstance(item, (int, float)):
            found.add(float(item))
        elif isinstance(item, dict):
            for k, v in item.items():
                _walk(v)
        elif isinstance(item, (list, tuple, set)):
            for elem in item:
                _walk(elem)
        elif isinstance(item, str):
            # Check if string contains numeric representation
            for num in extract_numbers_from_text(item):
                found.add(num)

    _walk(tool_results)
    return found


def verify_number_grounding(
    answer_text: str,
    tool_results: List[Dict[str, Any]],
    tolerance: float = 1e-2,
) -> Tuple[bool, List[float], str]:
    """Verify that all numbers in answer_text match numbers present in tool_results.

    Returns:
        (is_grounded, ungrounded_numbers_list, flagged_or_original_text)
    """
    answer_numbers = extract_numbers_from_text(answer_text)
    tool_numbers = extract_numbers_from_tool_results(tool_results)

    ungrounded: List[float] = []

    for num in answer_numbers:
        # Check if number matches any tool number within tolerance
        matched = False
        for t_num in tool_numbers:
            if abs(num - t_num) <= tolerance or (t_num != 0 and abs((num - t_num) / t_num) <= tolerance):
                matched = True
                break

        if not matched:
            ungrounded.append(num)

    if ungrounded:
        flag_note = (
            f"\n\n> ⚠️ **Verification Notice**: Ungrounded numbers detected not present in tool results: "
            f"`{ungrounded}`. Always inspect tool output."
        )
        return False, ungrounded, answer_text + flag_note
    else:
        return True, [], answer_text


def verify_event_id_grounding(
    answer_text: str,
    event_store_instance: Optional[Any] = None,
) -> Tuple[bool, List[str], str]:
    """Verify that any cited event ID in answer_text actually exists in the event store.

    Returns:
        (is_grounded, invalid_event_ids_list, flagged_or_original_text)
    """
    from storage.event_store import get_event_store
    es = event_store_instance or get_event_store()

    # Search for patterns: 'Event #evt_123', 'Event #12', 'event evt_abc', 'Event ID evt_123'
    pattern = re.compile(r"(?:event\s*(?:#|id\s*)?|#\s*)(evt_[a-zA-Z0-9_]+|\d+)", re.IGNORECASE)
    matches = pattern.findall(answer_text)

    if not matches:
        return True, [], answer_text

    invalid: List[str] = []
    for cid in matches:
        cid_clean = cid.strip()
        ev = es.get_event(cid_clean)
        if not ev and not cid_clean.startswith("evt_"):
            ev = es.get_event(f"evt_{cid_clean}")
        if not ev:
            # Check list of recent events for substring or id match
            try:
                recent = es.list_events(limit=50)
                if not any(e.id == cid_clean or cid_clean in e.id for e in recent):
                    invalid.append(cid_clean)
            except Exception:
                invalid.append(cid_clean)

    if invalid:
        flag_note = (
            f"\n\n> ⚠️ **Verification Notice**: Cited event ID(s) `{invalid}` do not exist in the event store."
        )
        return False, invalid, answer_text + flag_note

    return True, [], answer_text

