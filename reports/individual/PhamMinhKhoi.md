# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Phạm Minh Khôi  
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
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
- File chính: `eval_trace.py` và quản lý thư mục `artifacts/` (gồm `traces/`, `eval_report.json`, `grading_run.jsonl`)
- Functions tôi implement: `compare_single_vs_multi()`, `analyze_traces()`, logic ghi log và tổng hợp metrics

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Tôi đảm nhận vai trò chốt chặn cuối cùng (Sprint 4) của dự án. Sau khi các thành viên hoàn thành Supervisor và các Worker ở 3 sprint đầu, tôi chạy toàn bộ hệ thống trên 15 câu hỏi test và 10 câu hỏi grading. Tôi chịu trách nhiệm tổng hợp trace, đo lường các metrics như confidence, latency, routing distribution, và so sánh trực tiếp với baseline của Lab Day 08 để cung cấp dữ liệu cho đội Docs.

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

Tên commit: `feat: complete sprint 4 trace, comparison report, and grading log`  
Đã xử lý xóa khóa `artifacts/` trong file `.gitignore`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Hard-code baseline của Lab Day 08 vào dictionary `day08_baseline` trong hàm `compare_single_vs_multi()` thay vì đọc từ file ngoài.

**Lý do:**

Trong bối cảnh thời gian gấp (file grading mở lúc 17:00 và deadline 18:00), mục tiêu quan trọng nhất là đảm bảo pipeline sinh ra `eval_report.json` đúng hạn. Việc viết thêm module để parse kết quả cũ tiềm ẩn rủi ro lỗi đường dẫn hoặc sai định dạng, có thể làm gián đoạn toàn bộ quá trình chạy grading.

**Trade-off đã chấp nhận:**

Hy sinh tính tự động hóa và khả năng tái sử dụng để đổi lấy độ ổn định và tốc độ. Code trở nên kém linh hoạt (phải sửa tay nếu thay đổi baseline), nhưng đảm bảo pipeline chạy mượt mà, không crash trong thời điểm quan trọng.

**Bằng chứng từ trace/code:**

```python
# Bên trong hàm compare_single_vs_multi() của eval_trace.py
day08_baseline = {
    "total_questions": 15,
    "avg_confidence": 0.52,          
    "avg_latency_ms": 2100,            
    "abstain_rate": "15%",            
    "multi_hop_accuracy": "45%",      
}
```
---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** UnicodeDecodeError: 'charmap' codec can't decode byte... khi đọc file trace JSON.

**Symptom (pipeline làm gì sai?):**

Khi chạy lệnh `python eval_trace.py --compare`, hệ thống crash ngay lập tức. Các file trace không thể đọc được, dẫn đến không thể tổng hợp metrics và không sinh ra `eval_report.json`.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Lỗi nằm ở logic đọc file trong hàm `analyze_traces()` của `eval_trace.py`. Trên Windows, hàm `open()` mặc định dùng encoding `cp1252`. Trong khi đó, các file trace chứa tiếng Việt (UTF-8), dẫn đến lỗi decode.

**Cách sửa:**

Thêm tham số `encoding="utf-8"` vào hàm `open()` khi đọc file.

**Bằng chứng trước/sau:**

Trước khi sửa:
```python
for fname in trace_files:
with open(os.path.join(traces_dir, fname)) as f:
traces.append(json.load(f))
```
(Lỗi: UnicodeDecodeError)
Sau khi sửa:
```python
for fname in trace_files:
with open(os.path.join(traces_dir, fname), encoding="utf-8") as f:
traces.append(json.load(f))
```
(Output: 📊 Comparison report saved → artifacts/eval_report.json)

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Quản lý môi trường chạy và xử lý sự cố nhanh. Tôi phát hiện kịp thời việc database ChromaDB chưa được index, sửa lỗi encoding trên Windows, và đảm bảo file `grading_run.jsonl` đúng format và nộp đúng hạn.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi tập trung vào lớp evaluation và trace, chưa tham gia sâu vào việc tối ưu prompt hoặc logic bên trong các Worker như `policy_tool.py`, nên mức độ hiểu chi tiết về luồng MCP còn hạn chế.

**Nhóm phụ thuộc vào tôi ở đâu?**  

Nhóm phụ thuộc hoàn toàn vào tôi ở bước xuất file `grading_run.jsonl`. Nếu bước này lỗi hoặc trễ, toàn bộ phần Grading Questions sẽ mất điểm.

**Phần tôi phụ thuộc vào thành viên khác:**  

Tôi phụ thuộc vào cấu trúc graph và contract của các Worker. Nếu Worker phát sinh exception không được handle, pipeline chạy test sẽ bị gián đoạn.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ cải tiến hàm `save_trace` để log chi tiết latency theo từng Worker thay vì chỉ lưu tổng `latency_ms`. Trace thực tế cho thấy có câu mất hơn 12.000ms (ví dụ gq01 trước khi warm-up), nên việc tách riêng latency của `retrieval_worker` và `policy_tool_worker` sẽ giúp xác định chính xác bottleneck để tối ưu hiệu năng.

---
