FROM tiki-absa-airflow:3.3.2 AS ml
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
COPY --from=ml /opt/tiki-venv /opt/tiki-venv
# The source venv used the Airflow image's /usr/python. Rebind to this interpreter.
RUN ln -sf /usr/local/bin/python3.11 /opt/tiki-venv/bin/python \
    && ln -sf /usr/local/bin/python3.11 /opt/tiki-venv/bin/python3 \
    && ln -sf /usr/local/bin/python3.11 /opt/tiki-venv/bin/python3.11
COPY requirements-api.txt /tmp/requirements-api.txt
RUN /opt/tiki-venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements-api.txt \
    && /opt/tiki-venv/bin/python -m pip check
WORKDIR /opt/tiki
COPY --chown=app:app source/ ./source/
RUN mkdir -p logs && chown app:app logs
USER app
ENV PYTHONPATH=/opt/tiki PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
EXPOSE 8000
CMD ["/opt/tiki-venv/bin/python", "-m", "uvicorn", "source.chatbot.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
