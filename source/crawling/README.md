# Tiki crawling và preprocessing

Chạy từ repository root bằng `.venv`. HTTP client dùng chung với URL Analyzer.

## Bulk crawl

```powershell
.\.venv\Scripts\python.exe -m source.crawling.main --category 1846 --pages 3 --review-pages 10 --output data/raw/new_crawl
```

| Module | Output | Nội dung |
|---|---|---|
| 1 | `products_list.csv` | Product IDs và URLs, loại ID trùng |
| 2 | `products_detail.csv` | Thông tin sản phẩm, seller, specs, metadata |
| 3 | `products_reviews.csv` | product_id, customer_name, rating, content, created_at UTC |

Chạy từng module:

```powershell
.\.venv\Scripts\python.exe -m source.crawling.main --module 1 --category 1846 --pages 3 --output data/raw/new_crawl
.\.venv\Scripts\python.exe -m source.crawling.main --module 2 --input-csv data/raw/new_crawl/products_list.csv --output data/raw/new_crawl
.\.venv\Scripts\python.exe -m source.crawling.main --module 3 --input-csv data/raw/new_crawl/products_list.csv --output data/raw/new_crawl
```

- Module 2 mặc định chỉ giữ sản phẩm có review content trên trang kiểm tra đầu.
- `--include-without-reviews`: giữ cả sản phẩm không có review.
- `--ai-summary`: lấy summary có sẵn từ Tiki API; mặc định tắt.
- Module 3: tối đa mặc định 10 trang × 20 reviews, dedup theo ID hoặc content fallback.
- Output mặc định không overwrite; dùng thư mục mới hoặc chỉ định `--overwrite`.
- HTTP/schema errors được báo lỗi; không chuyển thành trang rỗng.

## Preprocessing

```powershell
.\.venv\Scripts\python.exe -m source.preprocessing.main --raw-dir data/raw/new_crawl --output data/processed/new_crawl
```

| Output | Transformation |
|---|---|
| `processed_details.csv` | Loại HTML/script/style và nội dung quảng cáo; giữ field names cho KB |
| `processed_products_reviews.csv` | Giữ content gốc, thêm clean_content, loại empty/duplicate theo sản phẩm |

`clean_text()` lowercase, mở rộng viết tắt, lọc ký tự và chuẩn hóa khoảng trắng.
Preprocessing không tạo nhãn ABSA, tokens hoặc train/test splits.
Đưa review mới vào [incremental pipeline](../knowledge_base/INCREMENTAL.md) để gán nhãn và cập nhật KB.

## URL Analyzer integration

```text
URL → optional Redis → Qdrant
                     └→ cache/KB miss → Module 2/3 → clean → ABSA → report/cache
```

URL Analyzer lấy tối đa 5 trang review, giữ raw content cho báo cáo và clean_content cho model.
Cache namespace `analysis:v4` tách collection/model/product. `predict_and_aggregate()`
ưu tiên clean_content nếu có; nếu thiếu, áp dụng clean_text lên content.
Vectorizer đã lưu chỉ chạy transform, không fit lại. Live analysis không ghi CSV hoặc index KB.

## Verification và giới hạn

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_crawling_preprocessing.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_url_analyzer.py -v
```

Tests dùng HTTP fixtures, kiểm tra CSV/preprocessing, pagination, dedup và error handling.
Live availability phụ thuộc Tiki API và có thể gặp 403/429/timeout.
Cleaner hiện có chưa tái tạo mọi sửa lỗi từ ngữ trong dữ liệu huấn luyện lịch sử;
độ chính xác checkpoint cần được đánh giá với đúng preprocessing/runtime.
Bulk crawler chưa được nối vào lịch Airflow; DAG hiện nhận CSV đã submit.
