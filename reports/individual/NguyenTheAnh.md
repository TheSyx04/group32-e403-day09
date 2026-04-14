# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Thế Anh  
**Vai trò trong nhóm:** MCP Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi đảm nhận vai trò **MCP Owner**, chịu trách nhiệm chính cho Sprint 3 — tích hợp MCP (Model Context Protocol) vào hệ thống multi-agent. Công việc cụ thể bao gồm thiết kế và implement MCP Server, MCP Client, và đảm bảo policy worker gọi tool thông qua MCP interface thay vì truy cập trực tiếp ChromaDB.

**Module/file tôi chịu trách nhiệm:**
- File chính: `mcp_server.py`
- File liên quan: `workers/policy_tool.py` (phần MCP integration), `graph.py` (phần MCP decision logging)
- Functions tôi implement: class `MCPClient` (với `call_tool()`, `list_tools()`, `get_call_log()`, `get_tools_called_names()`), cập nhật `_call_mcp_tool()` và `_get_mcp_client()` trong policy worker, thêm MCP decision logging trong supervisor

**Cách công việc của tôi kết nối với phần của thành viên khác:**

MCP Server cung cấp abstraction layer cho policy_tool_worker (Sprint 2). Khi policy worker cần tra cứu KB hoặc kiểm tra access permission, thay vì gọi ChromaDB trực tiếp, nó gọi qua `MCPClient.call_tool()`. Điều này giúp trace (Sprint 4) ghi được `mcp_tool_called` và `mcp_result` cho mỗi lần gọi tool. Supervisor (Sprint 1) cũng được cập nhật để log "chọn MCP" vs "không chọn MCP" vào `route_reason`.

**Bằng chứng:**

Trace file `run_20260414_162248_074375.json` cho query "Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp" ghi nhận 3 MCP calls: `search_kb`, `check_access_permission`, `get_ticket_info` — tất cả đều có đầy đủ `mcp_tool_called`, `mcp_result`, và `timestamp`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn implement MCP ở mức **Standard** — sử dụng class `MCPClient` trong Python (in-process mock) thay vì HTTP server thật.

**Lý do:**

Có 2 lựa chọn theo README: (1) Mock MCP class gọi qua function call (Standard — full credit), hoặc (2) MCP server thật dùng `mcp` library hoặc HTTP server (Advanced — bonus +2). Tôi chọn Standard vì trong bối cảnh lab 60 phút, ưu tiên đảm bảo **tất cả Definition of Done** đều pass hơn là chase bonus mà risking incomplete implementation. MCP class in-process cũng giúp tránh complexity về network, CORS, và port management khi các thành viên khác chạy pipeline trên máy họ.

**Trade-off đã chấp nhận:**

Không có bonus +2 từ HTTP server thật, nhưng đổi lại mọi thành viên chạy `python graph.py` đều hoạt động ngay mà không cần setup thêm server riêng. Class `MCPClient` vẫn giữ interface giống MCP thật (có `list_tools()`, `call_tool()`) nên nếu cần upgrade lên HTTP trong tương lai thì chỉ cần thay implementation bên trong `call_tool()`.

**Bằng chứng từ trace/code:**

```json
{
  "tool": "search_kb",
  "input": {"query": "refund policy flash sale", "top_k": 3},
  "output": {"chunks": "[...0 items...]", "sources": []},
  "timestamp": "2026-04-14T16:21:55.473047",
  "mcp_tool_called": "search_kb",
  "mcp_result": {"chunks": [...], "sources": [...], "total_found": 0}
}
```

Format output đúng chuẩn MCP tool call JSON mà README Sprint 3 yêu cầu.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Policy worker gọi `dispatch_tool()` trực tiếp từ `mcp_server.py` nhưng không ghi lại `mcp_tool_called` và `mcp_result` vào trace — vi phạm Definition of Done Sprint 3.

**Symptom (pipeline làm gì sai?):**

Trước khi sửa, `_call_mcp_tool()` trong `workers/policy_tool.py` import `dispatch_tool` từ `mcp_server` và gọi trực tiếp. Kết quả trả về chỉ có `tool`, `input`, `output`, `error`, `timestamp` — **thiếu** `mcp_tool_called` và `mcp_result` mà trace (Sprint 4) yêu cầu. Supervisor cũng không log rõ quyết định "chọn MCP vs không chọn MCP".

**Root cause (lỗi nằm ở đâu?):**

Lỗi nằm ở thiết kế ban đầu: `_call_mcp_tool()` chỉ wrap `dispatch_tool()` đơn giản, không bọc thêm metadata cho trace. Supervisor thiếu log entry cho non-MCP branches (retrieval, human_review).

**Cách sửa:**

1. Tạo class `MCPClient` với `call_tool()` tự động ghi `mcp_tool_called`, `mcp_result`, `timestamp` vào mỗi trace entry
2. Cập nhật `_call_mcp_tool()` trong policy worker để dùng `MCPClient.call_tool()` thay vì `dispatch_tool()` trực tiếp  
3. Thêm log "supervisor không chọn MCP" cho retrieval và human_review branches trong `graph.py`
4. Thêm field `mcp_decision` vào `worker_io_logs` của supervisor

**Bằng chứng trước/sau:**

Trước: `state["mcp_tools_used"]` chứa entries không có `mcp_tool_called` key.

Sau: Mỗi entry trong `state["mcp_tools_used"]` đều có đầy đủ:
```
mcp_tool_called: search_kb
mcp_result keys: ['chunks', 'sources', 'total_found']
timestamp: 2026-04-14T16:22:48.074375
error: None
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi hoàn thành đúng và đủ **tất cả 4 Definition of Done** của Sprint 3: (1) `mcp_server.py` có 4 tools implement (vượt yêu cầu tối thiểu 2), (2) policy worker gọi MCP client không direct call ChromaDB, (3) trace ghi `mcp_tool_called` cho từng lần gọi, (4) supervisor ghi log "chọn MCP vs không chọn MCP". Tôi cũng đảm bảo backward compatibility — code mới không break pipeline của các sprint khác.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa implement mức Advanced (HTTP server thật hoặc `mcp` library) để lấy bonus +2. Nếu quản lý thời gian tốt hơn, có thể đã thử FastAPI wrapper.

**Nhóm phụ thuộc vào tôi ở đâu?**

Policy worker (`workers/policy_tool.py`) phụ thuộc vào MCP interface. Nếu `mcp_server.py` chưa xong, policy worker không thể gọi `search_kb` hay `check_access_permission`, và trace không ghi được MCP calls.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần retrieval worker (`workers/retrieval.py`) hoạt động đúng vì `tool_search_kb` trong MCP server delegate sang `retrieve_dense()`. Tôi cũng cần supervisor routing logic (Sprint 1) để set `needs_tool=True` cho policy path.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ upgrade MCP Server lên **HTTP server thật dùng FastAPI** để lấy bonus +2. Cụ thể: wrap 4 tools hiện có thành REST endpoints (`POST /tools/call`, `GET /tools/list`), và thay `MCPClient.call_tool()` bằng `httpx.post()`. Lý do: trace của query "Cần cấp quyền Level 3" cho thấy 3 MCP calls liên tiếp hoàn thành trong ~5ms mỗi call (in-process) — với HTTP sẽ có thêm network latency nhưng đổi lại được isolation thật giữa MCP server và agent, giống production environment hơn.

---

*File: `reports/individual/NguyenTheAnh.md`*
