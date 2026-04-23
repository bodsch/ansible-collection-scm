#
from typing import List, Optional

from ansible_collections.bodsch.scm.plugins.module_utils.forgejo.api import ForgejoApi

# ---------------------------------------
# Users API (Beispielmodul)
# ---------------------------------------


class ForgejoApiUsers:
    """ """

    def __init__(self, api: ForgejoApi):
        self.api = api
        self.module = api.module

        self.module.log("ForgejoApiUsers::__init(api)")

    def list_users(self) -> List[dict]:
        """ """
        # self.module.log("ForgejoApiUsers::list_users()")

        return self.api._get("/admin/users")

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        must_change_password: bool = False,
        send_notify: bool = False,
        source_id: int = 0,
        login_name: Optional[str] = None,
        visibility: str = "public",
    ) -> dict:
        """
        Erstellt einen neuen Forgejo-User.

        :param source_id:   0 = lokale Auth, > 0 = externer Auth-Provider (LDAP, OAuth, ...)
        :param login_name:  Pflichtfeld; bei lokaler Auth identisch mit username
        """
        # self.module.log("ForgejoApiUsers::create_user(...)")

        # minimal_payload = {
        #     "username": username,
        #     "email": email,
        #     "password": password,
        #     "must_change_password": must_change_password,
        # }

        payload = {
            "username": username,
            "email": email,
            "password": password,
            "login_name": login_name or username,  # Pflichtfeld!
            "source_id": source_id,  # 0 = lokal, Pflichtfeld!
            "must_change_password": must_change_password,
            "send_notify": send_notify,
            "visibility": visibility,
        }
        # self.module.log(f" payload: {payload}")

        return self.api._post("/admin/users", json=payload)

    def update_user(self, username: str, updates: dict) -> dict:
        return self.api._patch(f"/admin/users/{username}", json=updates)

    def delete_user(self, username: str) -> dict:
        return self.api._delete(f"/admin/users/{username}")

    def settings(self):
        """ """
        self.module.log("ForgejoApiUsers::settings()")

        settings = self.api._get("/settings/api")

        self.module.log(f"settings: {settings}")


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
