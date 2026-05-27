from batch_jobs.refresh_vector_db import VectorDBRefreshJob
from src.vector_store.metadata_store import MetadataStore

class DummyEmbedding:
    def embed_texts(self, texts):
        return [[0.01, 0.02, 0.03] for _ in texts]

class DummyVectorStore:
    def __init__(self):
        self.docs = []
    def add_documents(self, documents, embeddings):
        self.docs.extend(list(zip(documents, embeddings)))

job = VectorDBRefreshJob(config={})
job.set_services(
    embedding_service=DummyEmbedding(),
    vector_store=DummyVectorStore(),
    metadata_store=MetadataStore(config={"type": "json", "connection": {"file": "temp_meta.json"}}),
)
job.pending_documents = [
    {
        "id": "public.customers",
        "text": "Customer table info",
        "metadata": {
            "asset_type": "table",
            "table_name": "customers",
            "source_asset_id": "src_table",
            "target_asset_id": "public.customers",
        },
    },
    {
        "id": "sql-1",
        "text": "SELECT * FROM public.customers",
        "metadata": {"asset_type": "sql", "source": "report1", "owner": "analyst@example.com"},
    },
]

print('Generate embeddings:', job._generate_embeddings())
print('Update vector store:', job._update_vector_store())
print('Update metadata store:', job._update_metadata_store())
print('Vector store docs count:', len(job.vector_store.docs))
