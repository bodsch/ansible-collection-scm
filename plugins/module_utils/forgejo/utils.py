import os
from typing import List, Tuple


def validate_users(users: List) -> Tuple[List[dict], List[dict]]:
    """ """
    valid_users = []
    invalid_users = []

    for user in users:
        username = user.get("username", "").strip()
        password = user.get("password", "").strip()
        email = user.get("email", "").strip()

        # Prüfe Vollständigkeit und Eindeutigkeit
        if username and password and email:
            valid_users.append(user)
        else:
            invalid_users.append(user)

    return valid_users, invalid_users


def check_existing_users(
    new_users: List[dict], existing: List[dict]
) -> Tuple[List[dict], List[dict]]:
    """ """
    if isinstance(existing, list):
        existing_map = {user["username"]: user for user in existing}
        existing = existing_map

    existing_usernames = {username.lower() for username in existing.keys()}
    existing_emails = {user.get("email").lower() for user in existing.values()}

    existing_users = []
    non_existing_users = []

    for user in new_users:
        username = user.get("username").lower()
        email = user.get("email").lower()

        if username in existing_usernames or email in existing_emails:
            existing_users.append(user)
        else:
            non_existing_users.append(user)
            existing_usernames.add(username)
            existing_emails.add(email)

    return existing_users, non_existing_users


def is_absolute_path(path: str) -> bool:
    """ """
    return os.path.isabs(path)
