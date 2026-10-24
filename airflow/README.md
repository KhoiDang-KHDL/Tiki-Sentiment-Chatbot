# Airflow orchestration

DAG: `tiki_kb_incremental` trong `dags/kb_incremental_dag.py`.
Runtime: Airflow 3.3.2/Python 3.11, LocalExecutor, PostgreSQL 16.

```text
CSV inbox → process_batches → report
              └→ subprocess ML → scripts.update_kb
```

| Setting | Mặc định |
|---|---|
| Schedule / timezone | `*/15 * * * *` / `Asia/Ho_Chi_Minh` |
| Initial state / catchup | Paused / false |
| Active runs / tasks | 1 / 1 |
| Retry | 2 lần, cách 2 phút |
| Batch limit | `KB_MAX_BATCHES=4`, xử lý tuần tự |
| ABSA model | `KB_ABSA_MODEL=logreg` |

## Setup và lifecycle

Full stack: [DOCKER.md](../DOCKER.md). Chỉ quản lý Airflow:

```powershell
.\scripts\airflow.ps1 setup
.\scripts\airflow.ps1 start
.\scripts\airflow.ps1 status
.\scripts\airflow.ps1 password
.\scripts\airflow.ps1 stop
```

UI mặc định [localhost:8080](http://localhost:8080). Setup sinh `.env.airflow`, build ML image,
migrate metadata và start API server/scheduler/DAG processor. Qdrant hiện có được nối
alias `qdrant` vào network chung; container/volume không được tạo lại.

## Submit batch

Schema và preconditions: [Incremental KB](../source/knowledge_base/INCREMENTAL.md).

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.submit_kb_batch --input data/raw/reviews_batch_001.csv
```

Submit publish CSV hoàn chỉnh theo content hash vào inbox, chưa cập nhật KB.
Trong Airflow UI: Unpause DAG và Trigger để chạy ngay. Khi bật lịch, DAG kiểm tra inbox
mỗi 15 phút. Inbox rỗng trả `completed_batches=0`; không tự crawl từ Tiki.

## Queue và artifacts

| Path trong `data/airflow_queue/` | Vai trò |
|---|---|
| `inbox/` | Batch đã publish |
| `processing/` | Bản bất biến cho worker/retry |
| `archive/` | Batch hoàn thành |
| `receipts/` | Kết quả thành công; chống reprocess cùng nội dung |
| `results/` | Output của subprocess ML |

Worker root `/opt/tiki`; ML interpreter `/opt/tiki-venv/bin/python`.
Pipeline artifacts: `data/processed/kb_batches/<batch_id>/`.
Chỉ tạo archive/receipt sau khi pipeline xác nhận Qdrant thành công.

## Recovery

1. Đọc task log và pending manifest; giữ nguyên input, snapshots và cấu hình batch.
2. Sửa nguyên nhân runtime: Qdrant, cache, checkpoint hoặc quyền file.
3. Sau khi hết retries, Clear task `process_batches` hoặc trigger run mới.

Queue ưu tiên batch pending/processing trước inbox. Không chạy writer Windows song song
với DAG Linux: khóa Windows và `flock` Linux không đồng bộ trên bind mount.
Batch pending từ Windows phải hoàn tất bằng môi trường/lệnh gốc trước khi chuyển writer.

## Model/cache configuration

Các biến trong `.env.airflow`:

| Biến | Ý nghĩa |
|---|---|
| `QDRANT_URL`, `QDRANT_COLLECTION` | Đích ghi KB |
| `HF_HUB_CACHE_HOST` | Host cache mount vào `/opt/hf-cache/hub` |
| `HF_HUB_OFFLINE=1` | Chỉ dùng cache có sẵn; đặt 0 nếu cần tải artifact |
| `KB_ABSA_MODEL` | `logreg`, `phobert`, `phobert_onnx` |
| `KB_MAX_LENGTH`, `KB_INDEX_BATCH_SIZE` | Embedding settings; max-length phải khớp full index |
| `KB_PIPELINE_REVISION` | Tăng khi thay logic/model phụ trợ sau khi batch cũ hoàn tất |
| `KB_SCHEDULE`, `KB_MAX_BATCHES` | Lịch và giới hạn batch/run |

Đổi cấu hình rồi chạy `start`. Checkpoint/tokenizer phải tồn tại trước khi xử lý batch.
ML dependencies được cài trong venv riêng, gồm scikit-learn 1.6.1 cho checkpoint LogReg.

## Verification

```powershell
.\scripts\airflow.ps1 check
.\scripts\airflow.ps1 test
.\scripts\airflow.ps1 logs
```

`check`: collection/data schema, point count và LogReg smoke; không ghi KB.
`test`: queue/DAG và incremental fixtures. Log tại Airflow UI hoặc `airflow/logs/`.

DAG hiện xử lý CSV → KB, chưa điều phối crawl định kỳ, S3, retrain hoặc MLflow/W&B.
SimpleAuthManager và loopback ports dùng cho local deployment.
