#
# import re
# import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict


class Forgejo:
    """
    """
    def __init__(self, module: any, url: str):
        """
        Initialisiert die Klasse
        """
        self.module = module
        self.module.log(msg="Forgejo::__init__(module)")

        self.url = url
        self.headers: Dict[str, str] = {
            "Accept": "application/json"
        }

    def users(self):
        """
            GET 'https://codeberg.org/api/v1/admin/users' -H 'accept: application/json'
        """
        self.module.log(msg="Forgejo::users()")

        params = {}
        _users = self._request(self.url, params)

        self.module.log(msg=f"users: {_users}")

        pass

    # ------------------------------------------------------------------------------------------
    # private API
    def _request(
        self,
        url: str,
        params: Optional[dict] = None,
    ) -> Tuple[int, Union[List[dict], str, requests.Response], Optional[str]]:
        """
        Robuste GET-Anfrage mit:
        - Retry bei 5xx und Timeout
        - Pagination über Link-Header
        - Rate Limit Handling
        - JSON oder plain text/streaming Download
        """
        self.module.log(msg=f"Forgejo::_request(url={url}, params={params})")

        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        headers = self.headers.copy()
        result: List[dict] = []
        error = None

        try:
            response = session.get(self.url, headers=headers, params=params, timeout=15)

            response.raise_for_status()

            # Wenn kein JSON erwartet wird (z. B. Datei-Download)
            # return (200, response.text, None)

            # JSON-Verarbeitung
            json_data = response.json()
            if not isinstance(json_data, list):
                json_data = [json_data]
            result.extend(json_data)

        except requests.exceptions.RequestException as e:
            error = f"Request failed: {e}"
            self.module.log(error)
            return (419, [], error)
        except ValueError as e:
            error = f"Error parsing the JSON: {e}"
            self.module.log(error)
            return (419, [], error)

        return (200, result, None)
