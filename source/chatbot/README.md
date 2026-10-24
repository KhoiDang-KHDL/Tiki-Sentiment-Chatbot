# Chatbot và HTTP API

```text
Chainlit → api_client.py → FastAPI → retrieval / URL Analyzer / LLM
```

Entry point UI: `demo_chainlit.py` → `demo_chainlit_http.py`.
`demo_chainlit_local.py` là bản direct cũ, chỉ giữ để đối chiếu và regression tests.
Docker lifecycle: [DOCKER.md](../../DOCKER.md). Kiểm tra chức năng: [TESTING.md](TESTING.md).

## API contract

Swagger/OpenAPI: [localhost:8000/docs](http://localhost:8000/docs).

| Endpoint | Input chính | Output |
|---|---|---|
| `GET /health` | — | Qdrant/collection status, provider configuration |
| `POST /search` | `query`, `top_k`, filters | `sources`, `documents`; không gọi LLM |
| `POST /chat` | Search fields, `history`, `context_id`, `focus_current` | `answer`, `sources` |
| `POST /chat/stream` | Như `/chat` | SSE: `sources`, `token`, `done` hoặc `error` |
| `POST /analyze` | `url`, `absa_model` | `report`, `context_id`, `product_id`, `sources` |
| `GET /metrics` | `API_ENABLE_METRICS=true` | Prometheus exposition |

`query`: 1–4.000 ký tự. `top_k`: integer 1–8, mặc định 5.
Filters: `min_rating`, `price_min`, `price_max`, `doc_types`, `aspect_preferences`.
`history`: tối đa 8 message, role `user` hoặc `assistant`; client gửi lại mỗi request.
`absa_model`: `logreg`, `phobert_onnx`, `phobert`.

| HTTP status | Ý nghĩa |
|---|---|
| 422 | Input/schema không hợp lệ |
| 503 | Retrieval hoặc cấu hình LLM chưa sẵn sàng |
| 502 | Provider LLM thất bại |

SSE đã bắt đầu có thể trả HTTP 200 rồi phát `error`. Client phải chờ `done` để xác nhận
hoàn tất; không lưu partial answer vào history. Khi đã phát token, không ghép câu trả lời
của provider fallback vào cùng stream.

## Retrieval và context

- Encoder BGE-M3: dense 1.024 chiều; ưu tiên ONNX local nếu có, fallback FlagEmbedding.
- Truy xuất dense, áp dụng metadata filters và ABSA reranking; Redis cache tùy chọn.
- `TikiRAG` được khởi tạo tại API startup; request đầu vẫn có thể chậm do warm-up.
- `/analyze` giữ context trong RAM: tối đa 128 mục, TTL một giờ; restart xóa context.
- Chainlit `/clear` reset history và `context_id` phía UI. API chạy một worker.
- URL mới có thể crawl Tiki và chạy ABSA; kết quả không tự ghi vào Qdrant.

ABSA positive ratio dùng mẫu số `positive + negative`; neutral không được tính là negative.
Similarity score là điểm xếp hạng retrieval, không phải rating/xác suất.

## Provider configuration

| Biến | Giá trị |
|---|---|
| `LLM_PROVIDER` | `google`, `groq`, `auto` |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Google AI Studio; ưu tiên `GEMINI_API_KEY` |
| `GROQ_API_KEY` | Groq |
| `GOOGLE_MODEL`, `GROQ_MODEL`, `GROQ_FAST_MODEL` | Model IDs |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS` | Timeout/output limit |
| `LLM_CONTEXT_MAX_CHARS`, `LLM_HISTORY_MAX_CHARS` | Giới hạn prompt theo ký tự |

`auto` thử Groq trước Google khi có key tương ứng. OpenRouter không được hỗ trợ.
Docker đọc `.env.docker`; chạy host đọc `.env` và process environment (process ưu tiên).
`/health` không xác minh key/quota bằng một lời gọi LLM.

## Chạy ngoài Docker

Cần `.venv` có ML dependencies, checkpoint/cache và Qdrant collection đã index.
Đặt `QDRANT_URL`, `QDRANT_COLLECTION` và provider variables trong environment hoặc `.env`.
Nếu có `set_env.ps1` local, có thể dot-source file đó. Không chạy lại index khi restart.

Terminal API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn source.chatbot.api:app --host 127.0.0.1 --port 8000 --workers 1
```

Terminal UI:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000"
$env:DEBUG = "false"
.\.venv\Scripts\python.exe -m chainlit run source/chatbot/demo_chainlit.py --host 127.0.0.1 --port 8001 --headless
```

CLI chẩn đoán retrieval, không gọi LLM:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.demo_chat --query "sản phẩm chất lượng tốt" --context-only
```

## Runtime options

| Biến | Hành vi |
|---|---|
| `API_ENABLE_METRICS=true` | Expose `/metrics` |
| `API_LOG_INTERACTIONS=true` | Ghi question/answer/sources; path qua `API_LOG_FILE` |
| `REDIS_URL` | Bật cache nếu Redis server truy cập được |
| `API_WARM_CACHE=true` | Warm tối đa 20 tên sản phẩm; yêu cầu Redis |

API hiện phục vụ local, chưa có authentication/rate limiting.
