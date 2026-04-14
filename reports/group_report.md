# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Group 32  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| [Vũ Đức Minh] | Supervisor Owner | [vuducminh474@gmail.com] |
| [Trần Sỹ Minh Quân] | Worker Owner | [minhquantsy@gmail.com] |
| [Nguyễn Thế Anh] | MCP Owner | [theanha2hvtls@gmail.com] |
| [Ngô Quang Tăng ] | Docs Owner | [ngoquangtang2004@gmail.com] |
| [Phạm Minh Khôi ] | Trace Owner | [phamminhkhoi.05.09.12@gmail.com] |

**Ngày nộp:** 2026-04-14  
**Repo:** group32-e403-day09  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

Hệ thống gồm 1 `Supervisor` (implement trong `graph.py`) và 3 worker chính: `retrieval_worker` (tìm evidence trong `data/docs/` sử dụng ChromaDB / sentence-transformers), `policy_tool_worker` (kiểm tra policy và gọi MCP tools), và `synthesis_worker` (tạo câu trả lời grounded bằng LLM). `mcp_server.py` cung cấp mock MCP tools: `search_kb` và `get_ticket_info`.

Routing logic: Supervisor dùng kết hợp **keyword matching** (fast path cho các từ khóa như `refund`, `P1`, `access`) và một **fallback classifier** (lightweight LLM call) để xử lý câu phức tạp. `route_reason` ghi lại lý do (ví dụ: `contains:P1;risk:high`), giúp giải trình quyết định.

MCP tools tích hợp (ví dụ trace):
- `search_kb`: tìm các chunks liên quan cho policy/retrieval (ví dụ trace gq01 gọi `search_kb` trả về `policy_refund_v4.txt`)  
- `get_ticket_info`: mock trả về trạng thái ticket khi cần thông tin runtime

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

Quyết định quan trọng nhất của nhóm là dùng **keyword-based routing** làm route-first strategy, với **fallback LLM classifier** khi keyword không rõ ràng. Vấn đề: keyword đơn giản nhanh nhưng dễ sai với ngôn ngữ tự nhiên; classifier tăng chi phí/latency nhưng giảm false-positive.

Các phương án cân nhắc:
1) Chỉ keyword rules — nhanh, đơn giản, nhưng nhiều false routing.  
2) Chỉ LLM classifier — chính xác hơn nhưng tốn call và tăng độ trễ.  
3) Kết hợp: keyword-first, classifier fallback (chọn)

Chọn phương án 3 vì cân bằng tốc độ và độ chính xác: các case rõ ràng (P1, refund) đi đường tắt bằng keyword; các câu phức tạp hoặc ambiguous trigger classifier. Bằng chứng: trace `gq09` (multi-hop) ban đầu route đúng theo keyword nhưng policy exception bị bỏ sót — classifier fallback giảm các trường hợp này. Đoạn trace mẫu:

```
{ "task": "Ticket P1...", "supervisor_route": "retrieval_worker", "route_reason": "contains:P1;risk:high" }
```

---

## 3. Kết quả grading questions (150–200 từ)

**Tổng điểm raw ước tính:** 74 / 96

**Câu pipeline xử lý tốt nhất:**
- ID: gq01 — trả lời SLA/P1 chính xác, có citation đến `sla_p1_2026.txt` (điểm cao do evidence rõ ràng).

**Câu pipeline fail hoặc partial:**
- ID: gq09 — partial: trả lời cả hai phần nhưng thiếu một exception trong access SOP; root cause: policy_tool thiếu rule cho temporary contractor grant.

**Câu gq07 (abstain):** Nhóm chọn abstain và ghi rõ không có evidence trong docs → được điểm tối đa cho câu abstain.

**Câu gq09 (multi-hop khó nhất):** Trace ghi rõ 2 workers (retrieval + policy_tool) — trace có `workers_called: [retrieval_worker, policy_tool_worker, synthesis_worker]` — kết quả partial, được điểm một phần.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

Metric thay đổi rõ nhất: **Multi-hop accuracy** tăng từ ~58% (Day 08) lên ~82% (Day 09). Nhóm thấy rõ benefit ở những câu cần cross-document reasoning: multi-agent tách retrieval và policy check giúp kết hợp evidence chính xác. Bất ngờ: latency tăng nhưng debug time giảm đáng kể. Trường hợp multi-agent làm chậm hệ thống là các query đơn giản, nơi overhead của routing + MCP làm latency tăng mà không nhiều lợi ích.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**
| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| [Vũ Đức Minh] | Supervisor (`graph.py`), routing rules | 1 |
| [Trần Sỹ Minh Quân ] | `workers/retrieval.py`, Chroma index | 2 |
| [Nguyễn Thế Anh] | `mcp_server.py`, `workers/policy_tool.py` | 3 |
| [Ngô Quang Tăng, Phạm Minh Khôi] | `workers/synthesis.py`, `eval_trace.py`, docs | 4 |

**Điều nhóm làm tốt:** phối hợp nhanh, test workers độc lập trước khi nối vào graph; trace schema cơ bản đầy đủ.  
**Điều nhóm làm chưa tốt:** thiếu test cases cho một số exception trong policy; cần thêm unit tests cho policy_tool.

Nếu làm lại: phân công thêm thời gian để viết unit tests cho policy exceptions và chuẩn hoá `route_reason` từ đầu.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

1) Thêm caching cho `search_kb` và cache layer cho MCP để giảm latency nổi bật.  
2) Thêm bộ test tự động cho các case exception (flash sale, digital product, temporary access) và chuẩn hoá `route_reason` (enum + matched phrase) để tăng chất lượng trace.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
