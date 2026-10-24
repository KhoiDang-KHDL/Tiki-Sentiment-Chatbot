# Tiki Sentiment Chatbot

[![CI](https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot/actions/workflows/ci.yml)

Hệ thống hỏi đáp sản phẩm Tiki sử dụng RAG và phân tích cảm xúc theo khía cạnh (ABSA).

## Kiến trúc

```text
Browser → Chainlit → FastAPI → BGE-M3 → Qdrant → LLM
                         └→ URL Analyzer → KB hoặc Tiki API → ABSA

CSV batch → Airflow → clean/label → merge/aggregate → delta documents → Qdrant
FastAPI /metrics → Prometheus → Grafana
GitHub push/PR → offline tests + DAG validation + container smoke tests
```

| Thành phần | Triển khai |
|---|---|
| Serving | FastAPI, Chainlit HTTP client, một API worker |
| Retrieval | BGE-M3, Qdrant dense vectors, metadata filters, ABSA reranking |
| ABSA | LogReg, PhoBERT hoặc PhoBERT ONNX; sáu khía cạnh |
| LLM | Google AI Studio hoặc Groq |
| Orchestration | Airflow 3.3.2, LocalExecutor, PostgreSQL |
| Observability | Prometheus, Grafana, Locust |
| CI | GitHub Actions; Python 3.11/3.12 |

## Khởi động

Các lệnh PowerShell chạy từ thư mục gốc repository. Môi trường đã setup:

```powershell
.\scripts\stack.ps1 start
.\scripts\stack.ps1 check
```

| Giao diện | Địa chỉ mặc định |
|---|---|
| Chatbot | [localhost:8001](http://localhost:8001) |
| API docs | [localhost:8000/docs](http://localhost:8000/docs) |
| Airflow | [localhost:8080](http://localhost:8080) |
| Grafana | [localhost:3000/d/tiki-api](http://localhost:3000/d/tiki-api) |

Port thực tế: `.\scripts\stack.ps1 status`.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [Docker](DOCKER.md) | Prerequisites, setup, lifecycle, cấu hình và persistence |
| [Chatbot/API](source/chatbot/README.md) | Endpoint, provider, context và chạy ngoài Docker |
| [Testing](source/chatbot/TESTING.md) | Offline tests và acceptance checks |
| [Incremental KB](source/knowledge_base/INCREMENTAL.md) | Batch schema, outputs, idempotency và recovery |
| [Airflow](airflow/README.md) | Submit batch, lịch chạy và retry |
| [Monitoring](monitoring/README.md) | Metrics, alerts, Locust và báo cáo tải |
| [CI](CI.md) | Workflow, artifacts và kiểm tra trước khi push |
| [Crawling](source/crawling/README.md) | Tiki API và preprocessing |

## Phạm vi

- Dữ liệu, checkpoint, Hugging Face cache và secrets được cấp riêng; không lưu trong Git.
- URL analysis phục vụ báo cáo/cache; cập nhật KB đi qua pipeline incremental.
- CI dùng fixture; chất lượng ABSA/RAG và provider thật cần đánh giá riêng.
- Stack dành cho local, bind loopback; chưa có CD, xác thực API hoặc public deployment.
