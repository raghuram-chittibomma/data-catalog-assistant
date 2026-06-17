"""
Batch jobs for overnight refresh of vector database.
"""

import logging
from datetime import datetime
from typing import Any

from src.core.impact_analyzer import ImpactAnalyzer
from src.data_ingestion.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger(__name__)


class VectorDBRefreshJob:
    """
    Overnight batch job to refresh vector database with new DW updates.
    """

    def __init__(self, config: dict[str, Any] = None):
        """
        Initialize refresh job.

        Args:
            config: Job configuration
        """
        self.config = config or {}
        self.is_running = False
        self.embedding_service = None
        self.vector_store = None
        self.metadata_store = None
        self.pending_documents = []
        self.pending_embeddings = []
        logger.info("Initialized Vector DB Refresh Job")

    def set_services(self, embedding_service=None, vector_store=None, metadata_store=None):
        """Attach services used by the job (embedding service, vector store, metadata store)."""
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    def run(self) -> dict[str, Any]:
        """
        Run the refresh job.

        Returns:
            Job execution summary
        """
        logger.info("Starting Vector DB refresh job")
        start_time = datetime.now()
        self.is_running = True

        try:
            summary = {"start_time": start_time, "status": "running", "steps": []}

            # Step 1: Connect to DW and fetch updates
            logger.info("Step 1: Fetching updates from data warehouse")
            step1 = self._fetch_dw_updates()
            summary["steps"].append(step1)

            # Step 2: Parse ETL and SQL definitions
            logger.info("Step 2: Parsing ETL and SQL definitions")
            step2 = self._parse_etl_and_sql()
            summary["steps"].append(step2)

            # Step 3: Generate embeddings
            logger.info("Step 3: Generating embeddings")
            step3 = self._generate_embeddings()
            summary["steps"].append(step3)

            # Step 4: Update vector store
            logger.info("Step 4: Updating vector store")
            step4 = self._update_vector_store()
            summary["steps"].append(step4)

            # Step 5: Update metadata store
            logger.info("Step 5: Updating metadata store")
            step5 = self._update_metadata_store()
            summary["steps"].append(step5)

            # Step 6: Recompute impact scores from lineage graph
            logger.info("Step 6: Recomputing impact scores")
            step6 = self._recompute_impact_scores()
            summary["steps"].append(step6)

            summary["status"] = "completed"
            summary["end_time"] = datetime.now()
            summary["duration_seconds"] = (summary["end_time"] - start_time).total_seconds()

            logger.info(f"Vector DB refresh completed in {summary['duration_seconds']}s")
            return summary

        except Exception as e:
            logger.error(f"Vector DB refresh failed: {str(e)}")
            return {"start_time": start_time, "status": "failed", "error": str(e)}
        finally:
            self.is_running = False

    def _fetch_dw_updates(self) -> dict[str, Any]:
        """Fetch updates from data warehouse."""
        logger.debug("Fetching DW updates")
        if not self.config.get("datawarehouse") and not getattr(self, "datawarehouse_config", None):
            logger.warning("No datawarehouse configuration provided for refresh job")
            self.pending_documents = []
            return {
                "name": "fetch_dw_updates",
                "status": "completed",
                "tables_updated": 0,
                "records_processed": 0,
            }

        pipeline_config = self.config.get("datawarehouse") or getattr(
            self, "datawarehouse_config", {}
        )
        pipeline = IngestionPipeline(
            config=pipeline_config, embedding_service=self.embedding_service
        )

        try:
            self.pending_documents = pipeline.run()
            return {
                "name": "fetch_dw_updates",
                "status": "completed",
                "tables_updated": len(self.pending_documents),
                "records_processed": len(self.pending_documents),
            }
        except Exception as e:
            logger.error(f"Failed to fetch DW updates: {e}")
            self.pending_documents = []
            return {
                "name": "fetch_dw_updates",
                "status": "failed",
                "tables_updated": 0,
                "records_processed": 0,
                "error": str(e),
            }

    def _parse_etl_and_sql(self) -> dict[str, Any]:
        """Parse ETL definitions and SQL queries."""
        logger.debug("Parsing ETL and SQL")
        # At this stage, the ingestion pipeline already created document-ready metadata.
        sql_docs = [
            doc
            for doc in self.pending_documents
            if doc.get("metadata", {}).get("asset_type") == "sql"
        ]
        etl_docs = [
            doc
            for doc in self.pending_documents
            if doc.get("metadata", {}).get("asset_type") == "etl"
        ]
        return {
            "name": "parse_etl_and_sql",
            "status": "completed",
            "etl_processes_parsed": len(etl_docs),
            "sql_queries_parsed": len(sql_docs),
        }

    def _generate_embeddings(self) -> dict[str, Any]:
        """Generate embeddings for new data."""
        logger.debug("Generating embeddings")
        if not self.pending_documents:
            logger.debug("No pending documents to embed")
            return {"name": "generate_embeddings", "status": "completed", "embeddings_generated": 0}

        if not self.embedding_service:
            logger.error("No embedding service available for generating embeddings")
            return {"name": "generate_embeddings", "status": "failed", "embeddings_generated": 0}

        texts = [d.get("text") or d.get("content") or "" for d in self.pending_documents]
        try:
            embs = self.embedding_service.embed_texts(texts)
            self.pending_embeddings = embs
            return {
                "name": "generate_embeddings",
                "status": "completed",
                "embeddings_generated": len(embs),
            }
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return {"name": "generate_embeddings", "status": "failed", "embeddings_generated": 0}

    def _update_vector_store(self) -> dict[str, Any]:
        """Update vector store with new embeddings."""
        logger.debug("Updating vector store")
        if not self.pending_documents or not self.pending_embeddings:
            logger.debug("No documents or embeddings to update in vector store")
            return {
                "name": "update_vector_store",
                "status": "completed",
                "documents_added": 0,
                "documents_updated": 0,
            }

        if not self.vector_store:
            logger.error("No vector store configured for update")
            return {
                "name": "update_vector_store",
                "status": "failed",
                "documents_added": 0,
                "documents_updated": 0,
            }

        try:
            # Add documents with embeddings
            self.vector_store.add_documents(self.pending_documents, self.pending_embeddings)
            return {
                "name": "update_vector_store",
                "status": "completed",
                "documents_added": len(self.pending_documents),
                "documents_updated": 0,
            }
        except Exception as e:
            logger.error(f"Failed to update vector store: {e}")
            return {
                "name": "update_vector_store",
                "status": "failed",
                "documents_added": 0,
                "documents_updated": 0,
            }

    def _update_metadata_store(self) -> dict[str, Any]:
        """Update metadata store with new relationships."""
        logger.debug("Updating metadata store")
        if not self.metadata_store:
            logger.debug("No metadata store configured for refresh job")
            return {
                "name": "update_metadata_store",
                "status": "completed",
                "relationships_added": 0,
                "assets_registered": 0,
            }

        relationships_added = 0
        assets_registered = 0

        for doc in self.pending_documents:
            asset_id = doc.get("id") or doc.get("doc_id")
            if not asset_id:
                continue

            metadata = doc.get("metadata") or {}
            asset_type = metadata.get("asset_type", "document")
            name = metadata.get("name", str(asset_id))
            description = metadata.get("description") or doc.get("text", "")[:500]
            owner = metadata.get("owner", "unknown")

            if self.metadata_store.register_data_asset(
                asset_id=asset_id,
                asset_type=asset_type,
                name=name,
                description=description,
                owner=owner,
                metadata=metadata,
            ):
                assets_registered += 1

            for edge in metadata.get("lineage_edges") or []:
                source_asset = edge.get("source")
                target_asset = edge.get("target")
                relationship_type = edge.get("relationship_type", "foreign_key")
                if source_asset and target_asset:
                    if self.metadata_store.add_lineage_relationship(
                        source_asset, target_asset, relationship_type
                    ):
                        relationships_added += 1

            source_asset = metadata.get("source_asset_id")
            target_asset = metadata.get("target_asset_id")
            relationship_type = metadata.get("relationship_type", "depends_on")
            if source_asset and target_asset:
                if self.metadata_store.add_lineage_relationship(
                    source_asset, target_asset, relationship_type
                ):
                    relationships_added += 1

        return {
            "name": "update_metadata_store",
            "status": "completed",
            "relationships_added": relationships_added,
            "assets_registered": assets_registered,
        }

    def _recompute_impact_scores(self) -> dict[str, Any]:
        """Derive impact scores from upstream/downstream relationship counts."""
        if not self.metadata_store:
            return {
                "name": "recompute_impact_scores",
                "status": "skipped",
                "scores_updated": 0,
            }

        analyzer = ImpactAnalyzer(metadata_store=self.metadata_store)
        updated = analyzer.recompute_all_impact_scores()
        return {
            "name": "recompute_impact_scores",
            "status": "completed",
            "scores_updated": updated,
        }
