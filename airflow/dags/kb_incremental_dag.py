"""One sequential writer. Heavy ML imports run only in the isolated subprocess."""
from datetime import timedelta
import os

import pendulum
from airflow.sdk import dag, task


@dag(
    dag_id="tiki_kb_incremental",
    description="Process immutable CSV batches; resume pending KB updates before new data",
    schedule=os.getenv("KB_SCHEDULE", "*/15 * * * *"),
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    is_paused_upon_creation=True,
    default_args={"owner": "tiki-absa", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["tiki", "incremental", "local"],
)
def kb_incremental():
    @task(execution_timeout=timedelta(hours=2))
    def process_batches():
        from source.orchestration.airflow_batches import QueueConfig, process_queue
        return process_queue(QueueConfig.from_env())

    @task
    def report(summary):
        import json
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary["completed_batches"]

    report(process_batches())


kb_incremental()
