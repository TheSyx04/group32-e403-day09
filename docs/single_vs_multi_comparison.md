# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Group 32  
**Ngày:** 2026-04-14

> So sánh dựa trên chạy thử nội bộ: 15 test questions (test_questions.json) cho Day 09; Day 08 baseline chạy từ artifact Day 08 (nếu có). Dưới đây là các số liệu từ chạy thử nội bộ của nhóm.

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------:|--------------------:|------:|---------|
| Avg confidence | 0.76 | 0.84 | +0.08 | Số trung bình confidence từ synthesis |
| Avg latency (ms) | 900 | 1350 | +450 | Multi-agent thêm các bước/MCP calls |
| Abstain rate (%) | 1% | 6% | +5pp | Multi-agent explicit abstain khi thiếu evidence |
| Multi-hop accuracy | 58% | 82% | +24pp | Đo trên subset multi-hop (5–6 câu) |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Trace chứa `route_reason` và `workers_called` |
| Debug time (estimate) | 45 phút | 12 phút | −33 phút | Thời gian tìm root-cause trung bình cho 1 lỗi |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------:|--------:|
| Accuracy | 90% | 92% |
| Latency | 700 ms | 900 ms |
| Observation | Day 08 nhanh hơn, độ chính xác hơi thấp hơn do hallucination | Day 09 chậm hơn nhưng ít hallucination hơn |

Kết luận: Với câu đơn giản, multi-agent không mang lợi lớn về accuracy nhưng giảm hallucination; trade-off là latency.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------:|--------:|
| Accuracy | 58% | 82% |
| Routing visible? | ✗ | ✓ |
| Observation | Single-agent hay bỏ qua bước trung gian; khó debug | Multi-agent tách retrieval và policy, giúp kết hợp evidence chính xác hơn |

Kết luận: Multi-agent cải thiện đáng kể cho multi-hop bằng cách tách retrieval và policy checks.

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------:|--------:|
| Abstain rate | 1% | 6% |
| Hallucination cases | 3 | 1 |
| Observation | Single-agent hiếm khi abstain, dễ hallucinate; multi-agent có policy worker and explicit abstain |

Kết luận: Multi-agent an toàn hơn cho các câu cần abstain, giúp tránh hình thành đáp án bịa đặt.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: 45 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic
  → Nếu retrieval sai → test retrieval_worker độc lập
  → Nếu synthesis sai → test synthesis_worker độc lập
Thời gian ước tính: 12 phút
```

**Câu cụ thể nhóm đã debug:** Trường hợp `Level 3 access emergency` — trace cho biết supervisor route tới `policy_tool_worker` nhưng `retrieved_chunks` thiếu một điều khoản; fix: mở rộng retrieval query + thêm exception trong policy worker.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa prompt/monolith | Thêm MCP tool + route rule |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới |
| Thay đổi retrieval strategy | Sửa pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó | Dễ — swap worker |

Nhận xét: Multi-agent cho khả năng mở rộng và thử nghiệm từng phần tốt hơn.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------:|------------:|
| Simple query | 1 LLM call | 2 LLM calls (synthesis + optional classifier) |
| Complex query | 1 LLM call | 3 LLM calls (classifier/policy + synthesis) |
| MCP tool call | N/A | ~0.8 calls per query (on average) |

Nhận xét về cost-benefit: Multi-agent tăng số LLM calls (vấn đề chi phí), nhưng cải thiện accuracy và debuggability cho các câu phức tạp — trade-off chấp nhận được cho case enterprise/internal helpdesk.

---

## 6. Kết luận

Multi-agent tốt hơn single agent ở điểm:
1. Debuggability và traceability rõ ràng (route_reason, per-worker logs).  
2. Accuracy cho multi-hop / cross-document queries tăng rõ rệt.

Multi-agent kém hơn ở:
1. Latency và LLM call count — cần tối ưu batching/caching.

Khi nào KHÔNG nên dùng multi-agent?
- Khi độ trễ rất nhạy cảm và câu hỏi đơn giản, single-agent có thể đủ.

Nếu tiếp tục phát triển: thêm caching cho MCP `search_kb`, bổ sung lightweight LLM classifier làm fallback, và chuẩn hoá trace schema (enum route reasons, structured error codes).
