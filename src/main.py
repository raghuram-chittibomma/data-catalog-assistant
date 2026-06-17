"""
Main entry point for Data Catalog Assistant.
"""

import logging
import sys
from pathlib import Path

# Allow: python src/main.py from project root (sys.path[0] would otherwise be src/)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from batch_jobs.refresh_vector_db import VectorDBRefreshJob
from batch_jobs.scheduler import JobScheduler
from src.core.impact_analyzer import ImpactAnalyzer
from src.core.query_processor import QueryProcessor
from src.core.rag_engine import RAGEngine
from src.mcp_server.resources.data_catalog import DataCatalog
from src.mcp_server.server import MCPServer
from src.mcp_server.tools.impact_tools import ImpactTools
from src.mcp_server.tools.query_tools import QueryTools
from src.mcp_server.tools.search_tools import SearchTools
from src.ui.gradio_interface import GradioInterface
from src.utils.config_loader import load_config
from src.utils.logging import setup_logging
from src.vector_store.embeddings import LocalEmbedding
from src.vector_store.metadata_store import MetadataStore
from src.vector_store.vector_db import ChromaVectorStore

logger = logging.getLogger(__name__)


def initialize_components(config: dict):
    """Initialize all application components."""
    logger.info("Initializing Data Catalog Assistant components")

    # Initialize local embedding service (sentence-transformers)
    emb_cfg = config.get("embeddings", {})
    embedding_service = LocalEmbedding(model_name=emb_cfg.get("model_name", "all-MiniLM-L6-v2"))

    # Initialize vector store
    vector_store = ChromaVectorStore(config=config["vector_store"])
    vector_store.connect()

    # Initialize metadata store
    metadata_store = MetadataStore(config=config.get("metadata_store", {}))

    # Initialize RAG engine
    rag_engine = RAGEngine(
        vector_store=vector_store,
        llm_client=None,  # Will initialize based on config
        embedding_service=embedding_service,
        metadata_store=metadata_store,
        config=config,
    )

    # Initialize MCP server
    mcp_server = MCPServer(config=config["mcp_server"])

    # Initialize MCP tools and resources
    query_cfg = {**(config.get("schema_context") or {}), **(config.get("query") or {})}
    query_processor = QueryProcessor(
        llm_client=None,
        schema_context=query_cfg,
        rag_engine=rag_engine,
    )
    impact_analyzer = ImpactAnalyzer(vector_store=vector_store, metadata_store=metadata_store)
    query_tools = QueryTools(query_processor=query_processor, rag_engine=rag_engine)
    search_tools = SearchTools(rag_engine=rag_engine)
    impact_tools = ImpactTools(impact_analyzer=impact_analyzer)
    data_catalog = DataCatalog(metadata_store=metadata_store)

    register_mcp_services(
        mcp_server,
        query_tools=query_tools,
        search_tools=search_tools,
        impact_tools=impact_tools,
        data_catalog=data_catalog,
    )

    # Initialize Gradio UI (Phase 4 + 5B MCP parity)
    ui = GradioInterface(
        rag_engine=rag_engine,
        query_processor=query_processor,
        query_tools=query_tools,
        impact_tools=impact_tools,
        data_catalog=data_catalog,
        config=config["ui"],
    )

    # Initialize batch jobs
    refresh_job = VectorDBRefreshJob(config=config["batch_jobs"]["vector_db_refresh"])
    refresh_job.datawarehouse_config = config.get("datawarehouse", {})
    # Attach services to refresh job so it can generate embeddings, update vector store, and update metadata store
    refresh_job.set_services(
        embedding_service=embedding_service,
        vector_store=vector_store,
        metadata_store=metadata_store,
    )
    job_scheduler = JobScheduler()

    return {
        "embedding_service": embedding_service,
        "vector_store": vector_store,
        "metadata_store": metadata_store,
        "rag_engine": rag_engine,
        "mcp_server": mcp_server,
        "ui": ui,
        "refresh_job": refresh_job,
        "job_scheduler": job_scheduler,
    }


