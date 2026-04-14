# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trần Sỹ Minh Quân  
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài:** ~680 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong lab này tôi phụ trách chính ba worker cốt lõi của pipeline: retrieval, policy/tool, và synthesis. Cụ thể, tôi chịu trách nhiệm các file `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`, đồng thời rà soát phần contract liên quan ở `contracts/worker_contracts.yaml` để đảm bảo I/O nhất quán với graph. Ở retrieval, tôi tập trung vào đường truy vấn ChromaDB và chuẩn hóa score. Ở policy/tool, tôi đảm bảo worker có thể xử lý exception cases (flash sale, digital product, activated product) và có khả năng gọi tool qua MCP path khi cần. Ở synthesis, tôi ưu tiên logic grounded, có citation, và cơ chế abstain khi không đủ context.

Công việc của tôi kết nối trực tiếp với Supervisor Owner qua `graph.py`: supervisor route sang worker nào thì output của worker đó phải đủ sạch để synthesis tổng hợp và để trace/debug đọc được.

**Bằng chứng:** `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`, và các trace như `artifacts/traces/run_20260414_163843_745676.json`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi chọn hướng “worker deterministic trước, LLM sau” cho lớp synthesis để giảm rủi ro phụ thuộc API và giảm hallucination trong giai đoạn hoàn thiện Sprint 2-3.

Ban đầu có hai lựa chọn: (1) để synthesis phụ thuộc hoàn toàn vào LLM, hoặc (2) dùng rule-based synthesis làm baseline grounded rồi mới cho phép LLM diễn đạt lại khi có key. Tôi chọn phương án (2) vì phù hợp mục tiêu lab là trace/debug trước, tối ưu chất lượng sau. Với phương án này, ngay cả khi API key bị lỗi hoặc môi trường mạng không ổn định, worker vẫn trả được câu trả lời có cấu trúc, có citation, và không bịa thông tin khi thiếu evidence.

Trade-off tôi chấp nhận là câu trả lời có thể kém tự nhiên hơn cách viết của LLM full-mode. Tuy nhiên, lợi ích lớn là tính ổn định và tính kiểm thử cao: tôi có thể kiểm tra output bằng rule rõ ràng như có citation hay không, có abstain đúng hay không.

**Bằng chứng từ code/trace:** trong `workers/synthesis.py`, các hàm như `synthesize`, `_rule_based_answer`, `_ensure_citation`, và nhánh fallback khi thiếu context cho thấy định hướng này. Trong các trace chạy graph, output synthesis luôn bám evidence source.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Score retrieval có lúc không hợp lệ theo contract (âm hoặc khó diễn giải), kéo theo confidence ở downstream bị sai lệch.

**Symptom:** Khi chạy retrieval ở các vòng test ban đầu, có trường hợp score không nằm trong kỳ vọng 0.0–1.0. Điều này làm confidence ở synthesis không phản ánh đúng mức liên quan của evidence, và cũng vi phạm ràng buộc contract của retrieval worker.

**Root cause:** ChromaDB trả về distance, trong khi worker cần similarity. Nếu chuyển đổi không chặt chẽ thì score có thể vượt ngoài biên mong muốn. Vấn đề nằm ở worker logic, không phải ở dữ liệu nguồn.

**Cách sửa:** Tôi cập nhật logic trong retrieval để chuyển distance về similarity và clamp cứng vào [0, 1], đồng thời ghi score đã chuẩn hóa vào `retrieved_chunks`.

**Bằng chứng trước/sau:** Sau khi sửa, các lần chạy standalone của retrieval cho score hợp lệ (ví dụ 0.537, 0.684, 0.576 ở các query test gần nhất) và không còn thấy score âm trong output hiện tại. File liên quan: `workers/retrieval.py`.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt phần chuẩn hóa output giữa các worker: giữ contract rõ, tránh worker trả thiếu field, và đảm bảo synthesis có dữ liệu đủ để hoạt động ổn định trong nhiều tình huống (có context/không có context, có policy exception/không có).

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi vẫn cần cải thiện thêm ở retrieval quality (độ chính xác top chunk), đặc biệt các câu có nhiều keyword giao thoa giữa domain IT và policy.

**Nhóm phụ thuộc vào tôi ở đâu?**

Nếu worker layer chưa ổn định, supervisor route đúng vẫn không tạo ra câu trả lời đáng tin cậy; cả trace và report cũng khó kết luận nguyên nhân lỗi.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi phụ thuộc Supervisor Owner ở logic route/needs_tool để worker vào đúng nhánh, và phụ thuộc Trace & Docs Owner để phản ánh đúng hành vi worker trong tài liệu tổng hợp.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ thêm một lớp reranking đơn giản (hybrid lexical + semantic) cho retrieval trước khi đưa vào synthesis. Lý do là trong trace retrieval cho query SLA có lúc kéo thêm chunk ít liên quan (ví dụ câu hỏi SLA nhưng chunk FAQ laptop xuất hiện trong top kết quả). Nếu có rerank, chất lượng bằng chứng sẽ sạch hơn, giúp confidence và câu trả lời cuối ổn định hơn mà không cần tăng số lần gọi model.

---

*File: reports/individual/TranSyMinhQuan.md*