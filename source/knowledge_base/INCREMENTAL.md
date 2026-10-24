# Cập nhật Knowledge Base incremental

Chạy từ `C:\Users\User\Desktop\Tiki_ABSA`. Pipeline local xử lý tuần tự từng CSV;
không cần Airflow, S3, LLM hoặc API key LLM. Qdrant phải có collection đã khởi tạo
bằng BGE-M3: dense 1024 chiều/Cosine và sparse. Không tạo lại collection.

## Các file

| File | Vai trò |
|---|---|
| `source/absa/label_reviews.py` | Validate, clean và dự đoán sáu nhãn cho từng review. |
| `source/knowledge_base/merge_reviews.py` | Gộp review mới, chống nhập trùng, giữ affected IDs khi retry. |
| `source/knowledge_base/build_delta_documents.py` | Rebuild affected products; thêm review mới trực tiếp và giữ chúng qua batch sau. |
| `source/knowledge_base/index_qdrant_delta.py` | Upsert trước, xóa ID cũ sau, kiểm tra ID và payload cuối cùng. |
| `source/knowledge_base/incremental_io.py` | Kiểm tra dữ liệu, ghi file atomic, hash và khóa tiến trình. |
| `scripts/update_kb.py` | Điều phối, backup, snapshot, retry, cập nhật export documents và đánh dấu hoàn tất. |
| `tests/test_kb_incremental.py` | Kiểm thử offline bằng thư mục tạm và Qdrant trong RAM. |

## Chuẩn bị batch

CSV UTF-8 cần có header `product_id,content,rating`. Rating là số nguyên 1–5.
Có thể thêm customer_name, created_at, review_id; các cột này được giữ khi merge.
product_id phải là số nguyên dương và có trong `data/raw/products_detail.csv`.
Với sản phẩm mới, bổ sung thông tin detail trước. Thông tin giá/rating/review_count
của sản phẩm không được tự suy ra từ batch review; cập nhật detail từ nguồn khi cần.

Ví dụ cấu trúc (thay product_id bằng ID thật, không nhập dữ liệu giả vào KB thật):

```csv
product_id,content,rating
123456,"Sản phẩm tốt, giao hàng nhanh",5
123456,"Đóng gói chưa cẩn thận",2
```

Quy tắc chống trùng: `(product_id, clean_text(content))`, giống cleaner hiện tại.
Hai người mua cùng viết nội dung chuẩn hóa giống nhau cho một sản phẩm được coi
là một quan sát mới. Lịch sử cũ không bị tự động xóa trùng. Đây là luồng append
review, chưa hỗ trợ sửa/xóa review đã lưu; muốn dùng review_id làm khóa phải đổi
đồng bộ cleaner và merge. Các dòng rỗng hoặc trùng trong batch bị loại; ID/rating
không hợp lệ làm batch dừng để sửa đầu vào.

## Kiểm tra trước, chưa thay đổi dữ liệu

```powershell
cd C:\Users\User\Desktop\Tiki_ABSA
. .\set_env.ps1

.\.venv\Scripts\python.exe -X utf8 -m scripts.update_kb `
  --input data/raw/reviews_batch_001.csv `
  --collection tiki_kb_test `
  --model logreg `
  --dry-run
```

Thay đường dẫn bằng batch thật của bạn. Dry-run không tạo file, load model hay gọi
Qdrant; nó kiểm tra schema/clean/detail và báo số dòng dự kiến thêm. Nó chưa xác nhận
model load được, nhãn lịch sử hợp lệ hoặc collection truy cập được.

## Chạy cập nhật

Bật Docker/Qdrant. Sau đó chạy cùng lệnh, bỏ `--dry-run`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.update_kb `
  --input data/raw/reviews_batch_001.csv `
  --collection tiki_kb_test `
  --model logreg
```

Chỉ dùng `phobert` hoặc `phobert_onnx` khi đã có checkpoint/tokenizer tương ứng.
Batch size và độ dài embedding lấy từ KB_INDEX_BATCH_SIZE/KB_MAX_LENGTH, cũng có
thể đặt `--batch-size 2 --max-length 1024`. Giữ max-length giống lần full index.
Thiết bị load BGE-M3 lấy từ EMBEDDING_DEVICE. Model nằm trong cache tải từ trước,
hoặc thư viện có thể cần mạng để tải lần đầu.

Có thể override `--url http://localhost:6333`. Collection bắt buộc cấu hình bằng
`--collection` hoặc QDRANT_COLLECTION để tránh ghi nhầm collection mặc định.

