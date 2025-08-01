
from forge_api import ForgejoAPI
from typing import List

# ---------------------------------------
# Users API (Beispielmodul)
# ---------------------------------------


class ForgejoUsers:
    def __init__(self, api: ForgejoAPI):
        self.api = api

    def list_users(self) -> List[dict]:
        return self.api._get("/admin/users")

    def create_user(self, username: str, email: str, password: str, must_change_password: bool = False) -> dict:
        payload = {
            "username": username,
            "email": email,
            "password": password,
            "must_change_password": must_change_password
        }
        return self.api._post("/admin/users", json=payload)

    def update_user(self, username: str, updates: dict) -> dict:
        return self.api._patch(f"/admin/users/{username}", json=updates)

    def delete_user(self, username: str) -> dict:
        return self.api._delete(f"/admin/users/{username}")


"""
if __name__ == "__main__":
    # Beispiel: Verbindung aufbauen
    api = ForgejoAPI(
        base_url="https://codeberg.org/api/v1",
        username="DEIN_ADMIN_USER",
        password="DEIN_PASSWORT"
        # token="DEIN_TOKEN"  # optional
    )

    users_api = ForgejoUsers(api)

    # Alle User abrufen
    users = users_api.list_users()
    for user in users:
        print(f"{user['id']:3} {user['username']:20} {user.get('email', '-')}")
"""
