# Routing Decisions Log — Lab Day 09

**Nhóm:** Group 32  
**Ngày:** 2026-04-14

> Dưới đây là 3 quyết định routing trích từ kết quả chạy thử nội bộ (trace samples). Khi chạy grading suite, thay các entry này bằng các dòng tương ứng trong `artifacts/traces/`.

---

## Routing Decision #1

**Task đầu vào:**
> "Ticket P1 được tạo lúc 22:47. Ai nhận thông báo đầu tiên và qua kênh nào?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `contains: P1, SLA, escalation`  
**MCP tools được gọi:** `search_kb`  
**Workers called sequence:** `supervisor -> retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): "Theo SLA P1, kênh thông báo đầu tiên là email ticketing; assignee là on-call team"  
- confidence: 0.88  
- Correct routing? Yes

**Nhận xét:**
Routing đúng vì task liên quan SLA/P1 nên ưu tiên retrieval để lấy văn bản SLA gốc; policy check không cần thiết ở bước này.

---

## Routing Decision #2

**Task đầu vào:**
> "Flash Sale + lỗi nhà sản xuất + 7 ngày — được hoàn tiền không?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `contains: flash sale | refund | exception`  
**MCP tools được gọi:** `search_kb`  
**Workers called sequence:** `supervisor -> policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): "Có thể refund nếu chứng minh lỗi nhà sản xuất và nằm trong 7 ngày theo policy refund_v4; nếu là Flash Sale có điều khoản giới hạn, trường hợp cần escalate"  
- confidence: 0.82  
- Correct routing? Yes

**Nhận xét:**
Policy worker trích các điều khoản ngoại lệ (flash sale, digital product) và trả về `policy_result` cho synthesis. Trace ghi rõ `mcp_tools_used` và `policy_result` giúp kiểm chứng đáp án.

---

## Routing Decision #3

**Task đầu vào:**
> "Level 3 access emergency — cần bao nhiêu approvers, ai là người cuối cùng?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `contains: access, emergency, approver`  
**MCP tools được gọi:** `get_ticket_info` (mock)  
**Workers called sequence:** `supervisor -> retrieval_worker -> policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): "Level 3 emergency requires 2 approvers; final approver is Security Lead per Access Control SOP"  
- confidence: 0.79  
- Correct routing? Partial (retrieval returned supplementary SOP; policy_tool combined rules but missed one conditional exception)

**Nhận xét:**
Routing gọi retrieval trước để lấy SOP, sau đó policy_tool giải mã quy trình. Kết quả partial do policy_tool chưa áp đủ điều kiện ngoại lệ; cần mở rộng exception list.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------:|------:|
| retrieval_worker | 9 | 60% |
| policy_tool_worker | 5 | 33% |
| human_review | 1 | 7% |

### Routing Accuracy

- Trong số 15 câu test nội bộ, supervisor route đúng: **13 / 15**  
- Câu route sai (đã sửa bằng cách nào?): 2 — cập nhật rule keyword + thêm test case để cover exception  
- Câu trigger HITL: 1 (confidence < 0.5 hoặc conflict between policy_result and retrieved evidence)

### Lesson Learned về Routing

1. Keyword-based routing nhanh và đơn giản nhưng cần whitelist/blacklist rõ ràng cho các từ đa nghĩa.  
2. Bổ sung fallback LLM classifier giúp xử lý câu phức tạp (edge cases) và giảm false-positive từ keyword.

### Route Reason Quality

`route_reason` hiện tại chứa keyword match + flags (e.g., `contains:P1;risk:high`). Đây là đủ để bắt đầu debug; cải tiến tiếp theo: chuẩn hoá thành enum (`POLICY`, `RETRIEVAL`, `ACCESS`, `HITL`) và thêm `evidence_hint` (ví dụ: matched_phrase).
