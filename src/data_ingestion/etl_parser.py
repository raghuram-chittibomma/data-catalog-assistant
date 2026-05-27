"""
ETL parser - extracts information from ETL process definitions (YAML/JSON).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)


class ETLParser:
    """
    Parses ETL definitions to extract sources, targets, transformations, and lineage.
    """

    def __init__(self, default_schema: str = "public"):
        self.default_schema = default_schema
        logger.info("Initialized ETL Parser (default_schema=%s)", default_schema)

    def parse_etl_config(self, config_file: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Parse an ETL configuration file (YAML or JSON).

        Supports a single job object or a list under ``etl_jobs`` / ``jobs``.

        Returns:
            List of normalized ETL job dictionaries
        """
        path = Path(config_file)
        logger.debug("Parsing ETL config: %s", path)

        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return []

        data = self._load_raw(path, raw_text)
        jobs = self._extract_jobs(data)
        return [self._normalize_job(job, path) for job in jobs if job]

    def _load_raw(self, path: Path, raw_text: str) -> Any:
        suffix = path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            return yaml.safe_load(raw_text)
        if suffix == ".json":
            return json.loads(raw_text)
        try:
            return yaml.safe_load(raw_text)
        except yaml.YAMLError:
            return json.loads(raw_text)

    def _extract_jobs(self, data: Any) -> List[Dict[str, Any]]:
        if data is None:
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("etl_jobs", "jobs", "processes"):
                if key in data and isinstance(data[key], list):
                    return [item for item in data[key] if isinstance(item, dict)]
            return [data]
        return []

    def _normalize_job(self, job: Dict[str, Any], path: Path) -> Dict[str, Any]:
        name = job.get("name") or path.stem
        sources = [self._normalize_table(t) for t in job.get("sources", []) if t]
        targets = [self._normalize_table(t) for t in job.get("targets", []) if t]
        dependencies = list(job.get("dependencies", []) or [])

        return {
            "name": name,
            "description": job.get("description", ""),
            "owner": job.get("owner", ""),
            "sources": [s for s in sources if s],
            "targets": [t for t in targets if t],
            "transformations": list(job.get("transformations", []) or []),
            "schedule": job.get("schedule", ""),
            "dependencies": dependencies,
            "config_path": str(path),
        }

    def _normalize_table(self, table_name: str) -> str:
        cleaned = str(table_name).strip().strip('"').strip("'")
        if not cleaned:
            return ""
        if "." in cleaned:
            return cleaned.lower()
        return f"{self.default_schema}.{cleaned.lower()}"

    def extract_lineage(self, etl_config: Dict[str, Any], etl_asset_id: str) -> Dict[str, Any]:
        """
        Build lineage edges for an ETL job.

        Sources feed the ETL; the ETL writes to targets.
        """
        edges: List[Dict[str, str]] = []

        for source in etl_config.get("sources", []):
            edges.append(
                {
                    "source": source,
                    "target": etl_asset_id,
                    "relationship_type": "etl_source",
                }
            )

        for target in etl_config.get("targets", []):
            edges.append(
                {
                    "source": etl_asset_id,
                    "target": target,
                    "relationship_type": "etl_target",
                }
            )

        for dep in etl_config.get("dependencies", []):
            dep_id = self._normalize_dependency(dep)
            if dep_id:
                edges.append(
                    {
                        "source": dep_id,
                        "target": etl_asset_id,
                        "relationship_type": "etl_depends_on",
                    }
                )

        return {"edges": edges, "sources": etl_config.get("sources", []), "targets": etl_config.get("targets", [])}

    def _normalize_dependency(self, dep: Any) -> str:
        if isinstance(dep, dict):
            if dep.get("etl"):
                return f"etl:{dep['etl']}"
            if dep.get("name"):
                return f"etl:{dep['name']}"
        text = str(dep).strip()
        if text.startswith("etl:"):
            return text
        if text:
            return f"etl:{text}"
        return ""

    def generate_documentation(self, etl_config: Dict[str, Any]) -> str:
        """Generate a short human-readable description for an ETL job."""
        name = etl_config.get("name", "unknown")
        description = etl_config.get("description", "")
        sources = etl_config.get("sources", [])
        targets = etl_config.get("targets", [])
        transforms = etl_config.get("transformations", [])
        schedule = etl_config.get("schedule", "")

        parts = [f"ETL process {name}."]
        if description:
            parts.append(description)
        if sources:
            parts.append(f"Reads from: {', '.join(sources)}.")
        if targets:
            parts.append(f"Writes to: {', '.join(targets)}.")
        if transforms:
            parts.append(f"Transformations: {'; '.join(str(t) for t in transforms)}.")
        if schedule:
            parts.append(f"Schedule: {schedule}.")
        return " ".join(parts).strip()
