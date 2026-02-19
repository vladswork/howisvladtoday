import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaClient:
    def __init__(self):
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        self.access_token = None
        self.token_expires_at = 0

    def _ensure_token(self):
        """Refresh the access token if expired."""
        if self.access_token and time.time() < self.token_expires_at - 60:
            return

        response = requests.post(STRAVA_AUTH_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        })
        response.raise_for_status()
        data = response.json()

        self.access_token = data["access_token"]
        self.token_expires_at = data["expires_at"]

        # Update refresh token if Strava rotated it
        if data.get("refresh_token") != self.refresh_token:
            self.refresh_token = data["refresh_token"]
            print(f"[INFO] Refresh token rotated. New token: {self.refresh_token}")
            print("[WARN] Update STRAVA_REFRESH_TOKEN in your .env file!")

    def _get(self, endpoint, params=None):
        """Make an authenticated GET request to the Strava API."""
        self._ensure_token()
        response = requests.get(
            f"{STRAVA_API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def get_activities(self, after=None, per_page=200):
        """Fetch activities, paginating through all results.

        Args:
            after: Unix timestamp. Only return activities after this time.
            per_page: Number of activities per page (max 200).

        Yields:
            Activity dicts from the Strava API.
        """
        page = 1
        while True:
            params = {"per_page": per_page, "page": page}
            if after:
                params["after"] = int(after)

            activities = self._get("/athlete/activities", params=params)

            if not activities:
                break

            for activity in activities:
                yield activity

            if len(activities) < per_page:
                break

            page += 1
            # Be polite to the API
            time.sleep(0.5)

    def get_activity_detail(self, activity_id):
        """Fetch detailed info for a single activity."""
        return self._get(f"/activities/{activity_id}")

    def get_activity_streams(self, activity_id, stream_types=None):
        """Fetch time-series streams for an activity."""
        if stream_types is None:
            stream_types = ["time", "distance", "heartrate", "cadence", "altitude"]

        try:
            return self._get(
                f"/activities/{activity_id}/streams",
                params={"keys": ",".join(stream_types), "key_type": "time"},
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
