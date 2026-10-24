# Tiki ABSA

[![CI](https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/KhoiDang-KHDL/Tiki-Sentiment-Chatbot/actions/workflows/ci.yml)

Chatbot sản phẩm Tiki kết hợp phân tích cảm xúc theo khía cạnh (ABSA), Qdrant,
FastAPI và Chainlit. Airflow điều phối cập nhật Knowledge Base incremental.

## Tài liệu

- [Chạy hệ thống bằng Docker Compose](DOCKER.md)
- [Continuous Integration bằng GitHub Actions](CI.md)
- [Cập nhật Knowledge Base incremental](source/knowledge_base/INCREMENTAL.md)
- [Setup và vận hành Airflow](airflow/README.md)
- [Prometheus, Grafana và kiểm tra tải Locust](monitoring/README.md)

Luồng phục vụ hiện tại: trình duyệt → Chainlit → HTTP API → retrieval/Qdrant → LLM.
UI production không chạy model trực tiếp. API/ML và UI có image riêng.
CI offline kiểm tra code và fixture; không chứng minh độ chính xác model hay
khả năng hoạt động của khóa/quota LLM thật. Các checkpoint, dữ liệu và secrets
không được lưu trong Git; làm theo hướng dẫn Docker để setup môi trường riêng.

## Kiểm tra trước khi push

```powershell
.\scripts\ci.ps1 -Install
```

GitHub Actions chạy khi push/PR tại repo `KhoiDang-KHDL/Tiki-Sentiment-Chatbot`.
Xem `CI.md` để tạo repo mới, đọc kết quả và biết phạm vi CI hiện tại.
