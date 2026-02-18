import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Add the parent directory so we can import our sync module
sys.path.insert(0, "/opt/airflow")

default_args = {
    "owner": "vladimir",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="strava_sync",
    default_args=default_args,
    description="Sync Strava activities to PostgreSQL",
    # Run at 8:00 AM UTC every Monday and Thursday
    schedule_interval="0 8 * * 1,4",
    start_date=datetime(2026, 2, 18),
    catchup=False,
    tags=["strava"],
) as dag:

    def run_sync():
        from sync import sync
        sync(full=False, fetch_streams=False)

    sync_task = PythonOperator(
        task_id="sync_strava_activities",
        python_callable=run_sync,
    )
