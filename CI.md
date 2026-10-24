# Continuous Integration cho Tiki_ABSA

Đã có workflow `.github/workflows/ci.yml`, Git local trên nhánh `main` và remote
`https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot.git`.
Xem kết quả tại [GitHub Actions](https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot/actions/workflows/ci.yml).
Không cần server, SSH key hay khóa LLM.

## CI chạy những gì?

Workflow chạy khi push bất kỳ nhánh, tạo/cập nhật pull request, hoặc bấm Run workflow.
Các run cũ cùng nhánh được hủy khi có code mới. Quyền token chỉ `contents: read`.

| Check trên GitHub | Nội dung |
|---|---|
| Offline tests (Python 3.11) | Cài dependency CI, pip check, compile code, đọc YAML/TOML/JSON, toàn bộ unittest |
| Offline tests (Python 3.12) | Cùng bộ kiểm tra để phát hiện khác biệt giữa Python local và runtime Docker |
| Airflow DAG import | Import DAG thật và kiểm tra single writer/retry/queue trong image Airflow 3.3.2 chính thức, network none |
| Docker and monitoring smoke | actionlint, Compose config, promtool, build Docker UI production, build API fixture riêng, kiểm tra HTTP/SSE/metrics và UI container gọi API |

Offline test dùng dữ liệu tạm, predictor giả và Qdrant in-memory. Kết nối TCP bị
chặn trong runner test; Windows cho phép loopback để asyncio tạo socketpair.
Một DAG test được skip trong môi trường Python thường vì không cài Airflow;
job Airflow riêng chạy test đó thật. Không tải model hay gọi LLM/Tiki thật.

Job container khởi tạo API/UI tạm, dùng port 18000/18001 trên runner rồi dọn dẹp.
Compose production chỉ được validate bằng `.env.*.example`; không start stack thật.
`docker/ci.Dockerfile` chỉ dùng fixture `loadtest_api`, không dùng để deploy.
Dockerfile production API hiện lấy ML venv từ `tiki-absa-airflow:3.3.2`, vốn phải
build trước. CI này **chưa build toàn bộ image ML/API production**, chưa kiểm thử
checkpoint, chất lượng ABSA, retrieval KB thật hay provider LLM thật. Các mục đó
cần bài integration/evaluation riêng; CI xanh không thay thế các bài đánh giá này.

## Tạo repo và kích hoạt lần đầu

1. Đăng nhập GitHub, tạo repository mới, ví dụ `Tiki_ABSA`. Chọn private/public
   theo nhu cầu; **không** khởi tạo README, `.gitignore` hoặc license trên GitHub
   để repo mới rỗng và dễ push lịch sử local.
2. Mở PowerShell tại thư mục gốc dự án. Kiểm tra các file sắp đưa lên:

```powershell
git status --short
git add --dry-run .
```

`.gitignore` loại `.env`, `.env.*` (giữ file example), `set_env.ps1`, `.venv`,
`.venv-ci`, dữ liệu, model, log và báo cáo sinh ra. Các khóa thật chỉ ở máy bạn.
Không dùng `git add -f` với file bị ignore. Mẫu env được giữ vì CI cần chúng.
Nếu sau này một file bí mật đã được commit, thêm vào `.gitignore` không xóa nó
khỏi lịch sử; cần thu hồi khóa và xử lý lịch sử riêng.

3. Commit và nối repo. Thay URL dưới đây bằng URL repo vừa tạo:

```powershell
git add .
git commit -m "Add application and offline CI pipeline"
git remote add origin https://github.com/YOUR_USERNAME/Tiki_ABSA.git
git push -u origin main
```

Nếu Git báo thiếu danh tính, cấu hình `git config user.name "Tên của bạn"` và
`git config user.email "Email GitHub của bạn"` trong repo rồi chạy lại commit.
Đăng nhập GitHub qua cơ chế Git Credential Manager trên máy; không đặt token vào URL.

4. Mở tab **Actions → CI**, chọn run vừa tạo. Chỉ coi CI trên GitHub đã hoạt động
   sau khi cả bốn check xanh. Nếu lỗi, mở job/step đỏ để đọc log.
5. Tạo nhánh mới, thay đổi code và mở pull request để xác nhận CI cũng chạy cho PR.
   Sau khi có run đầu tiên, có thể cấu hình ruleset cho `main` yêu cầu bốn check này
   thành công trước khi merge (phụ thuộc quyền và tính năng repo GitHub của bạn).

Không cần thêm GitHub Secrets cho workflow hiện tại. CI không triển khai ứng dụng,
không push Docker image lên registry và không cập nhật Qdrant thật.

## Chạy kiểm tra offline ở Windows trước khi push

Cần Python 3.12 và Windows Python launcher (`py`). Tạo venv riêng, không sửa `.venv`
đang chạy dự án:

```powershell
.\scripts\ci.ps1 -Install
```

Những lần sau:

```powershell
.\scripts\ci.ps1
```

Khi requirements thay đổi, chạy lại `-Install`. Lệnh local này chạy static checks
và offline tests; các job Docker/Airflow đầy đủ chạy trên GitHub runner Linux.
Kết quả lưu tại `reports/ci/unit-tests.txt` và `summary.json`.
Trên GitHub, tải artifact `offline-tests-py3.11`, `offline-tests-py3.12`,
`container-smoke` ở trang run; thời gian giữ 7 ngày. Log có thể có thông báo lỗi
provider giả lập có chủ đích: dựa vào trạng thái test cuối cùng để kết luận.

## Khi lỗi CI

- Dependency install/pip check: đối chiếu requirements đã pin và phiên bản Python.
- Unit test đỏ: đọc tên test và traceback trong artifact; sửa code/test rồi push lại.
- DAG import đỏ: kiểm tra API Airflow 3.3.2 và các import trong DAG, không bỏ qua test.
- Compose đỏ: kiểm tra example env và biến bắt buộc; không tải env thật lên GitHub.
- UI build hoặc smoke đỏ: kiểm tra artifact log, response SSE done/error và tên host Docker.
- GitHub chặn Actions/quota: xem Settings → Actions hoặc giới hạn tài khoản; đây là
  điều kiện tài khoản, không phải lỗi code.

Workflow tuân theo cách tổ chức Python CI trong
[tài liệu GitHub Actions](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
