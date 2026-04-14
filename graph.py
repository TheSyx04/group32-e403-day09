"""
graph.py — Supervisor Orchestrator
Sprint 1: Implement AgentState, supervisor_node, route_decision và kết nối graph.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py
"""

import json
import os
import sys
import unicodedata
from datetime import datetime
from typing import Literal, Optional, TypedDict

from workers.policy_tool import run as policy_tool_run
from workers.retrieval import run as retrieval_run
from workers.synthesis import run as synthesis_run


VALID_ROUTES = ("retrieval_worker", "policy_tool_worker", "human_review")


class AgentState(TypedDict):
    # Input
    task: str

    # Supervisor decisions
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool

    # Worker outputs
    retrieved_chunks: list
    retrieved_sources: list
    policy_result: dict
    mcp_tools_used: list

    # Final output
    final_answer: str
    sources: list
    confidence: float

    # Trace & history
    history: list
    worker_io_logs: list
    workers_called: list
    supervisor_route: str
    latency_ms: Optional[int]
    run_id: str


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "worker_io_logs": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
    }


def _append_history(state: AgentState, message: str) -> None:
    state["history"].append(message)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_for_routing(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_like = ascii_like.lower()
    replacements = {
        "—": " ",
        "–": " ",
        "_": " ",
        "/": " ",
        "\\": " ",
        ":": " ",
        ";": " ",
        ",": " ",
        ".": " ",
        "?": " ",
        "!": " ",
        "(": " ",
        ")": " ",
        "-": " ",
    }
    for old, new in replacements.items():
        ascii_like = ascii_like.replace(old, new)
    return " ".join(ascii_like.split())


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task và quyết định:
    1. Route sang worker nào
    2. Có cần MCP tool không
    3. Có risk cao cần HITL không
    """
    task = state["task"].strip()
    task_lower = task.lower()
    task_normalized = _normalize_for_routing(task)
    _append_history(state, f"[supervisor] received task: {task[:120]}")

    policy_keywords = [
        "hoan tien",
        "refund",
        "flash sale",
        "license",
        "subscription",
        "cap quyen",
        "access",
        "access level",
        "level 2",
        "level 3",
        "level 4",
        "admin access",
        "contractor",
    ]
    retrieval_keywords = [
        "p1",
        "sla",
        "ticket",
        "escalation",
        "su co",
        "incident",
        "helpdesk",
        "quy trinh",
    ]
    high_risk_keywords = [
        "khan cap",
        "emergency",
        "2am",
        "2 am",
        "active",
        "prod",
        "production",
    ]

    route: Literal["retrieval_worker", "policy_tool_worker", "human_review"] = "retrieval_worker"
    route_reason_parts: list[str] = []

    access_context = _contains_any(
        task_normalized,
        ["access", "cap quyen", "level 2", "level 3", "level 4", "admin access", "contractor"],
    )
    ticket_context = _contains_any(task_normalized, ["p1", "ticket", "sla", "incident", "su co"])
    unknown_error = "err-" in task_lower or "err " in task_normalized
    needs_tool = False
    risk_high = _contains_any(task_normalized, high_risk_keywords)

    # Fallback heuristic để không phụ thuộc hoàn toàn vào dấu tiếng Việt khi input bị lỗi encoding.
    if not risk_high and access_context and ticket_context:
        risk_high = True

    if unknown_error:
        route = "human_review"
        risk_high = True
        route_reason_parts.append("task contains unknown error code pattern ERR-* without supporting context")
    elif _contains_any(task_normalized, policy_keywords):
        route = "policy_tool_worker"
        route_reason_parts.append("task contains refund/access/policy keywords")
        needs_tool = True
        route_reason_parts.append("task follows policy/tool path and may require tool-backed lookup")
    elif _contains_any(task_normalized, retrieval_keywords):
        route = "retrieval_worker"
        route_reason_parts.append("task contains SLA/ticket/escalation retrieval keywords")
    else:
        route_reason_parts.append("task does not match policy or error patterns -> default retrieval path")

    if risk_high:
        if access_context and ticket_context:
            route_reason_parts.append("risk_high=True because task combines access-control request with P1/ticket context")
        else:
            route_reason_parts.append("risk_high=True because task mentions urgent or production-impact context")

    route_reason = " | ".join(route_reason_parts)

    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["worker_io_logs"].append(
        {
            "worker": "supervisor",
            "input": {"task": task},
            "output": {
                "supervisor_route": route,
                "route_reason": route_reason,
                "risk_high": risk_high,
                "needs_tool": needs_tool,
            },
            "error": None,
        }
    )
    _append_history(
        state,
        f"[supervisor] route={route} risk_high={risk_high} needs_tool={needs_tool} reason={route_reason}",
    )
    return state


def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Trả về tên worker tiếp theo dựa vào supervisor_route trong state.
    Đây là conditional edge của graph.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    if route not in VALID_ROUTES:
        state["supervisor_route"] = "retrieval_worker"
        state["route_reason"] = (
            f"{state.get('route_reason', '')} | invalid supervisor_route detected -> fallback retrieval_worker"
        ).strip(" |")
        route = "retrieval_worker"
        _append_history(state, "[route_decision] invalid route detected, fallback to retrieval_worker")
    else:
        _append_history(state, f"[route_decision] next_node={route}")
    return route  # type: ignore[return-value]


def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: pause và chờ human approval.
    Trong Sprint 1, node này là placeholder để trace thể hiện rõ rằng flow
    đã đi qua human review trước khi quay lại retrieval.
    """
    state["hitl_triggered"] = True
    state["workers_called"].append("human_review")
    state["worker_io_logs"].append(
        {
            "worker": "human_review",
            "input": {
                "task": state["task"],
                "supervisor_route": state["supervisor_route"],
                "route_reason": state["route_reason"],
            },
            "output": {"approved": True, "reroute_to": "retrieval_worker"},
            "error": None,
        }
    )
    _append_history(state, "[human_review] HITL triggered - placeholder approval granted")

    print("\nHITL TRIGGERED")
    print(f"  Task   : {state['task']}")
    print(f"  Reason : {state['route_reason']}")
    print("  Action : Auto-approve in Sprint 1 placeholder mode\n")

    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human_review approved fallback to retrieval_worker"
    return state


def retrieval_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi retrieval worker thật (Sprint 2)."""
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi policy/tool worker thật (Sprint 2)."""
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker thật (Sprint 2)."""
    return synthesis_run(state)


def build_graph():
    """
    Xây dựng graph với supervisor-worker pattern.
    Sprint 1 dùng orchestrator Python thuần để ưu tiên rõ flow và trace.
    """

    def run(state: AgentState) -> AgentState:
        import time

        start = time.time()
        _append_history(state, "[graph] run started")

        state = supervisor_node(state)
        route = route_decision(state)

        if route == "human_review":
            state = human_review_node(state)
            state = retrieval_worker_node(state)
        elif route == "policy_tool_worker":
            state = policy_tool_worker_node(state)
            if not state["retrieved_chunks"]:
                state = retrieval_worker_node(state)
        else:
            state = retrieval_worker_node(state)

        state = synthesis_worker_node(state)

        state["latency_ms"] = max(1, int((time.time() - start) * 1000))
        _append_history(state, f"[graph] completed in {state['latency_ms']}ms")
        return state

    return run


_graph = build_graph()


def run_graph(task: str) -> AgentState:
    """Entry point: nhận câu hỏi, trả về AgentState với full trace."""
    state = make_initial_state(task)
    return _graph(state)


def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph")
    print("=" * 60)

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?",
        "ERR-403-AUTH là lỗi gì và cách xử lý?",
    ]

    for query in test_queries:
        print(f"\n> Query: {query}")
        result = run_graph(query)
        print(f"  Route      : {result['supervisor_route']}")
        print(f"  Reason     : {result['route_reason']}")
        print(f"  Needs tool : {result['needs_tool']}")
        print(f"  Risk high  : {result['risk_high']}")
        print(f"  Workers    : {result['workers_called']}")
        print(f"  Answer     : {result['final_answer'][:110]}...")
        print(f"  Confidence : {result['confidence']}")
        print(f"  Latency    : {result['latency_ms']}ms")

        trace_file = save_trace(result)
        print(f"  Trace saved -> {trace_file}")

    print("\nGraph test complete (Sprint 2 integration mode).")
