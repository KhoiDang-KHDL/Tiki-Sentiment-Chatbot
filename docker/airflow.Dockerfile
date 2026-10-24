FROM apache/airflow:3.3.2-python3.11

USER root
RUN python -m venv /opt/tiki-venv && chown -R airflow:root /opt/tiki-venv
USER airflow
COPY --chown=airflow:root requirements-airflow.txt /tmp/requirements-tiki.txt
RUN /opt/tiki-venv/bin/python -m pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && /opt/tiki-venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements-tiki.txt \
    && /opt/tiki-venv/bin/python -m pip check
WORKDIR /opt/tiki
