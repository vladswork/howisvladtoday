import os
import json
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

from strava.client import StravaClient

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def create_tables(conn):
    """Create tables if they don't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id              BIGINT PRIMARY KEY,
                athlete_id      BIGINT NOT NULL,
                name            TEXT,
                type            TEXT NOT NULL,
                sport_type      TEXT,
                start_date      TIMESTAMP WITH TIME ZONE,
                start_date_local TIMESTAMP WITHOUT TIME ZONE,
                timezone        TEXT,
                distance        DOUBLE PRECISION,
                moving_time     INTEGER,
                elapsed_time    INTEGER,
                total_elevation_gain DOUBLE PRECISION,
                average_speed   DOUBLE PRECISION,
                max_speed       DOUBLE PRECISION,
                average_heartrate DOUBLE PRECISION,
                max_heartrate   DOUBLE PRECISION,
                calories        DOUBLE PRECISION,
                suffer_score    INTEGER,
                average_cadence DOUBLE PRECISION,
                gear_id         TEXT,
                description     TEXT,
                raw_json        JSONB,
                synced_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS activity_streams (
                activity_id     BIGINT REFERENCES activities(id),
                stream_type     TEXT NOT NULL,
                data            JSONB NOT NULL,
                PRIMARY KEY (activity_id, stream_type)
            );

            CREATE TABLE IF NOT EXISTS sync_log (
                id              SERIAL PRIMARY KEY,
                started_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                finished_at     TIMESTAMP WITH TIME ZONE,
                status          TEXT DEFAULT 'running',
                activities_synced INTEGER DEFAULT 0,
                error_message   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(type);
            CREATE INDEX IF NOT EXISTS idx_activities_start_date ON activities(start_date);
            CREATE INDEX IF NOT EXISTS idx_activities_athlete_id ON activities(athlete_id);
        """)
    conn.commit()


def get_last_sync_timestamp(conn):
    """Get the most recent activity start_date from the database."""
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(EXTRACT(EPOCH FROM start_date)) FROM activities")
        result = cur.fetchone()[0]
        return float(result) if result else None


def upsert_activity(cur, activity):
    """Insert or update a single activity."""
    cur.execute("""
        INSERT INTO activities (
            id, athlete_id, name, type, sport_type, start_date, start_date_local,
            timezone, distance, moving_time, elapsed_time, total_elevation_gain,
            average_speed, max_speed, average_heartrate, max_heartrate,
            calories, suffer_score, average_cadence, gear_id, description, raw_json
        ) VALUES (
            %(id)s, %(athlete_id)s, %(name)s, %(type)s, %(sport_type)s,
            %(start_date)s, %(start_date_local)s, %(timezone)s, %(distance)s,
            %(moving_time)s, %(elapsed_time)s, %(total_elevation_gain)s,
            %(average_speed)s, %(max_speed)s, %(average_heartrate)s,
            %(max_heartrate)s, %(calories)s, %(suffer_score)s,
            %(average_cadence)s, %(gear_id)s, %(description)s, %(raw_json)s
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            raw_json = EXCLUDED.raw_json,
            synced_at = NOW()
    """, {
        "id": activity["id"],
        "athlete_id": activity["athlete"]["id"],
        "name": activity.get("name"),
        "type": activity.get("type"),
        "sport_type": activity.get("sport_type"),
        "start_date": activity.get("start_date"),
        "start_date_local": activity.get("start_date_local"),
        "timezone": activity.get("timezone"),
        "distance": activity.get("distance"),
        "moving_time": activity.get("moving_time"),
        "elapsed_time": activity.get("elapsed_time"),
        "total_elevation_gain": activity.get("total_elevation_gain"),
        "average_speed": activity.get("average_speed"),
        "max_speed": activity.get("max_speed"),
        "average_heartrate": activity.get("average_heartrate"),
        "max_heartrate": activity.get("max_heartrate"),
        "calories": activity.get("calories"),
        "suffer_score": activity.get("suffer_score"),
        "average_cadence": activity.get("average_cadence"),
        "gear_id": activity.get("gear_id"),
        "description": activity.get("description"),
        "raw_json": Json(activity),
    })


def upsert_streams(cur, activity_id, streams):
    """Insert or update activity streams."""
    for stream in streams:
        cur.execute("""
            INSERT INTO activity_streams (activity_id, stream_type, data)
            VALUES (%s, %s, %s)
            ON CONFLICT (activity_id, stream_type) DO UPDATE SET data = EXCLUDED.data
        """, (activity_id, stream["type"], Json(stream["data"])))


def sync(full=False, fetch_streams=False):
    """Main sync function.

    Args:
        full: If True, fetch all activities. Otherwise, incremental.
        fetch_streams: If True, also fetch time-series data for each activity.
    """
    conn = get_db_connection()
    create_tables(conn)

    # Log the sync start
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_log (status) VALUES ('running') RETURNING id"
        )
        sync_id = cur.fetchone()[0]
    conn.commit()

    try:
        client = StravaClient()

        after = None
        if not full:
            after = get_last_sync_timestamp(conn)
            if after:
                print(f"[INFO] Incremental sync: fetching activities after {datetime.fromtimestamp(after, tz=timezone.utc)}")
            else:
                print("[INFO] No existing activities found. Running full sync.")

        count = 0
        with conn.cursor() as cur:
            for activity in client.get_activities(after=after):
                upsert_activity(cur, activity)
                count += 1

                if fetch_streams:
                    streams = client.get_activity_streams(activity["id"])
                    if streams:
                        upsert_streams(cur, activity["id"], streams)

                if count % 10 == 0:
                    conn.commit()
                    print(f"[INFO] Synced {count} activities...")

        conn.commit()

        # Log success
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_log SET status = 'success', activities_synced = %s, finished_at = NOW() WHERE id = %s",
                (count, sync_id),
            )
        conn.commit()
        print(f"[DONE] Synced {count} activities successfully.")

    except Exception as e:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_log SET status = 'failed', error_message = %s, finished_at = NOW() WHERE id = %s",
                (str(e), sync_id),
            )
        conn.commit()
        print(f"[ERROR] Sync failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync Strava activities to PostgreSQL")
    parser.add_argument("--full", action="store_true", help="Full sync (all activities)")
    parser.add_argument("--streams", action="store_true", help="Also fetch activity streams")
    args = parser.parse_args()

    sync(full=args.full, fetch_streams=args.streams)