def register_mcp_services(
    mcp_server: MCPServer,
    query_tools: QueryTools,
    search_tools: SearchTools,
    impact_tools: ImpactTools,
    data_catalog: DataCatalog,
):
    """Register MCP tools and resources with the MCP server."""
    # Query generation tools
    mcp_server.register_tool(
        "generate_query",
        query_tools.generate_query,
        "Generate SQL from natural language descriptions.",
        {"description": {"type": "string", "required": True}},
    )
    mcp_server.register_tool(
        "validate_query",
        query_tools.validate_query,
        "Validate SQL syntax and safety.",
        {"sql": {"type": "string", "required": True}},
    )
    mcp_server.register_tool(
        "explain_query",
        query_tools.explain_query,
        "Explain SQL intent in plain English.",
        {"sql": {"type": "string", "required": True}},
    )
    mcp_server.register_tool(
        "suggest_optimizations",
        query_tools.suggest_optimizations,
        "Suggest SQL optimizations.",
        {"sql": {"type": "string", "required": True}},
    )

    # Search tools
    mcp_server.register_tool(
        "search_data_assets",
        search_tools.search_data_assets,
        "Search the data catalog and lineage store for relevant assets.",
        {
            "query": {"type": "string", "required": True},
            "top_k": {"type": "integer", "required": False},
        },
    )
    mcp_server.register_tool(
        "search_similar_queries",
        search_tools.search_similar_queries,
        "Find similar queries or reports based on a description.",
        {
            "query": {"type": "string", "required": True},
            "top_k": {"type": "integer", "required": False},
        },
    )
    mcp_server.register_tool(
        "search_by_table",
        search_tools.search_by_table,
        "Search catalog and lineage for a given table name.",
        {"table_name": {"type": "string", "required": True}},
    )
    mcp_server.register_tool(
        "search_by_owner",
        search_tools.search_by_owner,
        "Search data assets by owner.",
        {"owner": {"type": "string", "required": True}},
    )

    # Impact tools
    mcp_server.register_tool(
        "analyze_data_usage",
        impact_tools.analyze_data_usage,
        "Analyze usage and impact for a data asset.",
        {"data_asset": {"type": "string", "required": True}},
    )
    mcp_server.register_tool(
        "get_lineage",
        impact_tools.get_lineage,
        "Get upstream/downstream lineage for a data asset.",
        {
            "data_asset": {"type": "string", "required": True},
            "direction": {"type": "string", "required": False},
        },
    )
    mcp_server.register_tool(
        "assess_change_impact",
        impact_tools.assess_change_impact,
        "Assess the impact of a proposed change to a data asset.",
        {
            "data_asset": {"type": "string", "required": True},
            "change_description": {"type": "string", "required": True},
        },
    )
    mcp_server.register_tool(
        "compare_data_assets",
        impact_tools.compare_data_assets,
        "Compare two data assets and surface shared lineage.",
        {
            "asset1": {"type": "string", "required": True},
            "asset2": {"type": "string", "required": True},
        },
    )

    # Data catalog resources
    mcp_server.register_resource(
        "data_catalog_summary",
        data_catalog.get_catalog_summary,
        "Get a high-level summary of available data assets.",
    )
    mcp_server.register_resource(
        "list_tables", data_catalog.list_tables, "List tables in the data catalog."
    )
    mcp_server.register_resource(
        "list_reports", data_catalog.list_reports, "List reports in the data catalog."
    )
    mcp_server.register_resource(
        "list_etl_processes",
        data_catalog.list_etl_processes,
        "List ETL processes in the data catalog.",
    )
    mcp_server.register_resource(
        "get_asset_details",
        data_catalog.get_asset_details,
        "Get detailed metadata for a specific asset.",
    )


def main():
    """Main entry point."""
    # Setup logging
    setup_logging(level="INFO")
    logger.info("Starting Data Catalog Assistant")

    try:
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded")

        # Initialize components
        components = initialize_components(config)
        logger.info("Components initialized")

        # Start MCP server if enabled
        if config["mcp_server"]["enabled"]:
            logger.info("Starting MCP server")
            components["mcp_server"].start(
                host=config["mcp_server"]["host"], port=config["mcp_server"]["port"]
            )

        # Scheduled refresh: run manually via batch_jobs/run_refresh_job.py unless enabled
        refresh_cfg = config["batch_jobs"]["vector_db_refresh"]
        if refresh_cfg.get("enabled") and refresh_cfg.get("schedule_on_startup", False):
            logger.info("Scheduling vector DB refresh job on startup")
            components["job_scheduler"].schedule_daily_job(
                components["refresh_job"].run,
                refresh_cfg["schedule"],
                "vector_db_refresh",
            )
            components["job_scheduler"].start()

        mcp_cfg = config["mcp_server"]
        if mcp_cfg["enabled"]:
            logger.info(
                "MCP API: http://%s:%s — see docs/MCP_DEMO.md",
                mcp_cfg["host"],
                mcp_cfg["port"],
            )

        try:
            if config["ui"]["enabled"]:
                logger.info(
                    "Starting Gradio UI at http://%s:%s",
                    config["ui"]["host"],
                    config["ui"]["port"],
                )
                components["ui"].launch(
                    host=config["ui"]["host"],
                    port=config["ui"]["port"],
                    share=config["ui"]["share"],
                )
            elif mcp_cfg["enabled"]:
                logger.info("Press Ctrl+C to stop MCP server")
                import time

                while True:
                    time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            if mcp_cfg["enabled"]:
                components["mcp_server"].stop()

        logger.info("Data Catalog Assistant stopped")

    except Exception as e:
        logger.error(f"Failed to start Data Catalog Assistant: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
