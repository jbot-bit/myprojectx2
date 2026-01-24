import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PROJECTX_BASE_URL")
USERNAME = os.getenv("PROJECTX_USERNAME")
API_KEY = os.getenv("PROJECTX_API_KEY")
LIVE = os.getenv("PROJECTX_LIVE", "false").lower() == "true"


class ProjectXClient:
    def __init__(self):
        self.token = None
        self.headers = {"Accept": "text/plain"}

    def login(self):
        url = f"{BASE_URL}/api/Auth/loginKey"
        payload = {
            "userName": USERNAME,
            "apiKey": API_KEY,
        }

        with httpx.Client() as client:
            r = client.post(url, json=payload, headers=self.headers)
            r.raise_for_status()
            data = r.json()

        if not data.get("success"):
            raise RuntimeError(f"Login failed: {data}")

        self.token = data["token"]
        self.headers["Authorization"] = f"Bearer {self.token}"

    def get_active_mgc_contract_info(self):
        url = f"{BASE_URL}/api/Contract/search"
        payload = {"searchText": "MGC", "live": LIVE}

        with httpx.Client() as client:
            r = client.post(url, json=payload, headers=self.headers)
            r.raise_for_status()
            data = r.json()

        contracts = data.get("contracts", [])
        active = [c for c in contracts if c.get("activeContract")]

        if not active:
            raise RuntimeError("No active MGC contract found")

        c = active[0]
        return {"contract_id": c["id"], "source_symbol": c.get("name")}


    def retrieve_1m_bars(self, contract_id, start_utc, end_utc):
        url = f"{BASE_URL}/api/History/retrieveBars"
        payload = {
            "contractId": contract_id,
            "live": LIVE,
            "startTime": start_utc,
            "endTime": end_utc,
            "unit": 2,
            "unitNumber": 1,
            "limit": 20000,
            "includePartialBar": False,
        }

        with httpx.Client() as client:
            r = client.post(url, json=payload, headers=self.headers)
            r.raise_for_status()
            return r.json()["bars"]
