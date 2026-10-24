# Airflow cho Tiki_ABSA

Bộ setup local dùng Airflow **3.3.2 / Python 3.11**, PostgreSQL 16 và LocalExecutor.
Khác repo tham khảo Airflow 2: phiên bản này có API server và DAG processor riêng,
không dùng lệnh `airflow webserver`. Chỉ có một writer chạy pipeline incremental
hiện tại; không nhân bản clean/inference thành các DAG khác chạy lặp dữ liệu.

## File và dịch vụ

- `airflow/dags/kb_incremental_dag.py`: DAG `tiki_kb_incremental`, hai tasks
  `process_batches -> report`, tối đa một run/task đồng thời, retry 2 lần sau 2 phút.
- `source/orchestration/airflow_batches.py`: inbox, processing, receipts, archive,
  retry batch pending trước và chạy ML trong subprocess riêng.
- `scripts/airflow_worker.py`: gọi nguyên pipeline `scripts.update_kb.run()`.
- `docker/airflow.Dockerfile`, `requirements-airflow.txt`: image Airflow và ML venv
  `/opt/tiki-venv` riêng. scikit-learn 1.6.1 khớp version dùng lưu LogReg hiện có.
- `docker-compose.airflow.yml`: postgres, airflow-api-server, airflow-scheduler,
  airflow-dag-processor; service airflow-init chỉ dùng khi khởi tạo.
- `scripts/airflow.ps1`: setup/start/stop/status/check/test/logs/password.
- `scripts/submit_kb_batch.py`: đưa CSV hoàn chỉnh vào inbox theo hash nội dung.
- `scripts/airflow_init.py`: khởi tạo local admin auth, không in mật khẩu ra log.
- `scripts/airflow_check.py`: kiểm tra chỉ đọc collection và dữ liệu; smoke LogReg.
- `tests/test_airflow_dags.py`: queue/retry tests; DAG import tests chạy trong image.

Qdrant **không** nằm trong compose này. Script setup nối container đang có
(`tiki-qdrant`) vào network `tiki-absa-airflow-network` với alias `qdrant`.
Volume `tiki_qdrant_storage` và dữ liệu Qdrant hiện có được giữ nguyên.

## Lần đầu

Mở Docker Desktop, rồi PowerShell:

```powershell
cd C:\Users\User\Desktop\Tiki_ABSA
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\airflow.ps1 setup
.\scripts\airflow.ps1 check
.\scripts\airflow.ps1 test
.\scripts\airflow.ps1 password
```

`setup` tự tạo `.env.airflow` bằng secrets ngẫu nhiên, không ghi đè file đang có;
tạo thư mục, network, build image, migrate database và bật services. Mở
http://localhost:8080, đăng nhập `admin` và mật khẩu từ lệnh password.
Nếu port 8080 bận, đổi AIRFLOW_UI_PORT trong `.env.airflow`, rồi chạy start.

Docker cần đủ RAM cho Airflow và BGE-M3 (máy này Docker hiện được cấp khoảng 8 GB).
Khi index, tránh chạy đồng thời BGE-M3 khác hoặc PhoBERT nếu thiếu RAM. Không cần
Redis, Celery worker, LLM API key hay S3 cho DAG này.

## Sau khi bật lại máy

```powershell
cd C:\Users\User\Desktop\Tiki_ABSA
.\scripts\airflow.ps1 start
.\scripts\airflow.ps1 status
```

`start` cũng bảo đảm Qdrant chạy và nối đúng network. Dừng Airflow bằng
`.\scripts\airflow.ps1 stop`; lệnh này không dừng hoặc xóa Qdrant.
Không dùng `down --volumes` nếu muốn giữ metadata Airflow và login.

## Đưa review mới vào hàng đợi

CSV cần `product_id,content,rating`; product_id phải có trong products_detail.csv,
rating nguyên 1–5. Xem thêm `source/knowledge_base/INCREMENTAL.md`.
Không đưa dữ liệu thử giả vào KB thật.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.submit_kb_batch `
  --input data/raw/reviews_batch_001.csv
```

Thay bằng CSV thật của bạn. Lệnh này chỉ publish file hoàn chỉnh, chưa thay đổi KB.
Trong Airflow UI, chọn `tiki_kb_incremental`, bật Unpause và Trigger để chạy ngay.
DAG mặc định paused khi tạo, không tự crawl hay xử lý dữ liệu có sẵn trong data/raw.
Sau Unpause, lịch mặc định mỗi 15 phút, timezone Asia/Ho_Chi_Minh, catchup=False.
Không có batch: task hoàn tất với completed_batches=0.

