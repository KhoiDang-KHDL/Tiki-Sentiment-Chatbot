FROM python:3.11-slim-bookworm
RUN useradd --create-home --uid 10001 app
WORKDIR /opt/tiki
COPY requirements-ui.txt /tmp/requirements-ui.txt
RUN pip install --no-cache-dir -r /tmp/requirements-ui.txt && pip check
COPY --chown=app:app source/chatbot/demo_chainlit.py source/chatbot/demo_chainlit_http.py source/chatbot/api_client.py source/chatbot/container_check.py source/chatbot/monitoring_check.py ./source/chatbot/
COPY --chown=app:app chainlit.md ./chainlit.md
COPY --chown=app:app .chainlit/config.toml ./.chainlit/config.toml
RUN mkdir -p .files && chown -R app:app /opt/tiki
USER app
ENV PYTHONPATH=/opt/tiki PYTHONUNBUFFERED=1 CHAINLIT_NO_TELEMETRY=true
EXPOSE 8001
CMD ["python", "-m", "chainlit", "run", "source/chatbot/demo_chainlit.py", "--host", "0.0.0.0", "--port", "8001", "--headless"]
