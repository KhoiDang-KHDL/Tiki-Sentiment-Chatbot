# Incremental Knowledge Base

```text
CSV → validate/clean → ABSA → merge reviews → aggregate → delta documents
    → commit local snapshots → embed/upsert affected products → verify → done
```

Chạy bằng `scripts/update_kb.py` hoặc [Airflow](../../airflow/README.md).
Không yêu cầu LLM/S3. Qdrant collection phải tồn tại với dense 1.024/Cosine và sparse.

## Input contract

| Field | Ràng buộc |
|---|---|
| `product_id` | Integer dương, tồn tại trong `data/raw/products_detail.csv` |
| `content` | Văn bản review; dòng rỗng sau clean bị loại |
| `rating` | Integer 1–5 |
| Optional | `customer_name`, `created_at`, `review_id`; giữ khi merge |

CSV UTF-8, header `product_id,content,rating`. Với sản phẩm mới, bổ sung detail trước.
Giá/rating/review_count của sản phẩm lấy từ detail, không suy ra từ review batch.

Dedup key: `(product_id, clean_text(content))`. Nội dung chuẩn hóa giống nhau của cùng
sản phẩm chỉ được thêm một lần, kể cả từ người mua khác. Lịch sử cũ không bị dedup lại.
Luồng hỗ trợ append; chưa hỗ trợ edit/delete review theo `review_id`.
Invalid ID/rating làm batch fail; empty/duplicate reviews bị loại.

## Execution

Các lệnh chạy tại repository root với `.venv` có ML dependencies và model/cache.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.update_kb `
  --input data/raw/reviews_batch_001.csv `
  --collection tiki_kb_test --model logreg --dry-run
```

Dry-run validate schema/clean/detail và ước lượng review mới; không ghi file, load model
hoặc gọi Qdrant. Không xác nhận checkpoint, nhãn lịch sử hay kết nối collection.

Cập nhật thật:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.update_kb `
  --input data/raw/reviews_batch_001.csv `
  --collection tiki_kb_test --model logreg
```

| Option / env | Ý nghĩa |
|---|---|
| `--collection` / `QDRANT_COLLECTION` | Bắt buộc chỉ rõ collection |
| `--url` / `QDRANT_URL` | Đích Qdrant; host thường `http://localhost:6333` |
| `--model` | logreg/phobert/phobert_onnx; cần checkpoint/tokenizer tương ứng |
| `--batch-size` / `KB_INDEX_BATCH_SIZE` | Embedding batch size |
| `--max-length` / `KB_MAX_LENGTH` | Phải khớp full index, hiện dùng 1024 |
| `EMBEDDING_DEVICE` | Thiết bị BGE-M3 |
| `--revision` | Tăng khi thay logic/tokenizer; hoàn tất pending trước khi đổi |

Chỉ một writer hoạt động. Không sửa input/detail/canonical CSV hoặc chạy full index
song song với batch. OS lock chỉ bảo vệ các tiến trình dùng cùng cơ chế khóa.

## Data và artifacts

| Canonical file trong `data/processed/` | Cập nhật |
|---|---|
| `labeled_processed_products_reviews.csv` | Append review mới đã gán nhãn |
| `product_aspect_scores.parquet` | Aggregate lại từ toàn bộ review CSV |
| `documents.jsonl` | Thay documents của affected products |

Artifacts tại `data/processed/kb_batches/<batch_id>/`:

| Artifact | Vai trò |
|---|---|
| `labeled_reviews.csv` | Nhãn review của batch |
| `kb_delta_reviews.csv`, `kb_delta_product_ids.txt` | Reviews mới và affected IDs |
| `delta_documents.jsonl` | Payload cập nhật Qdrant |
| `main.csv`, `scores.parquet`, `documents.jsonl` | Snapshots sau rebuild |
| `before_*` | Backup canonical trước batch |
| `manifest.json` | Identity, hashes và state |
| `done.json` | Kết quả sau khi verify Qdrant thành công |

Qdrant chỉ embed/upsert affected products: upsert stable IDs trước, xóa stale IDs sau,
verify ID/payload rồi đánh dấu done. Point count có thể tăng hoặc giảm do review đại diện.
Direct-review documents mới được giữ và refresh metadata qua các batch tiếp theo.
`product_documents.jsonl` không thuộc canonical output của pipeline này.

Sau incremental, full reindex phải dùng `documents.jsonl` canonical nếu cần giữ direct
reviews. Full builder cũ chưa có cùng chính sách; không ghi đè canonical bằng builder đó.

## Idempotency và recovery

Batch ID phụ thuộc CSV content, ABSA checkpoint size/mtime, pipeline/revision và đích Qdrant.
Batch đã done được skip khi chạy lại; không tự phục hồi collection bị xóa/restore bên ngoài.
Model repository/auxiliary files chưa được khóa theo commit.

Local files và Qdrant không có transaction chung. Khi lỗi sau partial commit:

1. Giữ `kb_batches/pending.json`, input và toàn bộ artifacts.
2. Sửa nguyên nhân runtime, không sửa canonical/detail/snapshots.
3. Retry đúng lệnh gốc, cùng checkpoint, revision, URL, collection và embedding settings.
4. Xác nhận `done.json` được tạo trước khi bắt đầu batch tiếp theo.

Retry dùng snapshots, không merge/predict lại; stable IDs tránh tạo trùng.
Hash checks từ chối artifact/canonical/detail đã bị sửa ngoài pipeline.
Không tự rollback Qdrant; recovery theo hướng hoàn tất pending batch.

## Verification

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_kb_incremental.py -v
```

Offline tests dùng temporary files, fake encoder/predictor và in-memory Qdrant.
Với batch thật, kiểm tra manifest/done, new review count, affected IDs, payload/source
và retrieval cho nội dung mới. Không dùng point count hoặc câu trả lời LLM làm bằng chứng duy nhất.

## Modules

`label_reviews.py` → `merge_reviews.py` → `aggregate_absa.py` → `build_delta_documents.py`
→ `index_qdrant_delta.py`. `incremental_io.py` cung cấp validation, atomic writes và lock;
`scripts/update_kb.py` điều phối snapshots, retries và completion.
