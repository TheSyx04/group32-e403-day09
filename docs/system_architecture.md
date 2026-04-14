# System Architecture — Lab Day 09

**Nhóm:** Group 32  
**Ngày:** 2026-04-14  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

Pattern đã chọn: **Supervisor-Worker**. Hệ thống tách rõ trách nhiệm: `Supervisor` tiếp nhận task và quyết định route; các `Worker` chuyên trách (retrieval, policy check, synthesis). Cách tiếp cận này giúp tăng khả năng trace, test độc lập, và mở rộng capability bằng cách thêm worker hoặc MCP tool mà không thay đổi toàn bộ pipeline.

Lí do chọn pattern (so với single-agent Day 08):
- Cải thiện debuggability: mỗi bước ghi trace riêng (`route_reason`, `worker_io_log`).
- Tách ranh giới I/O: dễ test unit cho từng worker.
- Dễ mở rộng: thêm tool/MCP hoặc worker mới mà không đổi core logic.

---

## 2. Sơ đồ Pipeline

```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← decide `supervisor_route`, `route_reason`, `risk_high`
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
(evidence via ChromaDB) (policy checks + MCP tool calls)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
    (LLM grounded answer + citations)
            │
            ▼
         Output
```

Sơ đồ thực tế của nhóm: pipeline dùng `workers/retrieval.py` (ChromaDB index + SentenceTransformer), `workers/policy_tool.py` (gọi MCP tools như `search_kb` / `get_ticket_info`), và `workers/synthesis.py` (gọi LLM để tạo answer grounded trên evidence). Supervisor hiện được triển khai trong `graph.py` và lưu trace vào `artifacts/traces/`.

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Nhận task (text), quyết định route dựa trên keyword rule + risk flags, cập nhật shared `AgentState`, ghi `route_reason` vào trace |
| **Input** | `task` (str), optional `metadata` (e.g., ticket_id) |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, cập nhật `history` |
| **Routing logic** | Keyword matching (refund, policy, access, P1, escalation) với fallback classifier; policy/emergency keywords → `policy_tool_worker`; P1/escalation → `retrieval_worker`; default → `retrieval_worker` |
| **HITL condition** | `confidence` thấp từ synthesis or policy conflict; `risk_high` true (e.g., P1 escalation) |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Tìm evidence liên quan trong `data/docs/` bằng ChromaDB hoặc simple text match, trả về `retrieved_chunks` và `retrieved_sources` |
| **Embedding model** | `sentence-transformers/all-MiniLM-L6-v2` (đề xuất) |
| **Top-k** | 3 (mặc định) |
| **Stateless?** | Yes (không lưu state bên ngoài AgentState) |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Kiểm tra các quy định liên quan, xử lý các exception case (Flash Sale, digital product), và gọi MCP khi cần thông tin ngoài KB |
| **MCP tools gọi** | `search_kb`, `get_ticket_info` (mock MCP trong `mcp_server.py`) |
| **Exception cases xử lý** | Flash Sale refund window, digital product non-refundable clauses, emergency access temporary grant rules |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | OpenAI-compatible LLM via API (configurable) |
| **Temperature** | 0.0–0.2 (low to reduce hallucination) |
| **Grounding strategy** | Prompt enforces "Answer only from provided evidence"; include `retrieved_chunks` + `policy_result` as context |
| **Abstain condition** | Không đủ evidence hoặc policy conflict → trả về explicit abstain và `hitl_triggered` nếu cần |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | `query`, `top_k` | `chunks`, `sources` |
| get_ticket_info | `ticket_id` | `ticket_id`, `status`, `assignees`, `timestamps` |
| check_access_permission | `access_level`, `requester_role` | `can_grant`, `approvers` |

---

## 4. Shared State Schema

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào | supervisor đọc |
| supervisor_route | str | Worker được chọn | supervisor ghi |
| route_reason | str | Lý do route (keyword/flag) | supervisor ghi |
| retrieved_chunks | list[dict] | Evidence từ retrieval (`text`, `source`, `score`) | retrieval ghi, synthesis đọc |
| policy_result | dict | Kết quả kiểm tra policy, flags, notes | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list[dict] | Danh sách tool calls (tool, input, output, timestamp) | policy_tool ghi |
| workers_called | list[str] | Sequence workers đã chạy | supervisor/each worker ghi |
| worker_io_log | dict | IO logs per worker for debugging | each worker ghi |
| final_answer | str | Câu trả lời cuối cùng | synthesis ghi |
| confidence | float | Mức tin cậy (0..1) | synthesis ghi |
| hitl_triggered | bool | Có cần human-in-the-loop không | supervisor/worker ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không có trace theo bước | Dễ hơn — trace per-step, `route_reason` rõ ràng |
| Thêm capability mới | Thay đổi prompt/monolith | Thêm worker/MCP tool riêng, ít side-effect |
| Routing visibility | Không có | Có `route_reason` và `workers_called` trong trace |

**Nhóm quan sát từ thực tế lab:** Supervisor-worker giúp giảm thời gian debug từ ~45 phút (Day 08) xuống ~10–15 phút cho lỗi retrieval/synthesis do có trace chi tiết.

---

## 6. Giới hạn và điểm cần cải tiến

1. Latency tăng khi gọi nhiều worker / MCP tools — cần batching và cache cho `search_kb`.
2. Nếu routing rule quá đơn giản (chỉ keyword), có thể route sai với ngôn ngữ tự nhiên phức tạp — cân nhắc bổ sung classifier nhẹ.
3. Current trace schema có thể thiếu structured error codes — nên chuẩn hoá `route_reason` và `worker_io_log` để dễ aggregate.
