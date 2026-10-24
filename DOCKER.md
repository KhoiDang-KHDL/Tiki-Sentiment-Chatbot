# Chạy Tiki_ABSA bằng Docker Compose

Kiểm tra code tự động trước khi triển khai: xem [CI bằng GitHub Actions](CI.md).

Đã bổ sung Prometheus, Grafana và Locust. Xem [hướng dẫn monitoring và kiểm tra tải](monitoring/README.md)
và [kết quả chạy ngày 23/10/2026](reports/loadtest/RESULTS.md).

Đã kiểm tra trong setup này: tất cả services healthy; HTTP UI mở được; UI -> API
health/search -> Qdrant thành công; phân tích URL của sản phẩm có sẵn trong KB
hiển thị báo cáo trên trình duyệt. Thử chat thật đầu tiên đi qua API nhưng provider
Google trả HTTP 500, nên chưa xác nhận được câu trả lời LLM thành công trong lần
setup. Đây không phải lỗi kết nối giữa UI/API; lỗi được hiển thị trên UI và không
lưu câu trả lời dở vào lịch sử. Không tự đổi provider/model để tránh đổi cấu hình
hoặc chi phí ngoài ý định của bạn.

Luồng đã nối: trình duyệt -> Chainlit -> HTTP API -> Qdrant/LLM.
Airflow dùng cùng Qdrant để cập nhật KB. Qdrant hiện có được nối network, không
được tạo lại hoặc di chuyển volume. Compose chính include cấu hình Airflow cũ,
giữ project name `tiki-absa-airflow` để tái sử dụng PostgreSQL và auth volume.

## Các file chính

| File | Vai trò |
|---|---|
| `docker-compose.yml` | Stack thống nhất: API/UI và các dịch vụ Airflow được include. |
| `docker/api.Dockerfile` | Image API có ML venv, một uvicorn worker. |
| `docker/ui.Dockerfile` | Image Chainlit HTTP-only, không có torch hoặc keys LLM. |
| `requirements-api.txt`, `requirements-ui.txt` | Dependencies cho hai dịch vụ. |
| `.env.docker.example` | Mẫu provider config, không chứa key thật. |
| `scripts/stack.ps1` | Setup/start/stop/status/build/check/logs/test. |
| `source/chatbot/api_client.py` | HTTP và SSE client; kiểm tra done/error/stream gián đoạn. |
| `source/chatbot/demo_chainlit_http.py` | UI mới, URL và chat đều gọi API. |
| `source/chatbot/demo_chainlit.py` | Entry point mặc định của UI mới. |
| `source/chatbot/demo_chainlit_local.py` | Bản UI direct cũ được giữ để đối chiếu. |

API giữ các endpoint `/health`, `/search`, `/chat`, `/chat/stream`, `/metrics`.
Endpoint `/analyze` mới trả báo cáo URL và context_id ngẫu nhiên. Client gửi lại
context_id cho câu hỏi tiếp nối; dữ liệu sản phẩm được giữ phía API, tối đa 128
context, hết hạn sau một giờ. Khởi động lại API sẽ mất context: gửi lại URL hoặc
dùng /clear. Không dùng nhiều API workers cho cấu hình context in-memory này.

## Setup lần đầu

Bật Docker Desktop rồi chạy:

```powershell
cd C:\Users\User\Desktop\Tiki_ABSA
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\stack.ps1 setup
```

Setup bảo đảm Airflow/Qdrant network sẵn sàng, tạo `.env.docker` từ provider settings
trong `set_env.ps1`/`.env`/process environment, build hai image, bật services và đợi
health checks. Không ghi đè `.env.docker` đang có; không in key ra stdout.
API image copy ML venv đã build từ image `tiki-absa-airflow:3.3.2` để giữ cùng
versions model runtime; Airflow không được cài trong image API cuối cùng.

Cổng mặc định: API 8000, UI 8001, Airflow 8080; setup thử chọn 8002/8003 nếu các
cổng chatbot đang bận. Xem port mapping thực tế bằng:

```powershell
.\scripts\stack.ps1 status
```

