"""
mcp_server.py — Mock MCP Server (Sprint 3 Complete)

Mô phỏng MCP (Model Context Protocol) interface trong Python.
Agent (MCP client) gọi dispatch_tool() hoặc dùng MCPClient class thay vì hard-code từng API.

Tools available:
    1. search_kb(query, top_k)           → tìm kiếm Knowledge Base
    2. get_ticket_info(ticket_id)        → tra cứu thông tin ticket (mock data)
    3. check_access_permission(level, requester_role)  → kiểm tra quyền truy cập
    4. create_ticket(priority, title, description)     → tạo ticket mới (mock)

Sử dụng (Functional):
    from mcp_server import dispatch_tool, list_tools

    tools = list_tools()
    result = dispatch_tool("search_kb", {"query": "SLA P1", "top_k": 3})

Sử dụng (OOP — MCPClient):
    from mcp_server import MCPClient

    client = MCPClient()
    tools = client.list_tools()
    result = client.call_tool("search_kb", {"query": "SLA P1", "top_k": 3})
    # result chứa: tool, input, output, timestamp, mcp_tool_called, mcp_result

    # Xem lịch sử call
    print(client.get_call_log())

Chạy thử:
    python mcp_server.py
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────
# Tool Definitions (Schema Discovery)
# Giống với cách MCP server expose tool list cho client
# ─────────────────────────────────────────────

TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tìm kiếm Knowledge Base nội bộ bằng semantic search. Trả về top-k chunks liên quan nhất.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Câu hỏi hoặc keyword cần tìm"},
                "top_k": {"type": "integer", "description": "Số chunks cần trả về", "default": 3},
            },
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "sources": {"type": "array"},
                "total_found": {"type": "integer"},
            },
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cứu thông tin ticket từ hệ thống Jira nội bộ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "ID ticket (VD: IT-1234, P1-LATEST)"},
            },
            "required": ["ticket_id"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string"},
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "created_at": {"type": "string"},
                "sla_deadline": {"type": "string"},
            },
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Kiểm tra điều kiện cấp quyền truy cập theo Access Control SOP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer", "description": "Level cần cấp (1, 2, hoặc 3)"},
                "requester_role": {"type": "string", "description": "Vai trò của người yêu cầu"},
                "is_emergency": {"type": "boolean", "description": "Có phải khẩn cấp không", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "can_grant": {"type": "boolean"},
                "required_approvers": {"type": "array"},
                "emergency_override": {"type": "boolean"},
                "source": {"type": "string"},
            },
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tạo ticket mới trong hệ thống Jira (MOCK — không tạo thật trong lab).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "url": {"type": "string"},
                "created_at": {"type": "string"},
            },
        },
    },
}


# ─────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────

def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """
    Tìm kiếm Knowledge Base bằng semantic search.
    Kết nối với ChromaDB thông qua retrieval worker.
    """
    try:
        # Tái dùng retrieval logic từ workers/retrieval.py
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from workers.retrieval import retrieve_dense
        chunks = retrieve_dense(query, top_k=top_k)
        sources = list({c["source"] for c in chunks})
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as e:
        # Fallback: return mock data nếu ChromaDB chưa setup
        return {
            "chunks": [
                {
                    "text": f"[MOCK] Không thể query ChromaDB: {e}. Kết quả giả lập.",
                    "source": "mock_data",
                    "score": 0.5,
                }
            ],
            "sources": ["mock_data"],
            "total_found": 1,
        }


# Mock ticket database
MOCK_TICKETS = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "title": "API Gateway down — toàn bộ người dùng không đăng nhập được",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",
        "escalated": True,
        "escalated_to": "senior_engineer_team",
        "notifications_sent": ["slack:#incident-p1", "email:incident@company.internal", "pagerduty:oncall"],
    },
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "title": "Feature login chậm cho một số user",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
        "sla_deadline": "2026-04-14T09:15:00",
        "escalated": False,
    },
}


def tool_get_ticket_info(ticket_id: str) -> dict:
    """
    Tra cứu thông tin ticket (mock data).
    """
    ticket = MOCK_TICKETS.get(ticket_id.upper())
    if ticket:
        return ticket
    # Không tìm thấy
    return {
        "error": f"Ticket '{ticket_id}' không tìm thấy trong hệ thống.",
        "available_mock_ids": list(MOCK_TICKETS.keys()),
    }


# Mock access control rules
ACCESS_RULES = {
    1: {
        "required_approvers": ["Line Manager"],
        "emergency_can_bypass": False,
        "note": "Standard user access",
    },
    2: {
        "required_approvers": ["Line Manager", "IT Admin"],
        "emergency_can_bypass": True,
        "emergency_bypass_note": "Level 2 có thể cấp tạm thời với approval đồng thời của Line Manager và IT Admin on-call.",
        "note": "Elevated access",
    },
    3: {
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "emergency_can_bypass": False,
        "note": "Admin access — không có emergency bypass",
    },
}


def tool_check_access_permission(access_level: int, requester_role: str, is_emergency: bool = False) -> dict:
    """
    Kiểm tra điều kiện cấp quyền theo Access Control SOP.
    """
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {"error": f"Access level {access_level} không hợp lệ. Levels: 1, 2, 3."}

    can_grant = True
    notes = []

    if is_emergency and rule.get("emergency_can_bypass"):
        notes.append(rule.get("emergency_bypass_note", ""))
        can_grant = True
    elif is_emergency and not rule.get("emergency_can_bypass"):
        notes.append(f"Level {access_level} KHÔNG có emergency bypass. Phải follow quy trình chuẩn.")

    return {
        "access_level": access_level,
        "can_grant": can_grant,
        "required_approvers": rule["required_approvers"],
        "approver_count": len(rule["required_approvers"]),
        "emergency_override": is_emergency and rule.get("emergency_can_bypass", False),
        "notes": notes,
        "source": "access_control_sop.txt",
    }


def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    """
    Tạo ticket mới (MOCK — in log, không tạo thật).
    """
    mock_id = f"IT-{9900 + hash(title) % 99}"
    ticket = {
        "ticket_id": mock_id,
        "priority": priority,
        "title": title,
        "description": description[:200],
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "url": f"https://jira.company.internal/browse/{mock_id}",
        "note": "MOCK ticket — không tồn tại trong hệ thống thật",
    }
    print(f"  [MCP create_ticket] MOCK: {mock_id} | {priority} | {title[:50]}")
    return ticket


# ─────────────────────────────────────────────
# Dispatch Layer — MCP server interface (Functional)
# ─────────────────────────────────────────────

TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
}


def list_tools() -> list:
    """
    MCP discovery: trả về danh sách tools có sẵn.
    Tương đương với `tools/list` trong MCP protocol.
    """
    return list(TOOL_SCHEMAS.values())


def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """
    MCP execution: nhận tool_name và input, gọi tool tương ứng.
    Tương đương với `tools/call` trong MCP protocol.

    Args:
        tool_name: tên tool (phải có trong TOOL_REGISTRY)
        tool_input: input dict (phải match với tool's inputSchema)

    Returns:
        Tool output dict, hoặc error dict nếu thất bại
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' không tồn tại. Available: {list(TOOL_REGISTRY.keys())}"
        }

    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        result = tool_fn(**tool_input)
        return result
    except TypeError as e:
        return {
            "error": f"Invalid input for tool '{tool_name}': {e}",
            "schema": TOOL_SCHEMAS[tool_name]["inputSchema"],
        }
    except Exception as e:
        return {
            "error": f"Tool '{tool_name}' execution failed: {e}",
        }


