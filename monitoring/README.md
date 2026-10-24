# Monitoring và load testing

## Services

| Service | Địa chỉ mặc định | Cấu hình |
|---|---|---|
| Grafana | [Dashboard](http://localhost:3000/d/tiki-api) | `grafana/provisioning/`, `grafana/dashboards/tiki-api.json` |
| Prometheus | [Targets](http://localhost:9090/targets), [Alerts](http://localhost:9090/alerts) | `prometheus.yml`, `alerts.yml` |
| Locust | [Web UI](http://localhost:8089) | `tests/load_test.py`, profile `loadtest` |

Prometheus scrape mỗi 5 giây; retention 15 ngày. Prometheus/Grafana dùng persistent volumes.
Port chỉ bind loopback. Full stack setup: [DOCKER.md](../DOCKER.md).

```powershell
.\scripts\monitoring.ps1 start
.\scripts\monitoring.ps1 check
.\scripts\monitoring.ps1 password
.\scripts\monitoring.ps1 locust
```

Grafana mặc định user `admin`; password trong `.env.monitoring`.
`monitoring.ps1 setup` dùng khi bổ sung monitoring vào stack đã chuẩn bị.
Provisioning đọc dashboard JSON từ repo. Đổi env password không đổi tài khoản đã khởi tạo
trong database Grafana.

## Metrics và dashboard

Dashboard có 14 panel; selector `Target` tách `tiki-api` (thật) và `tiki-loadtest` (fixture).
Chọn khoảng thời gian có traffic; `Chưa có mẫu` nghĩa là chưa có dữ liệu metric tương ứng.

| Metric | Định nghĩa |
|---|---|
| `tiki_http_requests_total` | Completed requests theo method/route/status |
| `tiki_http_request_duration_seconds` | Toàn bộ response, gồm SSE body |
| `tiki_http_requests_in_progress` | HTTP requests đang xử lý |
| `tiki_stream_outcomes_total` | completed/provider_error/internal_error/cancelled/preflight_error |
| `tiki_stream_first_token_seconds` | Handler start → token đầu; gồm retrieval và queue |
| `tiki_stream_duration_seconds` | Handler start → kết thúc stream |
| `tiki_streams_in_progress` | Stream generators đang chạy |

Custom HTTP metrics loại `/health` và `/metrics`; labels không chứa query/product ID.
HTTP 200 có thể chứa SSE `error`; theo dõi thêm stream outcomes.
CPU/RAM trên dashboard là của tiến trình API, không đại diện toàn host/Qdrant.

## Alert rules

| Rule | Điều kiện duy trì |
|---|---|
| API down | Target `tiki-api` down 1 phút |
| HTTP errors | 5xx ratio >5% trong 2 phút |
| Stream failures | Non-completed stream ratio >5% trong 2 phút |
| Slow responses | HTTP p95 >10 giây trong 2 phút |

Rate/histogram rules dùng cửa sổ 5 phút. Rule hiển thị tại Prometheus;
chưa cấu hình Alertmanager hoặc notification channel.
`tiki-loadtest` DOWN là bình thường khi profile loadtest chưa chạy.

## Locust CLI

Synthetic test, không dùng dữ liệu KB hoặc provider:

```powershell
.\scripts\loadtest.ps1 -Target synthetic -Scenario mixed -Users 10 -Seconds 30 -P95Milliseconds 2000
```

Retrieval thật sau 3 request warm-up:

```powershell
.\scripts\loadtest.ps1 -Target real -Scenario search -Users 1 -Seconds 45 -WarmupRequests 3
.\scripts\loadtest.ps1 -Target real -Scenario search -Users 5 -Seconds 45 -WarmupRequests 3
```

| Parameter | Phạm vi / mặc định |
|---|---|
| `Scenario` | health/search/chat/stream/mixed; mặc định mixed |
| `Target` | synthetic/real; mặc định synthetic |
| `Users`, `Seconds` | 1–100 / 10–600; mặc định 5 / 30 |
| `SpawnRate` | 1–10; mặc định 1 |
| `WarmupRequests` | 0–20; mặc định 0; chỉ gọi search |
| `P95Milliseconds` | Mặc định 10.000 |
| `AllowLiveLlm` | Cho phép chat/stream/mixed thật, có gửi context và dùng quota provider |

Mỗi user nghỉ 0,3–0,8 giây sau request; đây là closed-loop workload, không phải fixed RPS.
Bỏ warm-up để đo cả request đầu. Synthetic dùng header `X-Tiki-Loadtest: synthetic`,
không mount key/model/data; không dùng kết quả fixture để suy ra năng lực model thật.

## Locust UI

Chọn một user class, nhập users/spawn rate, Start rồi Stop khi đủ thời gian.

| Mục tiêu | Host | Class |
|---|---|---|
| Fixture mặc định | `http://api-loadtest:8000` | `MixedUser` hoặc class riêng |
| Retrieval thật | `http://api:8000` | `SearchUser` |

LLM thật bị chặn mặc định; chỉ bật khi chủ động cho phép sử dụng provider.

## Reports và acceptance

Output: `reports/loadtest/<timestamp>-<target>-<scenario>-u<users>/` (gitignored).

| File | Nội dung |
|---|---|
| `report.html` | Locust charts/report |
| `summary.json` | RPS, errors, p50/p95, TTFT, thresholds và passed |
| `requests.csv` | Final aggregate theo endpoint |
| `warmup.json` | Warm-up samples, nếu có; không tính vào bài đo |

Exit 1 nếu failure ratio >1%, p95 vượt ngưỡng, không có request hoặc live LLM bị chặn.
Đây là test thresholds, chưa phải production SLO. Tổng request gồm health khi user start;
đọc hàng endpoint riêng khi đánh giá latency. Locust TTFT chỉ gồm stream hoàn tất;
đọc kèm failure count. SSE error, thiếu done hoặc completion rỗng đều là failure.

Locust percentiles và Prometheus histogram quantiles là các phép ước lượng khác nhau.
Ghi rõ warm/cold, môi trường, concurrency, duration và số mẫu trong báo cáo.

Nếu dashboard rỗng: kiểm tra target UP, selector và time range. Nếu test fail: đọc
`summary.json` trước khi điều chỉnh threshold. Không reset Qdrant để sửa monitoring.
