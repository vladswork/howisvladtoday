import os
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Strava Dashboard API", root_path="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://howisvlad.today"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "strava_db"),
        user=os.getenv("DB_USER", "strava_user"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=RealDictCursor,
    )


@app.get("/activities")
def get_activities(
    type: Optional[str] = None,
    after: Optional[date] = None,
    before: Optional[date] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
):
    """List activities with optional filters."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []

            if type:
                conditions.append("type = %s")
                params.append(type)
            if after:
                conditions.append("start_date_local >= %s")
                params.append(after)
            if before:
                conditions.append("start_date_local <= %s")
                params.append(before)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            cur.execute(f"""
                SELECT id, name, type, sport_type, start_date_local, distance,
                       moving_time, elapsed_time, total_elevation_gain,
                       average_speed, max_speed, average_heartrate, max_heartrate,
                       calories, suffer_score, average_cadence
                FROM activities
                {where}
                ORDER BY start_date_local DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])

            return cur.fetchall()
    finally:
        conn.close()


@app.get("/stats")
def get_stats(year: Optional[int] = None):
    """Summary statistics, optionally filtered by year."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            year_filter = ""
            params = []
            if year:
                year_filter = "WHERE EXTRACT(YEAR FROM start_date_local) = %s"
                params.append(year)

            cur.execute(f"""
                SELECT
                    type,
                    COUNT(*) as activity_count,
                    ROUND(SUM(distance)::numeric / 1000, 1) as total_km,
                    ROUND(SUM(moving_time)::numeric / 3600, 1) as total_hours,
                    ROUND(AVG(distance)::numeric / 1000, 1) as avg_km,
                    ROUND(MAX(distance)::numeric / 1000, 1) as max_km,
                    ROUND(SUM(total_elevation_gain)::numeric, 0) as total_elevation_m,
                    ROUND(AVG(average_heartrate)::numeric, 0) as avg_hr
                FROM activities
                {year_filter}
                GROUP BY type
                ORDER BY activity_count DESC
            """, params)

            return cur.fetchall()
    finally:
        conn.close()


@app.get("/weekly")
def get_weekly(
    type: Optional[str] = None,
    year: Optional[int] = None,
):
    """Weekly aggregated distance and time for mileage charts."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []

            if type:
                conditions.append("type = %s")
                params.append(type)
            if year:
                conditions.append("EXTRACT(YEAR FROM start_date_local) = %s")
                params.append(year)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            cur.execute(f"""
                SELECT
                    DATE_TRUNC('week', start_date_local)::date as week,
                    type,
                    COUNT(*) as activity_count,
                    ROUND(SUM(distance)::numeric / 1000, 1) as total_km,
                    ROUND(SUM(moving_time)::numeric / 3600, 1) as total_hours
                FROM activities
                {where}
                GROUP BY week, type
                ORDER BY week
            """, params)

            return cur.fetchall()
    finally:
        conn.close()


@app.get("/pace")
def get_pace(
    min_distance: float = Query(default=0, description="Min distance in km"),
):
    """Pace data for running activities over time."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id,
                    name,
                    start_date_local,
                    ROUND(distance::numeric / 1000, 2) as distance_km,
                    moving_time,
                    ROUND((moving_time::numeric / 60) / NULLIF(distance / 1000, 0), 2) as pace_min_per_km,
                    average_heartrate,
                    total_elevation_gain
                FROM activities
                WHERE type = 'Run'
                  AND distance > 0
                  AND distance / 1000 >= %s
                ORDER BY start_date_local
            """, [min_distance])

            return cur.fetchall()
    finally:
        conn.close()


@app.get("/calendar")
def get_calendar(year: Optional[int] = None):
    """Daily activity data for calendar heatmap."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            year_filter = ""
            params = []
            if year:
                year_filter = "WHERE EXTRACT(YEAR FROM start_date_local) = %s"
                params.append(year)

            cur.execute(f"""
                SELECT
                    start_date_local::date as date,
                    COUNT(*) as activity_count,
                    ROUND(SUM(distance)::numeric / 1000, 1) as total_km,
                    ROUND(SUM(moving_time)::numeric / 60, 0) as total_minutes,
                    ARRAY_AGG(DISTINCT type) as types
                FROM activities
                {year_filter}
                GROUP BY date
                ORDER BY date
            """, params)

            return cur.fetchall()
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok"}
