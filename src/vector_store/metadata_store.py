"""
Metadata store - maintains metadata about data assets, lineage, and relationships.
"""

import json
import logging
import os
import threading
from typing import Dict, List, Any, Optional, Union

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

logger = logging.getLogger(__name__)
DEFAULT_METADATA_FILE = "metadata_store.json"


class MetadataStore:
    """
    Stores metadata about data assets, including:
    - Table/column descriptions
    - Data lineage
    - Impact information
    - Owner/stakeholder data
    - ETL process information
    """

    def __init__(self, config: Union[str, Dict[str, Any]] = None):
        """
        Initialize Metadata Store.

        Args:
            config: Storage configuration dictionary or backend name.
        """
        self.config = config if isinstance(config, dict) else {}
        self.backend = (
            self.config.get("type") if isinstance(self.config, dict) else str(config)
        ) or "json"
        self.backend = self.backend.lower()
        self.connection = self.config.get("connection", {}) if isinstance(self.config, dict) else {}
        self.persist_file = self._resolve_persist_file()
        self._lock = threading.Lock()
        self.store = {"assets": {}, "relationships": []}
        self.db_connection = None

        if self.backend == "postgres":
            if psycopg2 is None:
                logger.warning(
                    "psycopg2 is not installed; falling back to local JSON persistence for MetadataStore."
                )
                self.backend = "json"
            else:
                try:
                    self._connect_postgres()
                    self._create_postgres_tables()
                except Exception as e:
                    logger.warning(
                        "Failed to initialize Postgres MetadataStore (%s), falling back to JSON: %s",
                        self.backend,
                        e,
                    )
                    self.backend = "json"
        elif self.backend != "json":
            logger.warning(
                "MetadataStore backend '%s' is not implemented; falling back to local JSON persistence.",
                self.backend,
            )
            self.backend = "json"

        if self.backend == "json":
            self._load()
        elif self.backend == "postgres":
            self._load_postgres()

        logger.info(f"Initialized Metadata Store with backend: {self.backend}")

    def _resolve_persist_file(self) -> str:
        file_path = None
        if isinstance(self.connection, dict):
            file_path = self.connection.get("persist_file") or self.connection.get("file") or self.connection.get("filepath")

        if not file_path:
            file_path = DEFAULT_METADATA_FILE

        path = os.path.abspath(file_path)
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        return path

    def _connect_postgres(self) -> None:
        conn_cfg = self.connection or {}
        conn_args = {
            "host": conn_cfg.get("host", "localhost"),
            "port": int(conn_cfg.get("port", 5432)) if conn_cfg.get("port") is not None else 5432,
            "dbname": conn_cfg.get("database"),
            "user": conn_cfg.get("user"),
            "password": conn_cfg.get("password"),
            "sslmode": conn_cfg.get("sslmode", "prefer"),
        }
        conn_args = {k: v for k, v in conn_args.items() if v is not None}
        self.db_connection = psycopg2.connect(cursor_factory=RealDictCursor, **conn_args)

    def _ensure_postgres_connection(self) -> None:
        if self.db_connection is None:
            self._connect_postgres()

    def _create_postgres_tables(self) -> None:
        self._ensure_postgres_connection()
        create_assets = """
            CREATE TABLE IF NOT EXISTS metadata_assets (
                asset_id TEXT PRIMARY KEY,
                asset_type TEXT,
                name TEXT,
                description TEXT,
                owner TEXT,
                metadata JSONB,
                impact_score NUMERIC
            );
        """
        create_relationships = """
            CREATE TABLE IF NOT EXISTS metadata_relationships (
                source_asset_id TEXT,
                target_asset_id TEXT,
                relationship_type TEXT,
                PRIMARY KEY (source_asset_id, target_asset_id, relationship_type)
            );
        """
        with self.db_connection.cursor() as cursor:
            cursor.execute(create_assets)
            cursor.execute(create_relationships)
            self.db_connection.commit()

    def _load_postgres(self) -> None:
        self._ensure_postgres_connection()
        with self.db_connection.cursor() as cursor:
            cursor.execute("SELECT asset_id, asset_type, name, description, owner, metadata, impact_score FROM metadata_assets")
            rows = cursor.fetchall()
            self.store["assets"] = {
                row["asset_id"]: {
                    "asset_id": row["asset_id"],
                    "asset_type": row["asset_type"],
                    "name": row["name"],
                    "description": row["description"],
                    "owner": row["owner"],
                    "metadata": row["metadata"] or {},
                    "impact_score": float(row["impact_score"] or 0.0),
                }
                for row in rows
            }
            cursor.execute("SELECT source_asset_id, target_asset_id, relationship_type FROM metadata_relationships")
            rel_rows = cursor.fetchall()
            self.store["relationships"] = [
                {
                    "source_asset_id": row["source_asset_id"],
                    "target_asset_id": row["target_asset_id"],
                    "relationship_type": row["relationship_type"],
                }
                for row in rel_rows
            ]

    def _load(self) -> None:
        if not os.path.exists(self.persist_file):
            return

        try:
            with open(self.persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.store["assets"] = data.get("assets", {}) or {}
                    self.store["relationships"] = data.get("relationships", []) or []
        except Exception as e:
            logger.warning(f"Could not load metadata store from {self.persist_file}: {e}")

    def _save(self) -> None:
        if self.backend == "postgres":
            return

        try:
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(self.store, f, indent=2)
                logger.debug(f"Saved metadata store to {self.persist_file}")
        except Exception as e:
            logger.error(f"Failed to save metadata store to {self.persist_file}: {e}")

    def _upsert_postgres_asset(self, asset_payload: Dict[str, Any]) -> None:
        self._ensure_postgres_connection()
        query = """
            INSERT INTO metadata_assets (asset_id, asset_type, name, description, owner, metadata, impact_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (asset_id) DO UPDATE SET
                asset_type = EXCLUDED.asset_type,
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                owner = EXCLUDED.owner,
                metadata = EXCLUDED.metadata,
                impact_score = EXCLUDED.impact_score
        """
        with self.db_connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    asset_payload["asset_id"],
                    asset_payload["asset_type"],
                    asset_payload["name"],
                    asset_payload["description"],
                    asset_payload["owner"],
                    json.dumps(asset_payload["metadata"]),
                    float(asset_payload["impact_score"]),
                ),
            )
            self.db_connection.commit()

    def _insert_postgres_relationship(self, relationship: Dict[str, Any]) -> None:
        self._ensure_postgres_connection()
        query = """
            INSERT INTO metadata_relationships (source_asset_id, target_asset_id, relationship_type)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """
        with self.db_connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    relationship["source_asset_id"],
                    relationship["target_asset_id"],
                    relationship["relationship_type"],
                ),
            )
            self.db_connection.commit()

    def _update_postgres_impact_score(self, asset_id: str, impact_score: float) -> None:
        self._ensure_postgres_connection()
        query = """
            UPDATE metadata_assets
            SET impact_score = %s
            WHERE asset_id = %s
        """
        with self.db_connection.cursor() as cursor:
            cursor.execute(query, (float(impact_score), asset_id))
            self.db_connection.commit()

    def _close_postgres_connection(self) -> None:
        if self.db_connection:
            try:
                self.db_connection.close()
                logger.debug("Closed Postgres metadata connection")
            except Exception as e:
                logger.warning(f"Error closing Postgres metadata connection: {e}")
            finally:
                self.db_connection = None

    def register_data_asset(
        self,
        asset_id: str,
        asset_type: str,
        name: str,
        description: str,
        owner: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a new or updated data asset.

        Args:
            asset_id: Unique identifier
            asset_type: Type of asset
            name: Display name
            description: Description
            owner: Owner email/id
            metadata: Additional metadata

        Returns:
            True if successful
        """
        if not asset_id:
            return False

        logger.debug(f"Registering asset: {asset_id}")
        asset_payload = {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "name": name,
            "description": description,
            "owner": owner,
            "metadata": metadata or {},
            "impact_score": self.store["assets"].get(asset_id, {}).get("impact_score", 0.0),
        }

        with self._lock:
            self.store["assets"][asset_id] = asset_payload
            if self.backend == "postgres":
                self._upsert_postgres_asset(asset_payload)
            else:
                self._save()

        return True

    def add_lineage_relationship(
        self,
        source_asset_id: str,
        target_asset_id: str,
        relationship_type: str,
    ) -> bool:
        """
        Add a lineage relationship between assets.

        Args:
            source_asset_id: Source asset
            target_asset_id: Target asset
            relationship_type: Type of relationship

        Returns:
            True if successful
        """
        if not source_asset_id or not target_asset_id:
            return False

        logger.debug(f"Adding lineage: {source_asset_id} -> {target_asset_id}")
        relationship = {
            "source_asset_id": source_asset_id,
            "target_asset_id": target_asset_id,
            "relationship_type": relationship_type,
        }

        with self._lock:
            if relationship not in self.store["relationships"]:
                self.store["relationships"].append(relationship)
                if self.backend == "postgres":
                    self._insert_postgres_relationship(relationship)
                else:
                    self._save()

        return True

    def get_asset_metadata(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an asset."""
        logger.debug(f"Getting metadata for: {asset_id}")
        return self.store["assets"].get(asset_id)

    def get_upstream_assets(self, asset_id: str) -> List[Dict[str, Any]]:
        """Get upstream assets that feed into this asset."""
        logger.debug(f"Getting upstream assets for: {asset_id}")
        assets = []
        for rel in self.store["relationships"]:
            if rel["target_asset_id"] != asset_id:
                continue
            upstream_asset = self.store["assets"].get(rel["source_asset_id"])
            if upstream_asset:
                assets.append(upstream_asset)
            else:
                assets.append({
                    "asset_id": rel["source_asset_id"],
                    "relationship_type": rel["relationship_type"],
                    "missing": True,
                })
        return assets

    def get_downstream_assets(self, asset_id: str) -> List[Dict[str, Any]]:
        """Get downstream assets that depend on this asset."""
        logger.debug(f"Getting downstream assets for: {asset_id}")
        assets = []
        for rel in self.store["relationships"]:
            if rel["source_asset_id"] != asset_id:
                continue
            downstream_asset = self.store["assets"].get(rel["target_asset_id"])
            if downstream_asset:
                assets.append(downstream_asset)
            else:
                assets.append({
                    "asset_id": rel["target_asset_id"],
                    "relationship_type": rel["relationship_type"],
                    "missing": True,
                })
        return assets

    def update_impact_score(self, asset_id: str, impact_score: float) -> bool:
        """Update impact score for an asset."""
        if asset_id not in self.store["assets"]:
            return False

        logger.debug(f"Updating impact score for {asset_id}: {impact_score}")
        with self._lock:
            self.store["assets"][asset_id]["impact_score"] = impact_score
            if self.backend == "postgres":
                self._update_postgres_impact_score(asset_id, impact_score)
            else:
                self._save()

        return True
