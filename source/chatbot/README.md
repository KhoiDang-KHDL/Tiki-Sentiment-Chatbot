# Chạy chatbot tại thư mục Tiki_ABSA

> Cập nhật: `demo_chainlit.py` hiện là giao diện HTTP gọi FastAPI. Bản direct cũ
> nằm trong `demo_chainlit_local.py`. Khi chạy local cần bật API trước; trong
> Docker dùng `scripts/stack.ps1 start`. Hướng dẫn hiện hành: `DOCKER.md` ở gốc dự án.

Hướng dẫn kiểm tra URL Analyzer và giao diện Chainlit: [TESTING.md](TESTING.md).

Hướng dẫn crawl hàng loạt, làm sạch dữ liệu và crawler dùng chung với URL Analyzer:
[Crawling và preprocessing](../crawling/README.md).

Yêu cầu: Qdrant hoạt động, collection đã index bằng BGE-M3, các thư viện trong
`requirements.txt` đã cài. Không cần BGE-M3 ONNX hoặc Redis để chạy.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
. .\set_env.ps1
```

Chọn ít nhất một provider và đặt key trong terminal. Không lưu key thật vào mã nguồn.
Các lệnh sau là lựa chọn thay thế, không bắt buộc cấu hình cả hai:

```powershell
$env:GROQ_API_KEY = "YOUR_GROQ_KEY"
# Hoặc:
$env:OPENROUTER_API_KEY = "YOUR_API_KEY"
```

`LLM_PROVIDER=auto` thử Groq nếu có key, sau đó OpenRouter nếu có key.
Có thể đặt `groq` hoặc `openrouter` để chỉ dùng một provider. Tên model,
timeout và giới hạn context được cấu hình trong `set_env.ps1`.
Model cần có quyền truy cập và quota tương ứng trên tài khoản provider.

Xem tài liệu truy xuất, không gọi API LLM:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.demo_chat --query "sản phẩm chất lượng tốt" --context-only
```

Một câu hỏi hoặc hội thoại nhiều lượt:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.demo_chat --query "sản phẩm chất lượng tốt" --stream
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.demo_chat --stream
```

Trong phiên tương tác, `/clear` xóa lịch sử và `/exit` kết thúc. Model retrieval
được tải một lần và tái sử dụng. Lịch sử chỉ tồn tại trong phiên; chưa có bộ phân tích
URL hoặc cơ chế chọn sản phẩm hiện tại. Khi có nhiều sản phẩm, nên nêu rõ tên.

Kết quả có nguồn truy xuất và prompt yêu cầu LLM dùng `[Nguồn N]`. Chưa có bộ
kiểm chứng tự động rằng mọi phát biểu hoặc trích dẫn do LLM tạo ra đều đúng.
ABSA dùng tỷ lệ tích cực trong các ý kiến không trung lập, không đại diện tỷ lệ
khách hài lòng trên tổng số đánh giá. Điểm retrieval dùng để xếp hạng, không phải xác suất.

Nếu stream lỗi trước khi phát nội dung, hệ thống có thể thử provider tiếp theo.
Nếu đã phát nội dung, hệ thống báo gián đoạn và không nối thêm câu trả lời khác.
Giới hạn context/lịch sử tính theo ký tự, không phải bộ đếm token chính xác.

Chạy kiểm tra offline (không cần key, không gọi API):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## HTTP API

Nạp `set_env.ps1` và đặt `GEMINI_API_KEY` trong cùng terminal trước khi khởi động:

```powershell
.\.venv\Scripts\python.exe -m uvicorn source.chatbot.api:app --host 127.0.0.1 --port 8000
```

Dùng một worker để chỉ tải một model embedding. Model được tải lúc startup;
server chỉ sẵn sàng sau khi tải xong. Nếu Qdrant/collection chưa có, startup sẽ lỗi.
Swagger UI: http://127.0.0.1:8000/docs. Không cần chạy lại index khi khởi động API.

- `POST /search`: trả `sources` và `documents`; không gọi LLM.
- `POST /chat`: trả `answer` và `sources`.
- `POST /chat/stream`: SSE có các event `sources`, `token`, `done`, hoặc `error`.
  Khi stream đã bắt đầu, lỗi nằm trong event `error`, không thể đổi mã HTTP.
- `GET /health`: kiểm tra collection Qdrant và báo key/provider đã cấu hình hay chưa;
  không gọi LLM để xác nhận key hợp lệ hoặc còn quota.

Ví dụ PowerShell (terminal thứ hai):

```powershell
$body = @{ query = "sản phẩm chất lượng tốt"; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/search -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
# Đổi /search thành /chat để sinh câu trả lời bằng Google.
```

Các bộ lọc: `min_rating`, `price_min`, `price_max`, `doc_types` và
`aspect_preferences` (ví dụ `{"quality": 0.5}`). `top_k` từ 1 đến 8.
`/chat` và `/chat/stream` nhận thêm `history`: tối đa 8 message dạng
`{"role": "user" hoặc "assistant", "content": "..."}`. Client tự gửi lại lịch sử;
API không lưu trạng thái hội thoại giữa các người dùng. Rewrite có thể thêm một
lời gọi Google khi có lịch sử.

Lỗi đầu vào trả HTTP 422; lỗi retrieval/thiếu cấu hình LLM trả 503;
lỗi provider LLM trả 502, chi tiết có thể kèm mã HTTP của Google (ví dụ 429).

Tính năng tùy chọn trong `set_env.ps1`:

- `API_ENABLE_METRICS=true`: bật `/metrics` bằng Prometheus instrumentator.
- `API_WARM_CACHE=true`: warm tối đa 20 tên sản phẩm từ đúng collection;
  chỉ thực hiện khi Redis đã được bật bằng `REDIS_URL`.
- `API_LOG_INTERACTIONS=true`: ghi câu hỏi, câu trả lời và nguồn vào
  `logs/interactions.jsonl` trong dự án. `API_LOG_FILE` thay đổi vị trí file.

`.env` tại gốc dự án được hỗ trợ qua `python-dotenv`; biến đã có trong terminal
được ưu tiên. Không commit file chứa API key. API này dùng cho local, chưa có
xác thực hoặc giới hạn yêu cầu cho triển khai công khai.