# ─────────────────────────────────────────────
# MCPClient Class — Sprint 3: OOP wrapper with tracing
# Policy worker gọi MCPClient thay vì trực tiếp dispatch_tool
# ─────────────────────────────────────────────

class MCPClient:
    """
    MCP Client giả lập — gọi MCP Server (in-process mock).

    Cung cấp:
    - list_tools(): discover available tools
    - call_tool(tool_name, tool_input): gọi tool, trả về trace-ready dict
    - get_call_log(): trả về lịch sử tất cả tool calls

    Mỗi lần call_tool() tự động ghi lại:
    - mcp_tool_called: tên tool đã gọi
    - mcp_result: kết quả trả về
    - timestamp: thời điểm gọi
    - Format theo chuẩn MCP tool call JSON (README Sprint 3)
    """

    def __init__(self):
        self._call_log: List[dict] = []

    def list_tools(self) -> list:
        """Discover available MCP tools (tương đương tools/list)."""
        return list_tools()

    def call_tool(self, tool_name: str, tool_input: dict) -> dict:
        """
        Gọi MCP tool và trả về kết quả với đầy đủ trace metadata.

        Args:
            tool_name: tên tool cần gọi
            tool_input: input params cho tool

        Returns:
            dict theo format MCP tool call:
            {
                "tool": "search_kb",
                "input": {"query": "...", "top_k": 3},
                "output": {"chunks": [...], "sources": [...]},
                "timestamp": "2026-04-13T14:32:11",
                "mcp_tool_called": "search_kb",
                "mcp_result": {...},
                "error": None
            }
        """
        timestamp = datetime.now().isoformat()

        try:
            result = dispatch_tool(tool_name, tool_input)
            has_error = "error" in result and result["error"] is not None

            trace_entry = {
                "tool": tool_name,
                "input": tool_input,
                "output": result,
                "timestamp": timestamp,
                "mcp_tool_called": tool_name,
                "mcp_result": result,
                "error": result.get("error") if has_error else None,
            }
        except Exception as e:
            trace_entry = {
                "tool": tool_name,
                "input": tool_input,
                "output": None,
                "timestamp": timestamp,
                "mcp_tool_called": tool_name,
                "mcp_result": None,
                "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            }

        self._call_log.append(trace_entry)
        print(f"  [MCPClient] called '{tool_name}' at {timestamp}")
        return trace_entry

    def get_call_log(self) -> List[dict]:
        """Trả về lịch sử tất cả MCP tool calls đã thực hiện."""
        return list(self._call_log)

    def get_tools_called_names(self) -> List[str]:
        """Trả về danh sách tên các tools đã gọi (dùng cho trace)."""
        return [entry["mcp_tool_called"] for entry in self._call_log]

    def reset_log(self):
        """Xóa lịch sử call log (dùng giữa các run)."""
        self._call_log.clear()


# ─────────────────────────────────────────────
# Test & Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print("MCP Server — Tool Discovery & Test (Sprint 3)")
    print("=" * 60)

    # ---- Test 1: Functional API (dispatch_tool) ----
    print("\n" + "-" * 40)
    print("Part A: Functional API (dispatch_tool)")
    print("-" * 40)

    # 1. Discover tools
    print("\n📋 Available Tools:")
    for tool in list_tools():
        print(f"  • {tool['name']}: {tool['description'][:60]}...")

    # 2. Test search_kb
    print("\n🔍 Test: search_kb")
    result = dispatch_tool("search_kb", {"query": "SLA P1 resolution time", "top_k": 2})
    if result.get("chunks"):
        for c in result["chunks"]:
            print(f"  [{c.get('score', '?')}] {c.get('source')}: {c.get('text', '')[:70]}...")
    else:
        print(f"  Result: {result}")

    # 3. Test get_ticket_info
    print("\n🎫 Test: get_ticket_info")
    ticket = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
    print(f"  Ticket: {ticket.get('ticket_id')} | {ticket.get('priority')} | {ticket.get('status')}")
    if ticket.get("notifications_sent"):
        print(f"  Notifications: {ticket['notifications_sent']}")

    # 4. Test check_access_permission
    print("\n🔐 Test: check_access_permission (Level 3, emergency)")
    perm = dispatch_tool("check_access_permission", {
        "access_level": 3,
        "requester_role": "contractor",
        "is_emergency": True,
    })
    print(f"  can_grant: {perm.get('can_grant')}")
    print(f"  required_approvers: {perm.get('required_approvers')}")
    print(f"  emergency_override: {perm.get('emergency_override')}")
    print(f"  notes: {perm.get('notes')}")

    # 5. Test invalid tool
    print("\n❌ Test: invalid tool")
    err = dispatch_tool("nonexistent_tool", {})
    print(f"  Error: {err.get('error')}")

    # ---- Test 2: MCPClient class (OOP with tracing) ----
    print("\n" + "-" * 40)
    print("Part B: MCPClient Class (OOP with tracing)")
    print("-" * 40)

    client = MCPClient()

    # List tools via client
    print("\n📋 MCPClient.list_tools():")
    for tool in client.list_tools():
        print(f"  • {tool['name']}")

    # Call search_kb via client
    print("\n🔍 MCPClient.call_tool('search_kb', ...)")
    trace1 = client.call_tool("search_kb", {"query": "refund policy flash sale", "top_k": 3})
    print(f"  mcp_tool_called: {trace1['mcp_tool_called']}")
    print(f"  timestamp: {trace1['timestamp']}")
    print(f"  output total_found: {trace1['output'].get('total_found', 'N/A')}")
    print(f"  error: {trace1['error']}")

    # Call get_ticket_info via client
    print("\n🎫 MCPClient.call_tool('get_ticket_info', ...)")
    trace2 = client.call_tool("get_ticket_info", {"ticket_id": "IT-1234"})
    print(f"  mcp_tool_called: {trace2['mcp_tool_called']}")
    print(f"  ticket_id: {trace2['output'].get('ticket_id', 'N/A')}")
    print(f"  priority: {trace2['output'].get('priority', 'N/A')}")

    # Call check_access_permission via client
    print("\n🔐 MCPClient.call_tool('check_access_permission', ...)")
    trace3 = client.call_tool("check_access_permission", {
        "access_level": 2,
        "requester_role": "contractor",
        "is_emergency": True,
    })
    print(f"  mcp_tool_called: {trace3['mcp_tool_called']}")
    print(f"  can_grant: {trace3['output'].get('can_grant')}")
    print(f"  emergency_override: {trace3['output'].get('emergency_override')}")

    # Show call log
    print("\n📊 MCPClient.get_call_log() — full trace:")
    for i, entry in enumerate(client.get_call_log(), 1):
        print(f"  [{i}] tool={entry['tool']}, timestamp={entry['timestamp']}, error={entry['error']}")

    print(f"\n  Tools called: {client.get_tools_called_names()}")

    # Show MCP tool call format (as per README Sprint 3)
    print("\n📄 Example MCP tool call JSON (per README format):")
    example_trace = client.get_call_log()[0]
    formatted = {
        "tool": example_trace["tool"],
        "input": example_trace["input"],
        "output": {
            "chunks": f"[...{example_trace['output'].get('total_found', 0)} items...]",
            "sources": example_trace["output"].get("sources", []),
        },
        "timestamp": example_trace["timestamp"],
    }
    print(json.dumps(formatted, indent=2, ensure_ascii=False))

    print("\n✅ MCP server Sprint 3 test done.")
    print("   ✓ 4 tools implemented (search_kb, get_ticket_info, check_access_permission, create_ticket)")
    print("   ✓ MCPClient class with tracing (mcp_tool_called, mcp_result, timestamp)")
    print("   ✓ Call log for observability")
