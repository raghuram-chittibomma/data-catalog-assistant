# Data Catalog Assistant — Architecture

## System Overview

Data Catalog Assistant is a modular RAG-based system for enterprise data intelligence. It consists of several key components that work together to provide data understanding and query generation capabilities.

## Component Architecture

### 1. Data Ingestion Layer

**Purpose**: Extract and prepare data for embedding

**Components**:
- `DataWarehouseConnector`: Connects to data warehouse
- `SQLParser`: Parses SQL queries
- `ETLParser`: Parses ETL definitions
- `DataProcessor`: Converts data to embedding-ready format

**Flow**:
```
DW Schema → DW Connector → Metadata
ETL Files → ETL Parser → Lineage
SQL Files → SQL Parser → Descriptions
          ↓
    Data Processor
          ↓
    Processed Documents
```

### 2. Vector Store Layer

**Purpose**: Index and search semantic data

**Components**:
- `ChromaVectorStore`: ChromaDB-backed vector index
- `EmbeddingService`: Converts text to vectors
- `MetadataStore`: Maintains relationships and lineage

**Features**:
- Embedded ChromaDB with local persistence (`chroma_data/`)
- Metadata preservation during search
- Efficient incremental updates

### 3. RAG Core Layer

**Purpose**: Orchestrate RAG operations

**Components**:
- `RAGEngine`: Main orchestrator
- `QueryProcessor`: Convert natural language to SQL
- `ImpactAnalyzer`: Analyze data usage and impact

**Key Operations**:
- Semantic search for data lineage
- Query generation with validation
- Impact assessment
- Lineage analysis

### 4. MCP Server Layer

**Purpose**: Expose tools via Model Context Protocol

**Components**:
- `MCPServer`: Server implementation
- `SearchTools`: Vector search operations
- `QueryTools`: Query generation operations
- `ImpactTools`: Impact analysis operations
- `DataCatalog`: Resource for browsing data

**Features**:
- Standardized tool interface
- Integration with Claude and other agents
- Extensible architecture

### 5. UI Layer

**Purpose**: Provide user interface

**Components**:
- `GradioInterface`: Web-based UI

**Sections**:
- Query Builder: Natural language to SQL
- Lineage Viewer: Visualize data relationships
- Impact Analyzer: Show change impacts
- Data Catalog: Browse available data

### 6. Batch Processing Layer

**Purpose**: Keep vector database updated

**Components**:
- `VectorDBRefreshJob`: Orchestrates refresh
- `JobScheduler`: Manages scheduling

**Schedule**: Nightly refresh (configurable)

## Data Flow

### Query Processing Flow

```
User Query
    ↓
Query Processor
    ↓
Vector Search for relevant tables/columns
    ↓
LLM generates SQL with context
    ↓
SQL Validation
    ↓
User receives SQL + explanation
```

### Impact Analysis Flow

```
Data Asset Selected
    ↓
Metadata Store lookup
    ↓
Get upstream sources
    ↓
Get downstream consumers
    ↓
Calculate impact score
    ↓
Return impact report
```

### Batch Refresh Flow

```
Scheduled Trigger (nightly)
    ↓
1. Fetch updates from DW
    ↓
2. Parse ETL and SQL files
    ↓
3. Generate embeddings
    ↓
4. Update vector store
    ↓
5. Update metadata store
    ↓
Refresh Complete
```

## Technology Stack

### Core Libraries
- **Vector database**: ChromaDB
- **Embeddings**: Sentence Transformers (local)
- **LLMs**: OpenAI, Anthropic
- **Web UI**: Gradio
- **MCP**: Python MCP SDK
- **Metadata**: PostgreSQL, MongoDB

### Infrastructure
- **Process Management**: Schedule library
- **HTTP**: FastAPI, Uvicorn
- **Caching**: Redis (optional)
- **Logging**: Python logging module

## Deployment Architectures

### Development
```
Single Machine
├── ChromaDB (persist_directory: chroma_data/)
├── Local embeddings (sentence-transformers)
├── FastAPI + Gradio on localhost
└── JSON or PostgreSQL metadata
```

### Production
```
Cloud Deployment
├── ChromaDB (persistent volume for chroma_data/)
├── Local embeddings (sentence-transformers)
├── PostgreSQL (DW + optional metadata)
├── Multiple worker processes
├── Load balancer
└── Monitoring & logging
```

## Scalability Considerations

### Horizontal Scaling
- MCP server can be deployed as multiple instances
- Gradio UI can be behind load balancer
- Batch jobs can be distributed

### Performance Optimization
- Caching layer for frequent queries
- Incremental vector DB updates
- Batch embedding generation
- Connection pooling for databases

## Security Architecture

### Authentication & Authorization
- Optional OAuth2/JWT
- API key management
- Role-based access control

### Data Protection
- Environment variable secrets
- Encrypted database connections
- Query validation and sanitization
- Audit logging

## Monitoring & Observability

### Key Metrics
- Batch job execution time
- Vector store query latency
- LLM API usage
- Cache hit rates
- Error rates by component

### Logging Strategy
- Component-level logging
- Query logging for analysis
- Error and exception tracking
- Batch job progress logs

## Extension Points

### Adding New Data Sources
Implement `DataWarehouseConnector` for new DW types

### ChromaDB tuning
Adjust `persist_directory`, `collection_name`, and refresh schedule in `config/config.yaml`.

### Adding New MCP Tools
Create tool class and register with MCPServer

### Embeddings
Configure `embeddings.model_name` in `config/config.yaml` (default: `all-MiniLM-L6-v2`). Must match `vector_store.embedding_dimension` (384 for MiniLM).

## Performance Characteristics

### Query Generation
- Typical latency: 2-5 seconds
- Depends on LLM provider
- Can be cached for identical queries

### Vector Search
- Typical latency: 100-500ms
- Scales with vector store size
- Optimized with indexing

### Batch Refresh
- Typical duration: 30-60 minutes
- Depends on DW size
- Incremental for efficiency

## Disaster Recovery

### Data Loss Prevention
- Metadata database backups
- Vector DB snapshots
- Configuration version control

### Recovery Procedures
- Restore from backup
- Rebuild vector store from scratch
- Replay batch jobs

---

For implementation details, see the module documentation in the code.
