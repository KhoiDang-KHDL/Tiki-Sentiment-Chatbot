# Docker Compose

## Prerequisites

- Docker Desktop chạy Linux containers; dự trù RAM cho Airflow và BGE-M3.
- Python environment `.venv` có `python-dotenv` để sinh cấu hình bằng script setup.
- Qdrant container hiện có, mặc định `tiki-qdrant`, với collection đã index.
- Checkpoint trong `models/`, dữ liệu canonical trong `data/`, Hugging Face cache đã chuẩn bị.
- Provider credentials lấy từ process environment, `.env` hoặc `set_env.ps1` local.

Đây là setup cho môi trường đã có dữ liệu/model; clone repository chưa cung cấp các artifact đó.
Tên project Compose: `tiki-absa-airflow`. Qdrant nằm ngoài Compose và được nối vào network chung.

## Setup

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\stack.ps1 setup
.\scripts\stack.ps1 check
```

`setup` khởi tạo Airflow, sinh env khi chưa tồn tại, build API/UI và start services.
Script giữ nguyên file env đã có và Qdrant volume hiện tại.

| Cấu hình | Nội dung |
|---|---|
| `.env.airflow` | Airflow credentials, Qdrant URL/collection/network, HF cache, KB settings |
| `.env.docker` | Provider, API keys, model, timeout và API/UI host ports |
| `.env.monitoring` | Grafana credentials và monitoring host ports |
| `.env.*.example` | Template được lưu trong Git |

Đổi cấu hình: sửa file env tương ứng rồi chạy `start`. Không commit file env thật hoặc `set_env.ps1`.

## Lifecycle

```powershell
.\scripts\stack.ps1 start    # Start/recreate với cấu hình hiện tại
.\scripts\stack.ps1 status   # Health và port mapping
.\scripts\stack.ps1 check    # UI → API → Qdrant; kiểm tra monitoring
.\scripts\stack.ps1 logs     # API/UI logs
.\scripts\stack.ps1 stop     # Stop services; giữ volumes
```

Sau khi sửa source API/UI:

```powershell
.\scripts\stack.ps1 build
.\scripts\stack.ps1 start
```

`start` không build code mới. API/UI dùng source COPY trong image; Airflow dùng bind mount.
Qdrant được start/nối network khi khởi động stack và không bị dừng bởi `stack.ps1 stop`.
Locust dùng profile riêng; xem [monitoring](monitoring/README.md).

## Services

| Service | Port mặc định | Runtime |
|---|---|---|
| API | 8000 | Python 3.11, ML venv, một uvicorn worker |
| UI | 8001 | Chainlit HTTP client |
| Airflow API | 8080 | Airflow 3.3.2; scheduler/DAG processor riêng |
| PostgreSQL | Internal | Airflow metadata |
| Prometheus | 9090 | API metrics, retention 15 ngày |
| Grafana | 3000 | Provisioned datasource/dashboard |
| Locust | 8089 | Profile `loadtest` |

Host ports bind `127.0.0.1`. Setup có thể chọn API/UI 8002/8003 khi port mặc định bận.

Credentials:

```powershell
.\scripts\airflow.ps1 password
.\scripts\monitoring.ps1 password
```

## Images và mounts

| Image | Build/runtime dependency |
|---|---|
| `tiki-absa-airflow:3.3.2` | `docker/airflow.Dockerfile`; ML venv tách khỏi Airflow |
| `tiki-absa-api:local` | Copy ML venv từ image Airflow; cài `requirements-api.txt` |
| `tiki-absa-ui:local` | `requirements-ui.txt`; không có model/provider keys |

API mount `models/` read-only, HF cache và `logs/`; retrieval đọc Qdrant, không đọc CSV.
Airflow mount source, scripts, tests, data, models và cache để xử lý batch.

## Persistence và kiểm tra

- Qdrant: volume ngoài Compose, mặc định `tiki_qdrant_storage`.
- Airflow/PostgreSQL, Prometheus và Grafana: persistent volumes.
- Hội thoại: `logs/interactions.jsonl` khi logging bật; chưa có log rotation.
- URL context: RAM của API, TTL một giờ; mất sau restart. Dùng một API worker.

Không dùng `down --volumes` khi cần giữ trạng thái. Tránh chạy nhiều tiến trình embedding
đồng thời nếu Docker thiếu RAM; tăng worker sẽ nhân bản model/context.

```powershell
.\scripts\stack.ps1 test
```

`check` không gọi LLM; `test` dùng fixture và kiểm tra runtime/model theo script Airflow.
Acceptance UI/LLM: [TESTING.md](source/chatbot/TESTING.md).
CI: [CI.md](CI.md). Batch scheduling: [Airflow](airflow/README.md).