Mỗi run xử lý tối đa KB_MAX_BATCHES=4 file tuần tự. Tên submit theo hash giúp
tránh xử lý lại cùng nội dung. Có thể sửa KB_SCHEDULE/KB_MAX_BATCHES trong
`.env.airflow`, rồi chạy start để Compose áp dụng thay đổi.

## Các thư mục trạng thái

```text
data/airflow_queue/
  inbox/       # CSV hoàn chỉnh chờ xử lý
  processing/  # bản bất biến, giữ nguyên đường dẫn để retry
  archive/     # bản lưu sau khi hoàn thành
  receipts/    # kết quả batch thành công; không tự reprocess lịch sử
  results/     # kết quả từ ML worker về task Airflow

data/processed/kb_batches/<batch_id>/
  manifest.json, done.json, backup và snapshots
```

CSV từ submit được sao chép sang processing trước khi chạy. Worker dùng root
`/opt/tiki` (mount chung data/models/source/scripts), nên các retry trong container
có cùng đường dẫn. Local files được cập nhật trước khi Qdrant hoàn tất; nếu lỗi,
batch pending phải chạy lại cùng settings, không sửa/xóa snapshots hoặc marker.

**Không chạy pipeline Windows hoặc writer khác cùng lúc với DAG.** Nếu có batch
pending từ Windows trước khi chuyển sang Airflow, hoàn tất batch đó bằng lệnh gốc
trước. Linux/Windows khác đường dẫn và URL Qdrant; helper sẽ từ chối tự chuyển đổi
pending batch để tránh nhập nhầm trạng thái. Khóa OS của Windows không đồng bộ
với flock của Linux trên bind mount: chỉ dùng một môi trường để ghi tại một thời điểm.

## Model và cache

Setup mount cache Hugging Face host vào `/opt/hf-cache/hub`. Mặc định
HF_HUB_OFFLINE=1 để dùng model đã tải và không gọi mạng trong task. Nếu cache chưa
đủ, đổi thành 0 và chạy start để tải bằng thư viện chính thức trong lần chạy sau.
Không mount Hugging Face token của host vào container. Với model public BGE-M3,
PhoBERT, không cần token nếu artifact có sẵn/nguồn public truy cập được.

KB_ABSA_MODEL mặc định logreg. PhoBERT/ONNX cần đầy đủ checkpoint/tokenizer và
được kiểm tra riêng trước khi chọn. KB_MAX_LENGTH phải khớp full index hiện tại
(1024). Model CPU torch ở venv riêng, không ảnh hưởng `.venv` Windows.

## Kiểm tra và log

```powershell
.\scripts\airflow.ps1 check
.\scripts\airflow.ps1 test
.\scripts\airflow.ps1 logs
```

`check` xác nhận schema collection/point count, schema CSV/documents và smoke LogReg;
không embed hoặc ghi KB. `test` chạy queue/DAG tests và incremental tests offline,
chỉ dùng fixture/thư mục tạm/Qdrant trong RAM.

Xem task log trong UI hoặc `airflow/logs/`. Khi fail, giữ nguyên batch để Airflow
retry; sau khi hết retries, sửa nguyên nhân (Qdrant dừng, thiếu cache, v.v.) rồi Clear
task `process_batches` hoặc trigger run mới. Airflow ưu tiên pending/processing.
Batch bị lỗi không bị chuyển archive hoặc ghi receipt thành công.

SimpleAuthManager và UI bind 127.0.0.1 dành cho môi trường học tập local. Secrets
trong `.env.airflow` đã được ignore khỏi Git. Không public stack này lên Internet.

## Phạm vi

DAG này tự động hóa pipeline CSV -> clean/label -> merge -> aggregate -> delta
documents -> Qdrant -> verify -> receipt. Chưa tự crawl theo lịch, đồng bộ S3,
retrain model hoặc log MLflow/W&B. Các phần đó là giai đoạn mở rộng tiếp theo.

Tham khảo chính thức:
- https://airflow.apache.org/docs/apache-airflow/3.3.2/howto/docker-compose/index.html
- https://airflow.apache.org/docs/apache-airflow/3.3.2/concepts/dags.html
