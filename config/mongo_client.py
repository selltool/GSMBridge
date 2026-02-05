# mongo_client.py
from __future__ import annotations

import atexit
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from pymongo import MongoClient, errors
from pymongo.collection import Collection
from pymongo.database import Database

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db: str
    collection: str

    # Networking / timeouts
    connect_timeout_ms: int = 5_000
    server_selection_timeout_ms: int = 5_000
    socket_timeout_ms: int = 10_000

    # Retry strategy for initial connect / operations
    max_retries: int = 8
    base_backoff_s: float = 0.25
    max_backoff_s: float = 5.0


def load_mongo_settings() -> MongoSettings:
    """
    Load Mongo settings from .env (or environment variables).
    Expected env:
      - MONGO_URI
      - MONGO_DB
      - MONGO_COLLECTION
    Optional tuning env:
      - MONGO_CONNECT_TIMEOUT_MS
      - MONGO_SERVER_SELECTION_TIMEOUT_MS
      - MONGO_SOCKET_TIMEOUT_MS
      - MONGO_MAX_RETRIES
      - MONGO_BASE_BACKOFF_S
      - MONGO_MAX_BACKOFF_S
    """
    load_dotenv()

    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid int for {name}: {raw}") from exc

    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name, str(default)).strip()
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"Invalid float for {name}: {raw}") from exc

    uri = (os.getenv("MONGO_URI") or "").strip()
    if not uri:
        raise ValueError("MONGO_URI is required (e.g. mongodb://user:pass@localhost:27017/?authSource=admin)")

    return MongoSettings(
        uri=uri,
        db=(os.getenv("MONGO_DB", "gsmbridge").strip()),
        collection=(os.getenv("MONGO_COLLECTION", "at_responses").strip()),
        connect_timeout_ms=_env_int("MONGO_CONNECT_TIMEOUT_MS", 5_000),
        server_selection_timeout_ms=_env_int("MONGO_SERVER_SELECTION_TIMEOUT_MS", 5_000),
        socket_timeout_ms=_env_int("MONGO_SOCKET_TIMEOUT_MS", 10_000),
        max_retries=_env_int("MONGO_MAX_RETRIES", 8),
        base_backoff_s=_env_float("MONGO_BASE_BACKOFF_S", 0.25),
        max_backoff_s=_env_float("MONGO_MAX_BACKOFF_S", 5.0),
    )


def _sleep_backoff(attempt: int, base: float, max_s: float) -> None:
    # exponential backoff: base * 2^(attempt-1), capped
    delay = min(max_s, base * (2 ** max(0, attempt - 1)))
    time.sleep(delay)


class MongoClientManager:
    """
    A small wrapper around pymongo.MongoClient:
      - Lazy connect + ping healthcheck
      - Retry on initial connect and transient errors
      - Simple insert helper with retry
      - Safe close at exit
    """

    def __init__(self, settings: MongoSettings):
        self._settings = settings
        self._client: Optional[MongoClient] = None

        # Ensure we close on process exit
        atexit.register(self.close)

    def _build_client(self) -> MongoClient:
        # retryWrites helps on replica set / Atlas; harmless on standalone.
        # maxPoolSize can be tuned if you have many concurrent operations.
        return MongoClient(
            self._settings.uri,
            connectTimeoutMS=self._settings.connect_timeout_ms,
            serverSelectionTimeoutMS=self._settings.server_selection_timeout_ms,
            socketTimeoutMS=self._settings.socket_timeout_ms,
            retryWrites=True,
        )

    def connect(self) -> MongoClient:
        """
        Ensure a live client. Retries ping on failure.
        """
        if self._client is None:
            self._client = self._build_client()

        for attempt in range(1, self._settings.max_retries + 1):
            try:
                # Healthcheck: force server selection
                self._client.admin.command("ping")
                logger.info("MongoDB connected (ping OK).")
                return self._client
            except (errors.ServerSelectionTimeoutError, errors.AutoReconnect, errors.NetworkTimeout) as exc:
                logger.warning("Mongo connect attempt %d/%d failed: %s", attempt, self._settings.max_retries, exc)
                _sleep_backoff(attempt, self._settings.base_backoff_s, self._settings.max_backoff_s)
                # Recreate client after failures to clear bad sockets
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = self._build_client()
            except Exception as exc:
                # Non-transient errors: fail fast
                logger.exception("Mongo connect failed with non-retryable error: %s", exc)
                raise

        raise RuntimeError("MongoDB connection failed after retries.")

    def db(self) -> Database:
        client = self.connect()
        return client[self._settings.db]

    def collection(self) -> Collection:
        return self.db()[self._settings.collection]

    def insert_one_with_retry(self, doc: Dict[str, Any]) -> str:
        """
        Insert a document with retry for transient errors.
        Returns inserted_id as string.
        """
        col = self.collection()

        for attempt in range(1, self._settings.max_retries + 1):
            try:
                result = col.insert_one(doc)
                return str(result.inserted_id)
            except (errors.AutoReconnect, errors.NetworkTimeout, errors.ServerSelectionTimeoutError) as exc:
                logger.warning("Mongo insert attempt %d/%d failed: %s", attempt, self._settings.max_retries, exc)
                _sleep_backoff(attempt, self._settings.base_backoff_s, self._settings.max_backoff_s)
                # force a fresh selection next round
                self._client = None
                col = self.collection()
            except errors.DuplicateKeyError as exc:
                # Not transient; surface clearly
                raise ValueError(f"Duplicate key insert: {exc.details}") from exc
            except Exception:
                logger.exception("Mongo insert failed (non-retryable).")
                raise

        raise RuntimeError("Mongo insert failed after retries.")

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
                logger.info("MongoDB client closed.")
            finally:
                self._client = None


# Singleton-ish helper (optional)
_settings: Optional[MongoSettings] = None
_manager: Optional[MongoClientManager] = None


def get_mongo_manager() -> MongoClientManager:
    global _settings, _manager
    if _manager is None:
        _settings = load_mongo_settings()
        _manager = MongoClientManager(_settings)
    return _manager
