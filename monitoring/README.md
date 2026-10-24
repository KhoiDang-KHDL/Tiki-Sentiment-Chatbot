# Prometheus, Grafana và Locust

Chạy các lệnh PowerShell dưới đây tại thư mục gốc `Tiki_ABSA`, khi Docker Desktop đang bật.
Stack hiện tại đã được setup và kiểm tra ngày 23/10/2026. Kết quả đo nằm trong
[reports/loadtest/RESULTS.md](../reports/loadtest/RESULTS.md).

## Mở và khởi động lại

```powershell
.\scripts\stack.ps1 start
.\scripts\monitoring.ps1 start
.\scripts\monitoring.ps1 check
.\scripts\monitoring.ps1 locust
```

| Dịch vụ | Địa chỉ | Công dụng |
|---|---|---|
| Grafana | http://localhost:3000/d/tiki-api | Dashboard API và streaming |
| Prometheus | http://localhost:9090/targets | Kiểm tra scrape target UP |
| Prometheus alerts | http://localhost:9090/alerts | Trạng thái các rule cảnh báo |
| Locust | http://localhost:8089 | Tạo tải tương tác |

Grafana dùng tài khoản `admin`; lấy mật khẩu trên máy bằng:

```powershell
.\scripts\monitoring.ps1 password
```

Mật khẩu được sinh ngẫu nhiên trong `.env.monitoring`, file này được gitignore.
Không đưa file này lên GitHub. Nếu chuyển sang máy mới, chạy
`.\scripts\monitoring.ps1 setup` sau khi đã setup stack API/Airflow.
Grafana lưu dashboard provisioning từ file; sửa JSON trong repo để thay đổi lâu dài.
Thay mật khẩu trong env sau lần khởi tạo đầu không tự đổi mật khẩu tài khoản đã lưu
trong database Grafana.

## Đọc dashboard

Chọn **Target = tiki-api** để xem API thật và **tiki-loadtest** để xem fixture giả lập.
Hai target tách biệt; không dùng tốc độ giả lập để kết luận tốc độ embedding hay LLM thật.
Dashboard có 14 panel: availability, throughput, HTTP 5xx, request đang chạy,
status code, p50/p95, thời gian đến token đầu (TTFT), kết quả stream, thời gian stream,
CPU và bộ nhớ của tiến trình API. Chọn khoảng thời gian có chạy test để thấy dữ liệu.
`Chưa có mẫu` là bình thường khi chưa gọi endpoint tương ứng.

- HTTP latency tính đến khi gửi hết response, gồm toàn bộ body SSE.
- HTTP 200 vẫn có thể chứa SSE `error`; xem thêm `Stream outcomes`.
- TTFT đo đến token đầu, chỉ có mẫu khi stream đã phát token. Locust tổng hợp TTFT
  của các stream hoàn tất, nên cần đọc cùng số stream lỗi.
- `/health` và `/metrics` được loại khỏi bộ đếm HTTP tùy chỉnh để không làm đẹp
  kết quả bởi traffic scrape. Locust vẫn ghi health khi khởi tạo người dùng.
- CPU/RAM là của tiến trình API, không đại diện toàn bộ Docker host hay Qdrant.
- Nhãn metric dùng route/status/outcome; không chứa câu hỏi hay ID sản phẩm.

Prometheus scrape mỗi 5 giây, giữ dữ liệu 15 ngày trong volume riêng. Grafana có
volume riêng. Port monitoring/Locust chỉ bind loopback trên máy này.
Rule trong `alerts.yml` phát hiện API down, 5xx cao, lỗi stream cao và p95 chậm.
Hiện rule hiển thị tại Prometheus; chưa cấu hình Alertmanager hay gửi email/Slack.
Target giả lập có thể DOWN khi profile `loadtest` chưa bật; rule availability chỉ
áp dụng API thật.

## Chạy Locust bằng script và xuất báo cáo

Kiểm tra luồng chat/stream bằng fixture riêng, không gọi provider hoặc ghi KB:

```powershell
.\scripts\loadtest.ps1 -Target synthetic -Scenario mixed -Users 10 -Seconds 30 -P95Milliseconds 2000
```

