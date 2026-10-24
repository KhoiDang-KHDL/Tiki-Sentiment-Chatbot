# Crawl và xử lý dữ liệu Tiki

Chạy các lệnh từ thư mục gốc `Tiki_ABSA` bằng Python trong `.venv`.
Các module được điều chỉnh từ repo tham khảo để dùng namespace `source`, đường
dẫn của dự án hiện tại và cùng một HTTP client với chatbot.

## Crawl hàng loạt

```powershell
.venv\Scripts\python.exe -m source.crawling.main --category 1846 --pages 3 --review-pages 10 --output data/raw/new_crawl
```

Lệnh chạy Module 1 → Module 2 → Module 3 và tạo:

- `products_list.csv`: ID và URL theo danh mục, loại ID trùng.
- `products_detail.csv`: thông tin sản phẩm, người bán, thông số và metadata.
- `products_reviews.csv`: product_id, customer_name, rating, content, created_at (UTC).

Mặc định Module 2 chỉ giữ sản phẩm có nội dung review trên trang kiểm tra đầu tiên,
giống ý định của repo tham khảo. Dùng `--include-without-reviews` để giữ mọi sản phẩm.
`--ai-summary` lấy thêm tóm tắt có sẵn từ API Tiki; mặc định không gọi API phụ này.
Review có nội dung được lấy tối đa 10 trang, 20 review/trang; loại trùng theo ID
(hoặc nội dung khi không có ID). Có khoảng nghỉ giữa các trang/sản phẩm.

Chạy riêng từng module:

```powershell
.venv\Scripts\python.exe -m source.crawling.main --module 1 --category 1846 --pages 3 --output data/raw/new_crawl
.venv\Scripts\python.exe -m source.crawling.main --module 2 --input-csv data/raw/new_crawl/products_list.csv --output data/raw/new_crawl
.venv\Scripts\python.exe -m source.crawling.main --module 3 --input-csv data/raw/new_crawl/products_list.csv --output data/raw/new_crawl
```

Mọi lệnh kiểm tra file đầu ra trước khi crawl, mặc định từ chối ghi đè. Dùng thư
mục đầu ra mới hoặc chỉ định `--overwrite` khi muốn thay thế file đã có. HTTP lỗi
hoặc dữ liệu API sai định dạng được báo thành lỗi, không giả thành trang rỗng.
Chưa xác minh API Tiki trực tiếp trong lần bổ sung này; kiểm thử dùng phản hồi giả
lập, không bảo đảm Tiki luôn cho phép truy cập từ môi trường triển khai.

## Xử lý dữ liệu

```powershell
.venv\Scripts\python.exe -m source.preprocessing.main --raw-dir data/raw/new_crawl --output data/processed/new_crawl
```

- `processed_details.csv`: bỏ HTML, script/style và các cụm quảng cáo trong mô tả;
  giữ tên trường `rating_average`, `review_count` để tương thích KB hiện tại.
- `processed_products_reviews.csv`: giữ review gốc, thêm `clean_content`; chữ thường,
  mở rộng viết tắt, bỏ ký tự theo quy tắc `clean_review.py` của repo tham khảo,
  chuẩn hóa khoảng trắng; bỏ câu rỗng và trùng theo từng sản phẩm.

Các file raw và tập dữ liệu đã gán nhãn hiện có không bị thay đổi. Lệnh này chưa
tạo `tokens`, nhãn ABSA hay chia tập train/test. Pipeline KB hiện tại cần
`labeled_processed_products_reviews.csv`; file review vừa làm sạch chưa thay thế
được file đã gán nhãn đó. Việc dự đoán/gán nhãn và cập nhật KB là bước tiếp theo.

## Chainlit và URL analyzer

```text
URL → Redis → Qdrant
                  ↘ chưa có: Module 2 + Module 3
                             → prepare_reviews → predict_and_aggregate → báo cáo
```

`url_analyzer.py` import `fetch_product_detail` và wrapper crawl review dùng chung;
không còn tự viết HTTP request. URL mới lấy tối đa 5 trang review, giữ nội dung gốc
cho báo cáo và `clean_content` cho model. Cache kết quả mới dùng namespace `analysis:v4`
để không dùng lại kết quả từ luồng chưa chuẩn hóa.

`predict_and_aggregate()` dùng chung `clean_text()` cho mọi caller. Nếu đã có
`clean_content` dạng chuỗi thì ưu tiên trường đó; nếu chưa có thì xử lý `content`.
Vectorizer đã lưu chỉ được `transform`, không `fit` lại; tokenizer PhoBERT giữ
nguyên cách gọi hiện tại. Live crawl không tự ghi CSV, huấn luyện lại hay index Qdrant.

Đối chiếu dữ liệu hiện có: 6.964/11.019 review có `clean_content` trùng hoàn toàn
với kết quả hàm làm sạch từ repo tham khảo. Một số câu có thêm sửa lỗi từ ngữ trong
dữ liệu đã xử lý; chưa có source tái tạo đầy đủ các sửa đổi đó. 9.011/9.015 câu train
khớp văn bản `clean_content` hiện có. Vì vậy đây là khôi phục quy tắc tiền xử lý có
source, chưa khẳng định tái tạo toàn bộ pipeline đã tạo checkpoint.

Không đưa scheduler, S3/Lambda hay DAG Airflow của repo tham khảo vào lần bổ sung
này vì chúng cần cấu hình hạ tầng riêng và không tham gia luồng crawl URL trực tiếp.

## Kiểm thử offline

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_crawling_preprocessing.py -v
.venv\Scripts\python.exe -m unittest discover -s tests -p test_url_analyzer.py -v
```

Kiểm tra crawl → CSV → preprocessing trong thư mục tạm, dữ liệu gốc cho hiển thị,
văn bản đầu vào model, giới hạn phân trang, xử lý lỗi và bảo vệ file đã có.

Lần xác minh bổ sung: toàn bộ 61 kiểm thử offline của dự án đạt. Đã chạy thử
checkpoint LogReg thật với hai review và nhận đủ sáu khía cạnh. Môi trường hiện tại
báo checkpoint được lưu bằng scikit-learn 1.6.1 trong khi runtime là 1.9.1;
chưa thay đổi thư viện hay checkpoint trong lần bổ sung này. Chưa xác minh lại
độ chính xác trên tập test hoặc chạy checkpoint PhoBERT thật.
