# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Ngo Quang Tang  
**Vai trò trong nhóm:** Docs Owner  
**Ngày nộp:** 14/4/2026 
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.

**Module/file tôi chịu trách nhiệm:**
- `docs/system_architecture.md` — mô tả kiến trúc Supervisor-Worker, roles, spec
- `docs/routing_decisions.md` — log 3 routing decisions từ traces
- `docs/single_vs_multi_comparison.md` — so sánh Day 08 vs Day 09
- `README.md` — context, objectives, structure
- `contracts/worker_contracts.yaml` — template contracts

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Docs dựa trên graph.py (Vũ Đức Minh), workers/ (Trần Sỹ Minh Quân), traces (Phạm Minh Khôi), MCP tools (Nguyễn Thế Anh). Tôi integrate insights từ tất cả components thành single source of truth.

**Bằng chức (commit hash, file có comment tên bạn, v.v.):**

5 files chính được soạn thảo hoàn toàn bởi tôi; markdown formatting consistent; tables trong system_architecture design để clarity.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Dùng **markdown table format** cho component specifications (thay vì prose paragraphs).

**Các lựa chọn thay thế:**
1. Prose paragraphs: dễ viết, khó scan
2. JSON/YAML schema: formal, khó đọc
3. Table format (chọn): dễ scan, compact, rõ ràng

**Lý do:**

Systematic multi-agent design cần `Input → Logic → Output` rõ ràng cho mỗi worker. Table format giúp:
- Reviewer nhanh hiểu worker responsibility
- MCP developer dễ định vị fields cần integrate
- Trace analyst dễ map logs → table columns

**Trade-off đã chấp nhận:**

- Table khó mở rộng khi field nhiều hơn → giới hạn 6-8 fields quan trọng
- Markdown table không support nested lists → dùng code blocks cho complex configs

**Bằng chứng từ trace/code:**

```markdown
| Thuộc tính | Mô tả |
|-----------|-------|
| Input | task (str), optional metadata |
| Output | supervisor_route, route_reason |
| Routing logic | Keyword matching + risk flags |
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Inconsistency giữa ví dụ tasks trong routing_decisions.md và actual trace filenames.

**Symptom:**

Người đọc không thể cross-reference examples với actual traces trong artifacts/traces/run_*.json. Khi trace analyst cần verify documentation, phải manual search thay vì có direct link.

**Root cause:**

routing_decisions.md dùng generic examples (\"Ticket P1\", \"Flash Sale\") nhưng không mapping tới actual run_*.json timestamps. Documentation separated từ artifact traces.

**Cách sửa:**

Thêm section \"Bằng chứng từ trace file\" với cụ thể trace source:
```
Trace file: artifacts/traces/run_20260414_172009_024184.json
Key fields: route_decision_log[0].route_reason
```

**Bằng chứng trước/sau:**

Trước: Route reason (từ trace): contains: P1, SLA → không rõ trace nào
Sau: Route reason từ run_20260414_172009_024184.json (line 15) → dễ verify

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Structuring documentation cho clarity. Tôi thiết kế system_architecture.md từ zero với flow logic: overview → pipeline → component roles → state schema. Người đọc có thể follow từ high-level xuống low-level. Markdown formatting consistent, tables design cho dễ scan. Routing examples có enough detail (MCP tools, confidence, worker sequence) — không quá generic.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Conciseness — section 2 của system_architecture.md quá dài (250+ từ). Reviewer phải scroll. Nên dùng collapsible sections hoặc reference thay vì inline.

Visual communication — pure text/table, không có flow diagram. Supervisor → [Policy/Retrieval/Synthesis] Workers khó hiểu qua markdown ASCII. Cần Mermaid/PlantUML.

**Nhóm phụ thuộc vào tôi ở đâu?**

Nếu docs sai/chưa xong: MCP developer không rõ tool interface → implement sai. Worker Owner không rõ state schema → contract mismatch. Supervisor Owner không rõ constraints → design lại.

**Phần tôi phụ thuộc vào thành viên khác:**

Cần actual traces từ Phạm Minh Khôi để validate routing_decisions.md. Cần worker code từ Trần Sỹ Minh Quân để extract function signatures. Cần supervisor routing confirmation từ Vũ Đức Minh.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.

**Cải tiến:** Thêm **sequence diagram (Mermaid)** cho routing flow và worker communication vào system_architecture.md (sau current ASCII diagram).

**Lý do và bằng chứng:**

ASCII diagram hiện tại không show **timing / message sequence**:
- Supervisor gọi workers parallel hay sequential?
- Synthesis worker luôn chạy sau?
- Error handling?

Sequence diagram sẽ clarify:
```
User -> Supervisor: submit(task)
Supervisor -> Retrieval + Policy: parallel fetch
Retrieval -> Supervisor: chunks
Policy -> Supervisor: policy_result
Supervisor -> Synthesis: generate(evidence + policy)
Synthesis -> User: final_answer
```

Trace analyst dễ map timing này sang trace JSON events (worker_io_log timestamps). Score improvement nếu grading script check for visual clarity — extra points cho diagram.
