"""
Memory Hub Client — read/write agent insights during group chat.
"""

import os
import json
import urllib.request
import urllib.error

HUB_URL = os.environ.get("MEMORY_HUB_URL", "http://127.0.0.1:8921")


class HubClient:
    def __init__(self, url: str = None):
        self.url = url or HUB_URL

    def _api(self, method, endpoint, body=None):
        url = f"{self.url}{endpoint}"
        data_bytes = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(
            url, data=data_bytes, method=method,
            headers={"Content-Type": "application/json"} if data_bytes else {}
        )
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            return json.loads(resp.read())
        except Exception:
            return None

    def share_insight(self, content, source="workshop", lens="general", confidence="observed"):
        """Agent discovers something about 泡芙 during chat → write to Hub."""
        return self._api("POST", "/insight", {
            "content": content,
            "source": source,
            "lens": lens,
            "confidence": confidence,
            "priority": "P2",
        })

    def pull_profile(self, lens=None):
        """Agent needs context about 泡芙 before responding."""
        endpoint = f"/profile?lens={lens}" if lens else "/profile"
        return self._api("GET", endpoint)

    def get_stats(self):
        """Get Memory Hub statistics for dashboard."""
        sources = self._api("GET", "/sources")
        return {
            "sources": sources or {},
            "hub_url": self.url,
            "connected": sources is not None,
        }
