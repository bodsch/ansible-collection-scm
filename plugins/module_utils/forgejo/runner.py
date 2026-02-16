from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

_ALLOWED_TABLES: Tuple[str, ...] = ("action_runner", "act_runner")

DbType = Literal["sqlite", "mariadb"]
RunnerState = Literal["active", "idle", "offline"]


class RunnerInfo(TypedDict):
    """Normalized runner information for external consumers."""

    id: int
    token_salt: str
    agent_labels: List[str]
    state: RunnerState
    last_online: int
    last_active: int


@dataclass(frozen=True, slots=True)
class RunnerSnapshot:
    """
    Aggregated runner information.

    Attributes:
        runners: Mapping runner-name -> RunnerInfo (created runners in DB).
        total: Number of all (not deleted) runners.
        online: Number of runners considered online (idle + active).
        active: Number of runners considered active.
        idle: Number of runners considered idle.
        offline: Number of runners considered offline.
    """

    runners: Dict[str, RunnerInfo]
    total: int
    online: int
    active: int
    idle: int
    offline: int

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the snapshot to a plain dict (e.g. for Ansible exit_json()).

        Returns:
            A JSON-serializable dict representation.
        """
        return {
            "runners": self.runners,
            "total": self.total,
            "online": self.online,
            "active": self.active,
            "idle": self.idle,
            "offline": self.offline,
        }


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """
    Database configuration for Forgejo runner queries.

    This dataclass supports both SQLite and MariaDB. Use the factory methods
    `DatabaseConfig.sqlite(...)` or `DatabaseConfig.mariadb(...)`.

    Attributes:
        db_type: Database type ('sqlite3' or 'mariadb').

        # SQLite
        sqlite_path: Path to SQLite DB file (required for db_type='sqlite').

        # MariaDB
        host: MariaDB host.
        port: MariaDB port.
        user: MariaDB username.
        password: MariaDB password.
        database: MariaDB database name.
        charset: Connection charset (default: utf8mb4).
    """

    db_type: DbType

    sqlite_path: Optional[str] = None

    host: Optional[str] = None
    port: int = 3306
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    charset: str = "utf8mb4"

    @classmethod
    def sqlite3(cls, path: str) -> "DatabaseConfig":
        """
        Create a SQLite configuration.

        Args:
            path: Path to the SQLite DB file.

        Returns:
            DatabaseConfig configured for SQLite.
        """
        return cls(db_type="sqlite", sqlite_path=path)

    @classmethod
    def mariadb(
        cls,
        *,
        host: str,
        user: str,
        password: str,
        database: str,
        port: int = 3306,
        charset: str = "utf8mb4",
    ) -> "DatabaseConfig":
        """
        Create a MariaDB configuration.

        Args:
            host: MariaDB host.
            user: MariaDB username.
            password: MariaDB password.
            database: Database name.
            port: MariaDB port.
            charset: Connection charset.

        Returns:
            DatabaseConfig configured for MariaDB.
        """
        return cls(
            db_type="mariadb",
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
        )

    def validate(self) -> None:
        """
        Validate that all required fields for the selected db_type are set.

        Raises:
            ValueError: If required fields are missing.
        """
        if self.db_type == "sqlite3":
            if not self.sqlite_path:
                raise ValueError("sqlite_path is required for db_type='sqlite'")
            return

        if self.db_type == "mariadb":
            missing = [
                k
                for k, v in {
                    "host": self.host,
                    "user": self.user,
                    "password": self.password,
                    "database": self.database,
                }.items()
                if not v
            ]
            if missing:
                raise ValueError(f"Missing MariaDB fields: {', '.join(missing)}")
            return

        raise ValueError(f"Unsupported db_type: {self.db_type}")


class ForgejoRunner:
    """
    Query Forgejo Action runners from the database (SQLite or MariaDB).

    This class provides a single public method `get_runner_snapshot()` that:
    - returns aggregated counts (total/online/active/idle/offline)
    - and returns all created runners as a dictionary keyed by runner name

    Online/active/idle semantics are derived from timestamps:
    - online  : now - last_online <= online_seconds
    - active  : online and now - last_active <= active_seconds
    - idle    : online and now - last_active >  active_seconds
    - offline : not online
    """

    def __init__(self, module: Any) -> None:
        """
        Initialize the runner helper.

        Args:
            module: Ansible module (used for logging and consistent error behavior).
        """
        self.module = module
        self.module.log("ForgejoRunner::__init__()")

    # -------------------------
    # Public API
    # -------------------------

    def get_runner_snapshot(
        self,
        db: DatabaseConfig,
        *,
        online_seconds: int = 60,
        active_seconds: int = 10,
        mask_token_salt: bool = True,
    ) -> RunnerSnapshot:
        """
        Fetch runner information and aggregate runner state counts.

        Args:
            db: Database configuration (SQLite or MariaDB).
            online_seconds: Threshold (seconds) to consider a runner online.
            active_seconds: Threshold (seconds) to consider a runner active.
            mask_token_salt:
                If True, token_salt is returned as an empty string to avoid leaking
                secrets. If False, the real token_salt is returned.

        Returns:
            RunnerSnapshot containing runner details and aggregated counts.

        Raises:
            ValueError: Invalid configuration or missing table.
            RuntimeError: Database access errors.
        """
        self.module.log(
            f"ForgejoRunner::get_runner_snapshot("
            f"db: {db}, online_seconds: {online_seconds}, active_seconds: {active_seconds}, mask_token_salt: {mask_token_salt})"
        )

        db.validate()

        now = int(time.time())

        if db.db_type == "sqlite3":
            import sqlite3  # local import to keep optional dependency

            conn = sqlite3.connect(db.sqlite_path)  # type: ignore[arg-type]
            try:
                table = self._detect_runner_table_sqlite(conn)
                rows = self._fetch_runner_rows_sqlite(conn, table)
            finally:
                conn.close()

        elif db.db_type == "mariadb":
            import pymysql  # local import to keep optional dependency

            conn = pymysql.connect(
                host=db.host,
                port=db.port,
                user=db.user,
                password=db.password,
                database=db.database,
                charset=db.charset,
                autocommit=True,
            )
            try:
                table = self._detect_runner_table_mariadb(conn)
                rows = self._fetch_runner_rows_mariadb(conn, table)
            finally:
                conn.close()
        else:
            raise ValueError(f"Unsupported db_type: {db.db_type}")

        runners: Dict[str, RunnerInfo] = {}
        total = 0
        online = 0
        active = 0
        idle = 0

        for (
            runner_id,
            name,
            token_salt,
            agent_labels_json,
            last_online,
            last_active,
        ) in rows:
            total += 1

            lo = int(last_online or 0)
            la = int(last_active or 0)

            is_online = (now - lo) <= int(online_seconds)
            is_active = is_online and (now - la) <= int(active_seconds)
            is_idle = is_online and not is_active

            if is_online:
                online += 1
            if is_active:
                active += 1
            if is_idle:
                idle += 1

            state: RunnerState = "offline"
            if is_active:
                state = "active"
            elif is_idle:
                state = "idle"

            labels = self._parse_agent_labels(agent_labels_json)

            runners[str(name)] = {
                "id": int(runner_id),
                "token_salt": "" if mask_token_salt else str(token_salt or ""),
                "agent_labels": labels,
                "state": state,
                "last_online": lo,
                "last_active": la,
            }

        offline = max(0, total - online)

        return RunnerSnapshot(
            runners=runners,
            total=total,
            online=online,
            active=active,
            idle=idle,
            offline=offline,
        )

    # -------------------------
    # Internal helpers
    # -------------------------

    def _detect_runner_table_sqlite(self, conn: Any) -> str:
        """
        Detect the runner table name in SQLite.

        Args:
            conn: sqlite3.Connection.

        Returns:
            The detected table name.

        Raises:
            ValueError: If no supported table is found.
        """
        self.module.log("ForgejoRunner::_detect_runner_table_sqlite(conn)")

        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?)",
            _ALLOWED_TABLES,
        )
        names = {row[0] for row in cur.fetchall()}
        for candidate in _ALLOWED_TABLES:
            if candidate in names:
                return candidate
        raise ValueError(f"No runner table found. Tried: {_ALLOWED_TABLES}")

    def _detect_runner_table_mariadb(self, conn: Any) -> str:
        """
        Detect the runner table name in MariaDB.

        Args:
            conn: pymysql connection.

        Returns:
            The detected table name.

        Raises:
            ValueError: If no supported table is found.
        """
        self.module.log("ForgejoRunner::_detect_runner_table_mariadb(conn)")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name IN (%s, %s)
                """,
                _ALLOWED_TABLES,
            )
            names = {row[0] for row in cur.fetchall()}
        for candidate in _ALLOWED_TABLES:
            if candidate in names:
                return candidate
        raise ValueError(f"No runner table found. Tried: {_ALLOWED_TABLES}")

    def _fetch_runner_rows_sqlite(self, conn: Any, table: str) -> List[Tuple[Any, ...]]:
        """
        Fetch runner rows from SQLite.

        Args:
            conn: sqlite3.Connection.
            table: Runner table name.

        Returns:
            Rows containing (id, name, token_salt, agent_labels, last_online, last_active).
        """
        self.module.log(
            f"ForgejoRunner::_fetch_runner_rows_sqlite(conn, table: {table})"
        )

        if table not in _ALLOWED_TABLES:
            raise ValueError("Invalid table name")

        where_not_deleted = "(deleted IS NULL OR deleted = 0)"
        query = (
            f"SELECT id, name, token_salt, agent_labels, last_online, last_active "
            f"FROM {table} WHERE {where_not_deleted}"
        )
        return conn.execute(query).fetchall()

    def _fetch_runner_rows_mariadb(
        self, conn: Any, table: str
    ) -> List[Tuple[Any, ...]]:
        """
        Fetch runner rows from MariaDB.

        Args:
            conn: pymysql connection.
            table: Runner table name.

        Returns:
            Rows containing (id, name, token_salt, agent_labels, last_online, last_active).
        """
        self.module.log(
            f"ForgejoRunner::_fetch_runner_rows_mariadb(conn, table: {table})"
        )

        if table not in _ALLOWED_TABLES:
            raise ValueError("Invalid table name")

        where_not_deleted = "(deleted IS NULL OR deleted = 0)"
        query = (
            f"SELECT id, name, token_salt, agent_labels, last_online, last_active "
            f"FROM {table} WHERE {where_not_deleted}"
        )

        with conn.cursor() as cur:
            cur.execute(query)
            return list(cur.fetchall())

    @staticmethod
    def _parse_agent_labels(agent_labels_json: Any) -> List[str]:
        """
        Parse the `agent_labels` column which is typically a JSON array string.

        Args:
            agent_labels_json: Value from DB (string or NULL).

        Returns:
            List of label strings. Returns [] on invalid input.
        """
        if not agent_labels_json:
            return []

        try:
            parsed = json.loads(agent_labels_json)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
            return []
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