Mở UI theo cổng hiển thị, ví dụ http://localhost:8001. API Swagger ở
http://localhost:8000/docs. Airflow ở http://localhost:8080, login lấy qua
`.\scripts\airflow.ps1 password`. UI/API chỉ publish trên 127.0.0.1 cho local.

## Các lần sau

```powershell
.\scripts\stack.ps1 start
.\scripts\stack.ps1 status
.\scripts\stack.ps1 check
.\scripts\stack.ps1 logs
```

`check` chạy từ **container UI**, gọi health/search của API thật và Qdrant thật,
không dùng LLM quota. Câu trả lời tự nhiên còn phụ thuộc provider key và quota.
`logs` cho thấy request `/chat/stream` hoặc `/analyze` ở API khi thao tác trên UI.

Dừng stack (giữ dữ liệu và Qdrant):

```powershell
.\scripts\stack.ps1 stop
```

`start` không tự build lại code. Khi sửa source API/UI:

```powershell
.\scripts\stack.ps1 build
.\scripts\stack.ps1 start
```

Code API/UI được COPY vào image; Airflow vẫn dùng source bind mount như trước.
Không cần chạy lại full index, train model hoặc cài lại `.venv` khi bật stack.

## Cấu hình và credentials

- `.env.airflow`: Qdrant collection/network, HF cache và cấu hình Airflow.
- `.env.docker`: provider/model/API keys và host ports, chỉ truyền vào API.
- UI chỉ nhận `API_BASE_URL=http://api:8000`; không mount models/cache hoặc secrets.
- API nhận models read-only, HF cache dùng chung và thư mục logs ghi được.
- Không mount data CSV vào API vì retrieval đọc Qdrant; Airflow giữ quyền cập nhật data.

Không commit `.env.docker`/`.env.airflow`; hai file đã được ignore. Khi đổi key/model,
sửa `.env.docker`, chạy start để Compose recreate API với cấu hình mới. `LLM_PROVIDER`
hiện hỗ trợ google/groq/auto theo `llm.py` của dự án; không dùng lại provider OpenRouter
từ bản tham khảo cũ. `health` báo cấu hình có key, chưa xác nhận key hợp lệ hay còn quota.

Log hội thoại ở `logs/interactions.jsonl`. Không tự xoay log trong bản local này.
Metrics API được bật nhưng chưa có Prometheus/Grafana service trong giai đoạn này.

## Kiểm tra

```powershell
.\scripts\stack.ps1 test
```

Chạy unit/integration tests offline trên host và các kiểm thử Airflow/ML trong
container; không gọi provider thật hoặc thay đổi KB. Tests mới kiểm tra HTTP client,
SSE hoàn tất/gián đoạn, URL context phía API, hỏi tiếp và loại sản phẩm hiện tại khi
gợi ý sản phẩm thay thế. Các tests direct UI cũ tiếp tục chạy với bản local giữ lại.

Đánh giá thủ công thêm: hỏi một câu trên Chainlit, kiểm tra API logs có POST
`/chat/stream`; gửi URL có trong KB, xem POST `/analyze`; hỏi tiếp về sản phẩm đó.
Nếu LLM trả lỗi quota/rate limit, UI hiển thị lỗi và không lưu câu trả lời dở vào history.

## Giới hạn vận hành

Docker hiện được cấp khoảng 8 GB RAM: API và task Airflow index có thể cùng load
BGE-M3, cộng thêm UI/Airflow. Nếu thiếu RAM, tăng RAM Docker hoặc tránh index đồng
thời chat nặng; không tăng số workers để giải quyết. Không chạy thêm bản local ML
khác nếu thiếu bộ nhớ. Dữ liệu Qdrant vẫn tồn tại độc lập khi stop stack.

Airflow DAG không bị tự unpause bởi setup này. Việc submit batch và bật lịch vẫn
theo `airflow/README.md`. Chưa thêm tự crawl theo lịch, monitoring dashboard hoặc CI/CD.

Compose include tham khảo: https://docs.docker.com/compose/how-tos/multiple-compose-files/include/
