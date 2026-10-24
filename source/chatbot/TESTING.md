# Testing và acceptance checks

Chạy lệnh từ repository root. Kiến trúc mặc định: **Chainlit → HTTP API → retrieval/LLM**.
Setup và start stack theo [DOCKER.md](../../DOCKER.md).

## Offline regression

```powershell
.\scripts\ci.ps1 -Install
.\scripts\ci.ps1
```

Hoặc dùng `.venv` đã có dependency:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

| Test module | Coverage |
|---|---|
| `test_api.py` | Validation, filters, provider errors, URL context, SSE |
| `test_http_ui.py` | HTTP client, history, stream completion/error |
| `test_url_analyzer.py` | URL validation, KB/cache, crawl/inference errors |
| `test_crawling_preprocessing.py` | HTTP fixtures, CSV, normalization, inference input |
| `test_kb_incremental.py` | Deduplication, delta updates, partial writes, retry |
| `test_airflow_dags.py` | Queue/idempotency; DAG import trong Airflow runtime |
| `test_llm.py` | Prompt/context, provider selection, fallback/stream |
| `test_monitoring.py` | Latency, SSE semantic errors, parser và percentiles |
| `test_chainlit_ui.py` | Regression cho direct UI cũ |

Các test trên dùng fixture, không kiểm tra chất lượng model/provider thật.
Job DAG và Docker riêng: [CI.md](../../CI.md).

## Stack smoke test

```powershell
.\scripts\stack.ps1 check
.\scripts\airflow.ps1 check
```

| Check | Điều kiện đạt |
|---|---|
| UI container → API | `/health` và `/search` thành công |
| API → Qdrant | Đúng collection và có documents |
| Monitoring | Prometheus target `tiki-api` UP; Grafana database OK |
| Airflow/model runtime | Collection/data schema và LogReg smoke check đạt |

`/health` không gọi LLM, không chứng minh key còn quota hoặc request đầu có latency thấp.

## UI acceptance

Mở UI theo port từ `stack.ps1 status`; theo dõi `stack.ps1 logs`.
Các thao tác hỏi đáp dưới đây gọi provider thật theo cấu hình API.

| Thao tác | Kết quả yêu cầu |
|---|---|
| Hỏi tên sản phẩm | API nhận `/chat/stream`; UI hiển thị answer và nguồn |
| Gửi URL đã có trong KB | API nhận `/analyze`; hiển thị báo cáo đúng sản phẩm |
| Hỏi tiếp “Có nên mua sản phẩm này?” | Giữ đúng `context_id` và báo cáo tham chiếu |
| Yêu cầu sản phẩm thay thế | Truy xuất sản phẩm khác, không đề xuất lại sản phẩm gốc |
| Chuyển sang tên sản phẩm mới | Retrieval mới, không giữ sai context URL |
| Gửi URL sai host | Lỗi validation trước khi gọi host đó |
| Provider lỗi/stream gián đoạn | Hiển thị lỗi; không lưu partial answer vào history |
| `/clear` hoặc phiên mới | History/context được reset hoặc tách riêng |

ABSA model trong Settings chỉ áp dụng khi cần crawl/infer, không tính lại thống kê KB.

## URL Analyzer và model checks

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.url_analyzer --url "https://tiki.vn/product-p53497035.html"
.\.venv\Scripts\python.exe -X utf8 -m source.absa.demo_inference --model logreg
```

URL có trong KB phải trả nguồn `kb`, model `kb_precomputed` và `absa_n_reviews` đúng.
Đổi model inference thành `phobert`/`phobert_onnx` khi đã có artifact tương ứng.

Live crawl, bỏ qua KB/cache:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.url_analyzer --url "https://tiki.vn/product-p53497035.html" --refresh --model logreg
```

Kiểm tra model đã chọn, số review sau clean/dedup và thống kê sáu khía cạnh.
Tiki 403/429/timeout phải được báo rõ; kết quả crawl không tự cập nhật KB.

## Đánh giá bổ sung

- ABSA: precision/recall/F1 trên tập có nhãn, cùng preprocessing và checkpoint version.
- Retrieval: tài liệu/sản phẩm đúng trong top-k trên bộ query chuẩn.
- Generation: bám nguồn, đúng sản phẩm và xử lý trường hợp thiếu dữ liệu.
- Incremental: [batch validation và recovery](../knowledge_base/INCREMENTAL.md).
- Performance: [Locust và metric definitions](../../monitoring/README.md).

Ghi rõ môi trường, dataset/model version, warm-up và số mẫu khi báo cáo kết quả.
