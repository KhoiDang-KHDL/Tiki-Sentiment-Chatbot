# Kiểm tra URL Analyzer và Chainlit

Chạy các lệnh tại `C:\Users\User\Desktop\Tiki_ABSA`.
Chainlit dùng trực tiếp retrieval/LLM, không cần khởi động FastAPI `api.py`.

## 1. Chuẩn bị

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
. .\set_env.ps1
```

Kiểm tra Qdrant và collection dùng chung:

```powershell
.\.venv\Scripts\python.exe -m source.knowledge_base.index_qdrant --check
```

Ví dụ hiện tại dùng `QDRANT_COLLECTION=tiki_kb_test`. Nếu collection khác,
sửa biến môi trường cho khớp dữ liệu đã index.

## 2. Bộ kiểm tra tự động offline

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Các test mới ở `tests/test_url_analyzer.py` và `tests/test_chainlit_ui.py` kiểm tra:
URL đúng/sai host, đọc đúng collection, cache có namespace theo model,
dữ liệu thiếu/null, giới hạn trang và trùng review, chọn model, chạy inference/stream
ngoài event loop, giữ ngữ cảnh URL, gợi ý thay thế, lỗi Tiki và stream gián đoạn.
Chúng dùng dữ liệu giả, không crawl Tiki hoặc gửi dữ liệu sang Google.

## 3. Phân tích URL từ KB, không cần Google

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.url_analyzer --url "https://tiki.vn/product-p53497035.html"
```

Mong đợi: tên sản phẩm, giá/rating nếu có, nguồn `kb`, model `kb_precomputed`,
các thống kê ABSA. Số đánh giá đã phân tích lấy từ `absa_n_reviews`, không lấy
giá trị lớn nhất của từng khía cạnh. Dữ liệu KB không phải giá/tồn kho thời gian thực.

Thử URL sai host:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.url_analyzer --url "https://example.com/a-p123.html"
```

Mong đợi: thông báo URL không hợp lệ, không request tới host đó.

## 4. Kiểm tra crawl mới và ABSA thật

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.url_analyzer --url "https://tiki.vn/product-p53497035.html" --refresh --model logreg
```

`--refresh` bỏ qua cả Redis và KB. Mỗi lần crawl tối đa 5 trang, 20 review/trang,
lọc nội dung rỗng và trùng trước khi inference. Có thể thay model bằng
`phobert_onnx` hoặc `phobert`; phải có checkpoint tương ứng trong `models/` và
thư viện cần thiết. PhoBERT có thể cần tải tokenizer/model nền lần đầu.

Mong đợi khi Tiki trả dữ liệu: nguồn `crawl`, đúng tên model và số review có nội dung
đã chạy inference. Dữ liệu mới chỉ phục vụ báo cáo/cache; không tự upsert vào Qdrant.

Nếu Tiki trả 403/429, timeout hoặc thay đổi định dạng, chương trình báo lỗi rõ ràng;
không có cơ chế vượt chặn. Nếu chỉ phần review lỗi, báo cáo giữ thông tin sản phẩm
và cảnh báo chưa có ABSA. Trường hợp này chưa xác nhận được toàn bộ pipeline live.
Kiểm tra các model độc lập với mạng Tiki bằng:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m source.absa.demo_inference --model logreg
.\.venv\Scripts\python.exe -X utf8 -m source.absa.demo_inference --model phobert_onnx
.\.venv\Scripts\python.exe -X utf8 -m source.absa.demo_inference --model phobert
```

Model nhận văn bản theo `source/absa/inference.py` hiện tại. Chưa bổ sung pipeline
tiền xử lý riêng cho crawler. Cần đối chiếu tiền xử lý lúc train và phiên bản
thư viện lưu checkpoint để đánh giá độ chính xác, không chỉ kiểm tra chạy được.

## 5. Nhận xét Google cho một URL

```powershell
$env:GEMINI_API_KEY = "YOUR_GOOGLE_AI_STUDIO_KEY"
.\.venv\Scripts\python.exe -X utf8 -m source.chatbot.url_analyzer --url "https://tiki.vn/product-p53497035.html" --question "Có nên mua sản phẩm này không?"
```

Lệnh này gọi API Google thật. Nếu thiếu key/hết quota, báo cáo vẫn được giữ và
ghi rõ chưa tạo được nhận xét. Nếu chỉ chạy URL không có `--question`, không gọi LLM.

## 6. Chạy giao diện Chainlit

```powershell
$env:DEBUG = "false"
.\.venv\Scripts\python.exe -m chainlit run source/chatbot/demo_chainlit.py --host 127.0.0.1 --port 8001 --headless
```

`set_env.ps1` cũng đặt `DEBUG=false`. Nếu thấy lỗi `'release' is not a valid boolean`,
terminal chưa được nạp lại cấu hình; đặt lại biến như trên rồi chạy lại.

Mở http://127.0.0.1:8001. Kiểm tra theo thứ tự:

| Thao tác | Kết quả mong đợi |
| --- | --- |
| Gửi URL đã có trong KB ở bước 3 | Có báo cáo ngay, không yêu cầu Google |
| Hỏi “Sản phẩm này có nên mua không?” | Google trả lời dựa trên đúng báo cáo URL |
| Hỏi “Có sản phẩm thay thế không?” | Tìm ứng viên khác, giữ sản phẩm gốc làm tham chiếu |
| Hỏi tên sản phẩm mới rõ ràng | Chạy retrieval mới, không bị giữ ở URL cũ |
| Chọn model ABSA khác trong Settings | Model đó chỉ dùng với sản phẩm cần crawl; KB vẫn dùng thống kê cũ |
| Gửi URL không tồn tại/bị chặn | Có thông báo lỗi; không lưu sản phẩm lỗi làm context hợp lệ |
| Google hết quota trong lúc chat | Giữ báo cáo URL; hiển thị lỗi; không ghi câu trả lời dở vào lịch sử |
| Gửi `/clear` | Xóa history, nguồn và sản phẩm hiện tại của phiên |
| Mở cửa sổ/phiên chat mới | History và sản phẩm hiện tại được tách riêng |

Lần tìm kiếm thông thường đầu tiên sẽ tải BGE-M3 và có thể chậm; gửi URL có trong KB
không cần tải BGE-M3. Nguồn có ID/URL và số `[Nguồn N]`, điểm similarity không phải rating.
Nhấn Ctrl+C trong terminal để dừng UI. Không cần bật `--watch` khi kiểm tra ổn định.

## 7. Redis là tùy chọn

Nếu đã có Redis server, đặt `$env:REDIS_URL = "redis://localhost:6379"` trước khi chạy.
Chạy cùng URL hai lần: lần hai có thể có nguồn `cache`, TTL 1 giờ. Key cache được
tách theo collection, model ABSA và product ID. Không bật Redis vẫn chạy được.
Việc có package `redis` trong `.venv` không có nghĩa là Redis server đã chạy.

Hoàn tất kiểm tra chức năng cần cả test offline, KB thật, crawl+ABSA live, và UI+Google
trên tài khoản của bạn. Test offline hoặc chỉ HTTP 200 của UI không chứng minh quota
Google, crawler Tiki hoặc độ chính xác dự đoán thực tế.
