"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện (với mcp_tool_called & mcp_result)
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import os
import sys
from typing import Optional

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client — Sprint 3: Dùng MCPClient class thay vì direct call
# Policy worker gọi MCP client, KHÔNG direct call ChromaDB
# ─────────────────────────────────────────────

def _get_mcp_client():
    """
    Tạo MCPClient instance.
    Sprint 3: Import từ mcp_server.py (in-process mock MCP server).
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from mcp_server import MCPClient
    return MCPClient()


def _call_mcp_tool(mcp_client, tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool thông qua MCPClient.

    Sprint 3: Sử dụng MCPClient.call_tool() thay vì dispatch_tool trực tiếp.
    Kết quả trả về đã có đầy đủ mcp_tool_called, mcp_result, timestamp.
    """
    return mcp_client.call_tool(tool_name, tool_input)


# ─────────────────────────────────────────────
# Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên context chunks.

    TODO Sprint 2: Implement logic này với LLM call hoặc rule-based check.

    Cần xử lý các exceptions:
    - Flash Sale → không được hoàn tiền
    - Digital product / license key / subscription → không được hoàn tiền
    - Sản phẩm đã kích hoạt → không được hoàn tiền
    - Đơn hàng trước 01/02/2026 → áp dụng policy v3 (không có trong docs)

    Returns:
        dict with: policy_applies, policy_name, exceptions_found, source, rule, explanation
    """
    task_lower = task.lower()
    context_text = " ".join([c.get("text", "") for c in chunks]).lower()

    # --- Rule-based exception detection ---
    exceptions_found = []

    # Exception 1: Flash Sale
    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 2: Digital product
    if any(kw in task_lower for kw in ["license key", "license", "subscription", "kỹ thuật số"]):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 3: Activated product
    if any(kw in task_lower for kw in ["đã kích hoạt", "đã đăng ký", "đã sử dụng"]):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Determine policy_applies
    policy_applies = len(exceptions_found) == 0

    # Determine which policy version applies (temporal scoping)
    # TODO: Check nếu đơn hàng trước 01/02/2026 → v3 applies (không có docs, nên flag cho synthesis)
    policy_name = "refund_policy_v4"
    policy_version_note = ""
    if "31/01" in task_lower or "30/01" in task_lower or "trước 01/02" in task_lower:
        policy_version_note = "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 (không có trong tài liệu hiện tại)."

    # TODO Sprint 2: Gọi LLM để phân tích phức tạp hơn
    # Ví dụ:
    # from openai import OpenAI
    # client = OpenAI()
    # response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[
    #         {"role": "system", "content": "Bạn là policy analyst. Dựa vào context, xác định policy áp dụng và các exceptions."},
    #         {"role": "user", "content": f"Task: {task}\n\nContext:\n" + "\n".join([c['text'] for c in chunks])}
    #     ]
    # )
    # analysis = response.choices[0].message.content

    sources = list({c.get("source", "unknown") for c in chunks if c})

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "explanation": "Analyzed via rule-based policy check. TODO: upgrade to LLM-based analysis.",
    }


def _extract_ticket_id(task: str) -> str:
    task_lower = task.lower()
    if "p1-latest" in task_lower:
        return "P1-LATEST"
    if "it-" in task_lower:
        words = task_lower.replace("/", " ").split()
        for word in words:
            if word.startswith("it-") or word.startswith("p1-"):
                return word.upper()
    return "P1-LATEST"


def _extract_access_request(task: str) -> dict:
    task_lower = task.lower()
    access_level = 3
    requester_role = "user"
    is_emergency = any(kw in task_lower for kw in ["khẩn cấp", "khan cap", "emergency", "2am", "2 am"])

    if "level 2" in task_lower or "level2" in task_lower:
        access_level = 2
    elif "level 3" in task_lower or "level3" in task_lower:
        access_level = 3
    elif "level 4" in task_lower or "level4" in task_lower:
        access_level = 4

    if "contractor" in task_lower or "nhân viên hợp đồng" in task_lower:
        requester_role = "contractor"
    elif "admin" in task_lower:
        requester_role = "admin"
    elif "user" in task_lower:
        requester_role = "user"

    return {
        "access_level": access_level,
        "requester_role": requester_role,
        "is_emergency": is_emergency,
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Sprint 3 changes:
    - Tạo MCPClient instance để gọi tools (không direct call ChromaDB)
    - Ghi mcp_tool_called và mcp_result vào trace cho mỗi lần gọi MCP
    - Tất cả KB lookup đều đi qua MCP search_kb, không gọi ChromaDB trực tiếp

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Sprint 3: Tạo MCPClient — mọi tool call đi qua MCP interface
        mcp_client = _get_mcp_client()

        # Step 1: Nếu chưa có chunks, gọi MCP search_kb (qua MCPClient, KHÔNG direct ChromaDB)
        if not chunks and needs_tool:
            mcp_trace = _call_mcp_tool(mcp_client, "search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_trace)
            state["history"].append(
                f"[{WORKER_NAME}] called MCP search_kb | "
                f"mcp_tool_called={mcp_trace['mcp_tool_called']} | "
                f"timestamp={mcp_trace['timestamp']}"
            )

            if mcp_trace.get("output") and mcp_trace["output"].get("chunks"):
                chunks = mcp_trace["output"]["chunks"]
                state["retrieved_chunks"] = chunks

        # Step 1b: Nếu task liên quan access/cấp quyền, gọi MCP access permission
        access_tools = ["access", "cấp quyền", "admin access", "level 2", "level 3", "level 4", "contractor"]
        if needs_tool and any(kw in task.lower() for kw in access_tools):
            access_input = _extract_access_request(task)
            mcp_trace = _call_mcp_tool(mcp_client, "check_access_permission", access_input)
            state["mcp_tools_used"].append(mcp_trace)
            state["history"].append(
                f"[{WORKER_NAME}] called MCP check_access_permission | "
                f"mcp_tool_called={mcp_trace['mcp_tool_called']} | "
                f"timestamp={mcp_trace['timestamp']}"
            )
            state.setdefault("policy_result", {})
            state["policy_result"]["access_check"] = mcp_trace.get("output") or mcp_trace

        # Step 1c: Nếu task liên quan ticket, gọi MCP get_ticket_info
        ticket_keywords = ["ticket", "p1", "jira"]
        if needs_tool and any(kw in task.lower() for kw in ticket_keywords):
            ticket_id = _extract_ticket_id(task)
            mcp_trace = _call_mcp_tool(mcp_client, "get_ticket_info", {"ticket_id": ticket_id})
            state["mcp_tools_used"].append(mcp_trace)
            state["history"].append(
                f"[{WORKER_NAME}] called MCP get_ticket_info | "
                f"mcp_tool_called={mcp_trace['mcp_tool_called']} | "
                f"timestamp={mcp_trace['timestamp']}"
            )
            state.setdefault("policy_result", {})
            state["policy_result"]["ticket_info"] = mcp_trace.get("output") or mcp_trace

        # Step 2: Phân tích policy
        policy_result = analyze_policy(task, chunks)
        if isinstance(state.get("policy_result"), dict):
            policy_result.update(state["policy_result"])
        state["policy_result"] = policy_result

        # Sprint 3: Ghi lại tổng hợp mcp_tool_called vào worker_io
        mcp_tools_called = [t.get("mcp_tool_called", "unknown") for t in state["mcp_tools_used"]]
        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state["mcp_tools_used"]),
            "mcp_tools_called": mcp_tools_called,
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}, "
            f"mcp_tools_called={mcp_tools_called}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 50)
    print("Policy Tool Worker — Standalone Test (Sprint 3)")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
            "needs_tool": True,
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
            "needs_tool": True,
        },
        {
            "task": "Cần cấp quyền Level 3 cho contractor để khắc phục P1 khẩn cấp.",
            "retrieved_chunks": [],
            "needs_tool": True,
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Task: {tc['task'][:70]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} — {ex['rule'][:60]}...")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")
        if result.get("mcp_tools_used"):
            for mcp_call in result["mcp_tools_used"]:
                print(f"    ↳ mcp_tool_called: {mcp_call['mcp_tool_called']}")
                print(f"      timestamp: {mcp_call['timestamp']}")
                print(f"      error: {mcp_call.get('error')}")

    print("\n✅ policy_tool_worker Sprint 3 test done.")
    print("   ✓ Policy worker gọi MCP client, không direct call ChromaDB")
    print("   ✓ Trace ghi mcp_tool_called cho từng lần gọi")
