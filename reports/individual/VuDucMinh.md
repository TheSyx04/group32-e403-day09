# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Vũ Đức Minh  
**Vai trò trong nhóm:** Supervisor Owner  
**Ngày nộp:** 2026-04-14  
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

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py`
- Functions tôi implement: `make_initial_state()`, `supervisor_node()`, `route_decision()`, `human_review_node()`, `build_graph()`, `run_graph()`

Tôi phụ trách phần orchestration của hệ thống ở Sprint 1, tức là phần nhận câu hỏi đầu vào, phân tích tín hiệu trong câu hỏi, quyết định route sang worker phù hợp và ghi trace để nhóm có thể debug sau này. Tôi không nhận phần implement worker thật trong `workers/*.py`, cũng không nhận phần MCP server. Trọng tâm phần tôi làm là làm cho graph chạy end-to-end ở mức tối thiểu nhưng có cấu trúc rõ: state đủ field, route đủ 3 nhánh `retrieval_worker`, `policy_tool_worker`, `human_review`, và trace có thể đọc được.

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Phần tôi làm là nền cho các role khác. Worker Owner cần state và route ổn định để nối worker thật ở Sprint 2. MCP Owner cần `needs_tool` và nhánh policy/access rõ ràng để nối tool ở Sprint 3. Trace & Docs Owner cần `route_reason`, `workers_called`, `history` và `latency_ms` để viết docs và báo cáo.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

Bằng chứng nằm trực tiếp trong `graph.py` và trace Sprint 1, ví dụ `artifacts/traces/run_20260414_152601_872885.json`, `artifacts/traces/run_20260414_152601_888316.json`, `artifacts/traces/run_20260414_152601_892620.json`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn dùng rule-based routing trong `supervisor_node()` thay vì gọi LLM để phân loại câu hỏi ngay từ Sprint 1.

**Lý do:**

Ở Sprint 1, mục tiêu chính của tôi không phải là trả lời đúng toàn bộ nghiệp vụ mà là dựng được bộ khung orchestration rõ ràng, chạy nhanh, dễ test và dễ debug. Nếu dùng LLM để classify ngay từ đầu thì graph có thể “thông minh” hơn, nhưng đổi lại sẽ khó kiểm soát, khó tái hiện lỗi, và khó giải thích vì sao câu hỏi bị route sai. Vì vậy tôi chọn route theo keyword và context quan sát được như `refund`, `flash sale`, `access`, `P1`, `ticket`, `ERR-*`. Tôi còn thêm `route_reason` để trace không chỉ ghi “đi đâu” mà còn ghi “vì sao đi như vậy”.

Tôi cũng thêm bước normalize text bằng `_normalize_for_routing()` để giảm phụ thuộc vào dấu tiếng Việt. Quyết định này xuất phát từ thực tế PowerShell có thể làm méo chuỗi khi pipe script test vào `python -`.

**Trade-off đã chấp nhận:**

Trade-off là rule-based routing đơn giản, nhanh và minh bạch nhưng không bao phủ được các câu hỏi quá mơ hồ. Độ chính xác ngắn hạn có thể kém hơn LLM classifier, nhưng đổi lại tôi có trace rõ và dễ sửa logic.

**Bằng chứng từ trace/code:**

```python
elif _contains_any(task_normalized, policy_keywords):
    route = "policy_tool_worker"
    route_reason_parts.append("task contains refund/access/policy keywords")
    needs_tool = True
```

```text
run_20260414_152601_888316.json
route_reason = "task contains refund/access/policy keywords | task follows policy/tool path and may require tool-backed lookup"
supervisor_route = "policy_tool_worker"
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Case `Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?` bị fail ở điều kiện `risk_high=True` khi chạy script test trong PowerShell.

**Symptom (pipeline làm gì sai?):**

Khi tôi hoặc người dùng chạy script test qua PowerShell, chuỗi tiếng Việt trong log hiển thị thành dạng lỗi mã hóa như `kh?n c?p`. Vì `supervisor_node()` ban đầu dựa vào keyword có dấu như `khẩn cấp`, pipeline vẫn route đúng sang `policy_tool_worker` nhưng lại không bật `risk_high`. Kết quả là script assert báo `risk_high_ok: False` và toàn bộ `SPRINT1_STATUS=FAIL`.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Lỗi nằm ở routing logic của supervisor. Cụ thể, phần phát hiện `risk_high` phụ thuộc quá nhiều vào so khớp chuỗi tiếng Việt nguyên gốc. Khi input bị méo encoding, keyword không còn match.

**Cách sửa:**

Tôi thêm `_normalize_for_routing()` dùng `unicodedata.normalize("NFKD", text)` để chuyển text về dạng ít phụ thuộc dấu hơn. Sau đó tôi đổi danh sách keyword sang dạng normalized như `khan cap`, `hoan tien`, `cap quyen`, `su co`, `quy trinh`. Ngoài ra tôi thêm fallback heuristic: nếu câu hỏi đồng thời có `access/level` và `P1/ticket` thì cũng coi là `risk_high=True`.

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

Trước khi sửa, script test báo:

```text
FAIL Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?
{'risk_high_ok': False, ...}
```

Sau khi sửa, script test báo:

```text
PASS Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?
SPRINT1_STATUS=PASS
```

Và trong trace `run_20260414_152601_890647.json` hoặc trace tương đương sau khi chạy lại, `route_reason` có thêm nhánh:

```text
risk_high=True because task combines access-control request with P1/ticket context
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt nhất ở chỗ biến phần orchestrator từ một file còn nhiều placeholder thành một flow Sprint 1 có thể chạy, test và debug được. Tôi đặc biệt chú ý đến tính minh bạch của trace chứ không chỉ làm cho code “chạy qua”.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa làm phần supervisor đủ thông minh cho các câu hỏi mơ hồ hoặc multi-hop thật. Logic hiện tại vẫn là rule-based nên mới phù hợp Sprint 1, chưa phải giải pháp cuối cùng.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Nếu tôi chưa chốt `graph.py`, các role khác sẽ bị block vì không có state ổn định, không có route rõ ràng và không có trace chuẩn để nối worker hoặc viết docs.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào Worker Owner để Sprint 2 thay placeholder bằng worker thật, và phụ thuộc vào Trace & Docs Owner để phản hồi xem trace hiện tại đã đủ rõ cho docs và grading chưa.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ bổ sung một lớp `route classifier` riêng cho supervisor, vẫn ưu tiên deterministic nhưng tách rule ra khỏi `graph.py` để dễ test và dễ mở rộng hơn. Lý do là trace hiện tại cho thấy supervisor đã route đúng các câu Sprint 1, nhưng logic đang nằm tập trung trong `supervisor_node()`, nên khi sang các case khó như temporal scoping hoặc multi-hop ở Sprint 2–4, việc sửa trực tiếp trong một hàm sẽ nhanh trở nên rối.

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
