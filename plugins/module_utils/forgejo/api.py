import re
from typing import Dict, List, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ForgejoApi:
    """
    Forgejo API Client:
    - Unterstützt Token Auth (empfohlen)
    - Fällt zurück auf Basic Auth (username+password), wenn kein Token gesetzt ist
    """

    def __init__(
        self,
        module: any,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """
        :param base_url: z.B. "https://codeberg.org/api/v1"
        :param username: Admin-Benutzername (nur für Basic Auth)
        :param password: Admin-Passwort (nur für Basic Auth)
        :param token: Optionaler Admin-Token
        """
        self.module = module
        # self.module.log(
        #     f"ForgejoApi::__init__(base_url: {base_url}, username: {username}, password: {password}, token: {token})"
        # )

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        # Retry Setup
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Auth
        self.auth = None
        self.headers: Dict[str, str] = {"Accept": "application/json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
        elif username and password:
            self.auth = (username, password)
        else:
            raise ValueError("Token oder Username+Passwort erforderlich")

    # ---------------------------
    # Generic HTTP Methods
    # ---------------------------
    def _get(self, path: str, params: Optional[dict] = None) -> List[dict]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: Optional[dict] = None) -> dict:
        return self._request("POST", path, json=json)

    def _patch(self, path: str, json: Optional[dict] = None) -> dict:
        return self._request("PATCH", path, json=json)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    # --------------------------------------------------------------------------------
    def users(self) -> List[dict]:
        """
        Ruft alle User aus /admin/users ab (mit Pagination)
        """
        # self.module.log(msg="ForgejoApi::users()")

        endpoint = f"{self.base_url}/admin/users"
        status, users, error = self._request(endpoint)

        if status == 200:
            print(f"{len(users)} Users gefunden")
            return users
        else:
            print(f"Fehler: {error}")
            return []

    # --------------------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> tuple[int, Union[List[dict], dict, str]]:
        """ """
        # self.module.log(
        #     f"ForgejoApi::_request(method: {method}, path: {path}, params: {params}, json: {json})"
        # )

        url = f"{self.base_url}{path}"
        result = []
        status_code = 0

        while url:
            resp = self.session.request(
                method,
                url,
                headers=self.headers,
                params=params,
                json=json,
                auth=self.auth,
                timeout=15,
            )

            status_code = resp.status_code

            try:
                data = resp.json()
            except ValueError:
                data = resp.text

            # Fehler explizit loggen – Forgejo liefert {"message": "..."} bei 4xx
            if not resp.ok:
                error_msg = (
                    data.get("message", data) if isinstance(data, dict) else data
                )
                self.module.log(
                    f"API Error {status_code} on {method} {path}: {error_msg}"
                )
                resp.raise_for_status()  # wirft HTTPError mit Details

            if method != "GET":
                return status_code, data

            if isinstance(data, list):
                result.extend(data)
            else:
                result.append(data)

            link_header = resp.headers.get("Link", "")
            match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
            url = match.group(1) if match else None
            params = None

        return status_code, result


"""
if __name__ == "__main__":
    BASE_URL = "https://codeberg.org/api/v1"

    # Beispiel 1: Mit Token
    # forgejo = Forgejo(BASE_URL, token="DEIN_ADMIN_TOKEN")

    # Beispiel 2: Mit Basic Auth
    forgejo = Forgejo(BASE_URL, username="DEIN_ADMIN_USER", password="DEIN_PASSWORT")

    users = forgejo.users()

    for user in users:
        print(f"{user['id']:3}  {user['username']:20}  {user.get('email', '-')}")
"""
