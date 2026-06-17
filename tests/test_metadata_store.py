import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.vector_store.metadata_store import MetadataStore


def test_metadata_store_json_persistence():
    temp_dir = tempfile.mkdtemp()
    try:
        metadata_file = os.path.join(temp_dir, "metadata_store.json")
        config = {"type": "json", "connection": {"file": metadata_file}}

        store = MetadataStore(config=config)
        assert store.register_data_asset(
            asset_id="customer_table",
            asset_type="table",
            name="customer",
            description="Customer table metadata",
            owner="data_owner",
            metadata={
                "schema": "public",
                "source_asset_id": "source_table",
                "target_asset_id": "customer_table",
            },
        )

        assert store.add_lineage_relationship("source_table", "customer_table", "feeds_into")

        asset = store.get_asset_metadata("customer_table")
        assert asset is not None
        assert asset["name"] == "customer"
        assert asset["metadata"]["schema"] == "public"

        upstream = store.get_upstream_assets("customer_table")
        assert len(upstream) == 1
        assert upstream[0]["asset_id"] == "source_table"

        downstream = store.get_downstream_assets("source_table")
        assert len(downstream) == 1
        assert downstream[0]["asset_id"] == "customer_table"

        assert store.update_impact_score("customer_table", 0.75)
        reloaded = MetadataStore(config=config)
        persisted_asset = reloaded.get_asset_metadata("customer_table")
        assert persisted_asset is not None
        assert persisted_asset["impact_score"] == 0.75
        assert os.path.exists(metadata_file)

        with open(metadata_file, encoding="utf-8") as f:
            data = json.load(f)
            assert data["assets"]["customer_table"]["name"] == "customer"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