Không chạy full index, sửa CSV/detail hay chạy writer khác cùng lúc. Khóa chỉ điều
phối những tiến trình dùng pipeline này; không khóa script cũ hoặc người sửa file.

## Trạng thái và đầu ra

Pipeline tạo `data/processed/kb_batches/<batch_id>/` chứa:

- `labeled_reviews.csv`: nhãn từng review, được tái sử dụng khi retry.
- `kb_delta_reviews.csv`, `kb_delta_product_ids.txt`: batch và affected products.
- `delta_documents.jsonl`: tài liệu để cập nhật Qdrant.
- `main.csv`, `scores.parquet`, `documents.jsonl`: snapshots sau merge/rebuild.
- `before_*`: backup CSV, scores và documents trước lần cập nhật.
- `manifest.json`: cấu hình, hashes, state, số review mới.
- `done.json`: kết quả sau khi Qdrant xác minh thành công.

Các file canonical được cập nhật:

1. `data/processed/labeled_processed_products_reviews.csv`.
2. `data/processed/product_aspect_scores.parquet` (aggregate lại toàn bộ CSV).
3. `data/processed/documents.jsonl` (chỉ thay documents của affected products).

Qdrant chỉ embed/upsert affected products. Mỗi batch mới thêm review documents
trực tiếp với ID hash ổn định, bên cạnh review đại diện. Các direct review cũ được
giữ lại và refresh metadata trong batch sau. Không giả định point count chỉ tăng:
số review đại diện có thể thay đổi. `product_documents.jsonl` không được dùng hoặc
cập nhật; đây là artifact khác của dự án.

Full `build_documents.py` cũ chưa có chính sách direct-review này. Sau incremental,
muốn full reindex mà giữ direct reviews, index từ `documents.jsonl` canonical đã
đồng bộ; không ghi đè file đó bằng full builder cũ mà chưa bổ sung cùng chính sách.

## Retry khi lỗi

Local files và Qdrant không thuộc một giao dịch chung. Lỗi có thể xảy ra sau khi
CSV đã merge hoặc một số vectors đã upsert. Lúc đó batch giữ trạng thái pending,
không tạo done.json và chặn batch khác. Chạy lại **đúng lệnh cũ**, với input,
checkpoint, revision, URL, collection và max-length như cũ. Không xóa pending.json.

Retry dùng snapshots đã chuẩn bị, không merge lặp hay dự đoán lại nhãn; nó upsert
theo stable IDs và kiểm tra payload rồi mới đánh dấu done. Artifact bị sửa hoặc
canonical/detail bị thay ngoài pipeline sẽ bị phát hiện và yêu cầu giải quyết
trước khi tiếp tục. Không tự động rollback Qdrant: ưu tiên retry hoàn tất.

Nếu đổi file nguồn sau khi batch lỗi, trước tiên khôi phục file nguồn cũ để hoàn
tất batch pending. Lưu lại thông tin trong pending.json/manifest.json khi cần
chẩn đoán, không đưa API keys vào báo cáo.

Batch ID phụ thuộc nội dung CSV, model và thông tin checkpoint (size/mtime),
pipeline version, revision và đích Qdrant. Với cùng batch đã done, lệnh chạy lại
sẽ bỏ qua; đây không phải cơ chế sửa collection sau khi bị xóa/restored bên ngoài.
Nếu đổi tokenizer, model code hoặc quy tắc pipeline, dùng `--revision 2` sau khi
hoàn tất batch cũ. Chưa khóa model weights/embedding repository theo commit.

## Đánh giá

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover `
  -s tests -p test_kb_incremental.py -v
```

Tests không dùng Qdrant thật, BGE-M3 thật hay API LLM. Bao gồm chống trùng, affected
products, thống kê ABSA, giữ direct reviews, không sửa vector sản phẩm khác,
upsert thất bại/partial write và retry, backup/export, khóa writer và artifact hash.

Sau khi chạy batch thật, kiểm tra done.json, số review mới, affected products và
metrics. Dùng retrieval hỏi về review vừa nhập. Giá trị mới phải xuất hiện trong
payload/sources trước khi đánh giá câu trả lời của LLM. Không coi số points hoặc
câu trả lời LLM là bằng chứng duy nhất; kiểm tra ID/payload được pipeline thực hiện
trước khi tạo done.json. Kiểm thử offline chưa thay thế đánh giá ABSA trên review
thực, encoder thực và chất lượng retrieval end-to-end.
