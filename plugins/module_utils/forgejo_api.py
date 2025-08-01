
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Tuple, Union, List, Dict


class ForgejoApi:
    """
    Forgejo API Client:
    - Unterstützt Token Auth (empfohlen)
    - Fällt zurück auf Basic Auth (username+password), wenn kein Token gesetzt ist
    """
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None
    ):
        """
        :param base_url: z.B. "https://codeberg.org/api/v1"
        :param username: Admin-Benutzername (nur für Basic Auth)
        :param password: Admin-Passwort (nur für Basic Auth)
        :param token: Optionaler Admin-Token
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        # Retry Setup
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PATCH", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Auth
        self.auth = None
        self.headers: Dict[str, str] = {
            "Accept": "application/json"
        }
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
        url: str,
        params: Optional[dict] = None,
    ) -> Tuple[int, Union[List[dict], str], Optional[str]]:
        """
        GET-Anfrage mit Retry und Pagination
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)

        result: List[dict] = []
        error = None

        try:
            while url:
                response = session.get(
                    url,
                    headers=self.headers,
                    params=params,
                    auth=self.auth,  # wird nur gesetzt, wenn kein Token
                    timeout=15
                )
                response.raise_for_status()

                json_data = response.json()
                if isinstance(json_data, list):
                    result.extend(json_data)
                else:
                    result.append(json_data)

                # Pagination prüfen
                link_header = response.headers.get("Link")
                next_url = None
                if link_header:
                    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
                    if match:
                        next_url = match.group(1)

                url = next_url
                params = None

        except requests.exceptions.RequestException as e:
            error = f"Request failed: {e}"
            return (419, [], error)
        except ValueError as e:
            error = f"Error parsing the JSON: {e}"
            return (419, [], error)

        return (200, result, None)


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