Kiểm tra retrieval thật (embedding và Qdrant) sau 3 request warm-up:

```powershell
.\scripts\loadtest.ps1 -Target real -Scenario search -Users 1 -Seconds 45 -WarmupRequests 3
.\scripts\loadtest.ps1 -Target real -Scenario search -Users 5 -Seconds 45 -WarmupRequests 3
```

Bỏ `-WarmupRequests` để đo cả request đầu. Warm-up chỉ gọi `/search`, lưu riêng
trong `warmup.json` và không cộng vào thống kê bài đo. Không che lần đo lạnh khi báo cáo.
Scenario hỗ trợ: `health`, `search`, `chat`, `stream`, `mixed`. Users là người dùng
đồng thời; mỗi người đợi ngẫu nhiên 0,3–0,8 giây sau request. Đây là mô hình tải
đóng, không bảo đảm số request/giây cố định. Bắt đầu nhỏ và tăng dần.

Mỗi lần chạy tạo `reports/loadtest/<thời-gian>-<target>-<scenario>-u<số-user>/`:

- `report.html`: báo cáo Locust có biểu đồ.
- `summary.json`: tổng hợp p50/p95, RPS, lỗi, TTFT, ngưỡng và `passed`.
- `requests.csv`: thống kê cuối bài đo theo endpoint.
- `warmup.json`: có khi yêu cầu warm-up.

Script trả lỗi nếu failure ratio vượt 1%, p95 vượt ngưỡng (mặc định 10.000 ms),
không có request hoặc bị chặn gọi LLM thật. Báo cáo vẫn được giữ.
Ngưỡng này là tiêu chí kiểm tra ban đầu, chưa phải cam kết SLO của sản phẩm.
Tổng hợp bao gồm health lúc khởi tạo; dùng hàng `/search` hay `/chat/stream`
trong CSV/JSON khi đánh giá riêng endpoint. Percentile Locust và histogram
Prometheus là ước lượng theo cách khác nhau nên có thể khác nhẹ.

Trong Locust UI, host mặc định là `http://api-loadtest:8000`. Chọn duy nhất class
mong muốn (ví dụ `MixedUser`), nhập users/spawn rate rồi Start; Stop khi đo xong.
Fixture có header `X-Tiki-Loadtest: synthetic`, không dùng khóa LLM hay dữ liệu KB.
Để kiểm tra API thật từ UI, chọn `SearchUser` với host `http://api:8000`.
Chat/stream thật bị chặn mặc định. Script có cờ `-AllowLiveLlm` dành cho lúc bạn
chủ động cho phép gửi context tới provider và sử dụng quota. Lần setup này không
chạy các bài LLM thật.

## Các file triển khai

| File | Vai trò |
|---|---|
| `docker-compose.yml` | Prometheus, Grafana, profile api-loadtest/locust, network và volumes |
| `monitoring/prometheus.yml`, `alerts.yml` | Scrape và rule cảnh báo |
| `monitoring/grafana/provisioning/` | Tự cấu hình datasource/dashboard |
| `monitoring/grafana/dashboards/tiki-api.json` | Dashboard 14 panel |
| `source/chatbot/metrics.py`, `api.py` | Đo request và vòng đời SSE |
| `source/chatbot/loadtest_api.py` | Fixture chạy trong container riêng |
| `tests/load_test.py`, `loadtest_support.py`, `loadtest_warmup.py` | Workload, kiểm tra SSE, warm-up |
| `scripts/monitoring.ps1`, `scripts/loadtest.ps1` | Setup, kiểm tra, chạy tải và xuất báo cáo |

Nếu Prometheus target DOWN, kiểm tra API healthy và Docker network bằng
`.\scripts\monitoring.ps1 status`. Nếu Grafana không có dữ liệu, chọn đúng Target,
mở rộng khoảng thời gian và kiểm tra trang Targets trước. Nếu test trả exit 1,
đọc `summary.json` trước khi tăng timeout/ngưỡng. Không xóa volume Qdrant để xử lý
lỗi monitoring. Các bài đo hiện tại không sửa collection `tiki_kb_test`.
