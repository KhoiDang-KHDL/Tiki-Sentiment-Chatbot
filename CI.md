# Continuous Integration

Workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
Runs: [GitHub Actions](https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot/actions/workflows/ci.yml).

## Triggers và jobs

Triggers: `push`, `pull_request`, `workflow_dispatch`. Run cũ cùng ref bị hủy khi có run mới.
Token permissions: `contents: read`. Không yêu cầu repository secrets.

| Job | Kiểm tra |
|---|---|
| Offline tests — Python 3.11/3.12 | Install/pip check, compile Python, YAML/TOML/JSON, unittest |
| Airflow DAG import | DAG/queue tests trong official Airflow 3.3.2, network disabled |
| Docker and monitoring smoke | actionlint, Compose validation, promtool, UI build, synthetic API build, HTTP/SSE/metrics, UI → API |

Offline suite dùng temporary files, mocked providers/predictors và Qdrant in-memory.
DAG test skip trong Python thường được chạy bởi job Airflow riêng.
Container jobs dùng port 18000/18001 trên runner và được dọn sau run.

## Chạy local

Python 3.12 và Windows Python launcher `py`:

```powershell
.\scripts\ci.ps1 -Install   # Tạo .venv-ci, cài dependency và chạy checks
.\scripts\ci.ps1           # Các lần tiếp theo
```

`-Install` cần chạy lại khi requirements thay đổi. Venv CI độc lập với `.venv` của ứng dụng.
Local script chạy static checks/offline tests; Docker/Airflow jobs chạy trên Linux runner.

## Development flow

```powershell
git switch -c docs/update-guide
# Sửa code hoặc tài liệu
git add README.md
git commit -m "Describe the change"
git push -u origin HEAD
```

Mở pull request vào `main`, kiểm tra đủ bốn status checks trước khi merge.
Có thể cấu hình branch ruleset yêu cầu các checks này nếu repository hỗ trợ.
Mỗi thay đổi trên `main` cũng kích hoạt CI.

## Artifacts

| Artifact | Nội dung |
|---|---|
| `offline-tests-py3.11`, `offline-tests-py3.12` | `unit-tests.txt`, `summary.json` |
| `container-smoke` | API/UI container logs |

Retention: 7 ngày. Kết quả local: `reports/ci/` (gitignored).

## Failure handling

| Step lỗi | Kiểm tra |
|---|---|
| Install/pip check | Requirements và phiên bản Python |
| Unit tests | Test name, traceback và summary artifact |
| DAG import | Airflow SDK/import và DAG settings |
| Compose/promtool | Example env, service config và alert rules |
| Container smoke | API/UI logs, host nội bộ, SSE `done`/`error` |
| Push protection | Xóa secret khỏi commit chưa push; không bypass cảnh báo |

`.gitignore` loại env thật, `set_env.ps1`, data, models, venv và generated reports.
File đã được track không tự bị loại khỏi lịch sử khi thêm vào `.gitignore`.

## Phạm vi

CI validate Compose bằng example env và chạy `docker/ci.Dockerfile` với API fixture.
Chưa build toàn bộ ML/API production image, kiểm tra checkpoint thật, chấm điểm ABSA/RAG,
gọi provider thật hoặc deploy. CI không cập nhật KB và không push image lên registry.
