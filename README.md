# Enterprise Knowledge MCP Server

The **Enterprise Knowledge MCP Server** is a Model Context Protocol (MCP) server that acts as a unified knowledge retrieval bridge between enterprise data silos and LLMs like Claude. It ingests documents from Local Files, Notion, and Google Drive, processes them into semantic embeddings, and exposes them to LLMs via an intelligent vector search tool with built-in citation capabilities.

## 🚀 Key Features

- **Multi-Source Ingestion**: 
  - Local Files (PDF, DOCX, XLSX).
  - Notion (Pages and Databases).
  - Google Drive (Folders and Files).
- **Smart Parsing & Chunking**: Automatic content-type detection and structure-aware chunking for different formats.
- **Semantic Vector Search**: High-performance semantic search using `pgvector` with `BAAI/bge-base-en-v1.5` embeddings.
- **Advanced Retrieval**: Optional Cross-Encoder reranking for higher precision.
- **Change Detection**: Differential syncing minimizes redundant parsing and embedding operations.
- **Enforced Citations**: Built-in prompt engineering that forces the LLM to provide inline references (e.g., `[1]`) mapping directly to the retrieved source documents.
- **Background Auto-Sync**: Automatically syncs with connected Google Drive folders and Notion workspaces every 30 minutes.

## 🛠 Tech Stack

From document parsing to semantic retrieval, the system leverages:

- **Core Framework**: `FastAPI`, `mcp` (Model Context Protocol SDK)
- **Database & Storage**: `PostgreSQL`, `pgvector` (Vector extension)
- **ORM & Migrations**: `SQLAlchemy`, `Alembic`
- **Document Parsing**: `PyMuPDF` (PDFs), `python-docx` (Word documents), `openpyxl` (Excel spreadsheets), `python-magic` (MIME type detection)
- **External Connectors**: `google-api-python-client`, `notion-client`
- **Embeddings & ML**: `sentence-transformers`, `torch`
- **Models Used**: Embedding: `BAAI/bge-base-en-v1.5`, Reranking (Optional): `cross-encoder/ms-marco-MiniLM-L-6-v2`

## 🏗 System Architecture

1. **Source Access Layer**: Connectors fetch data and metadata from various sources.
2. **Content Processing & Normalization**: Format-specific parsers extract structured content, routing it to a normalizer that standardizes it into a unified internal format.
3. **Change Detection**: Hashing mechanisms verify whether a file is new, unchanged, updated, or deleted.
4. **Indexing Pipeline**: Documents are chunked (structure-aware) and converted to vector embeddings.
5. **Storage Layer**: Processed chunks and metadata are persisted in PostgreSQL using `pgvector`.
6. **Retrieval & MCP Layer**: When an LLM requests information, the query is embedded, vectors are searched, optionally reranked, and formatted with citation constraints before being returned to the model.

## ⚙️ Prerequisites

To run the server, ensure your environment meets the following requirements:
- **Python**: 3.10+
- **PostgreSQL**: Must have the [`pgvector`](https://github.com/pgvector/pgvector) extension installed.

### Installing pgvector
Once PostgreSQL is running, connect to your database (`psql -d enterprise_mcp`) and run:
```sql
CREATE EXTENSION vector;
```

## 💻 Setup & Installation Guide

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Enterprise-mcp
```

### 2. Create a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Integration Setup (Google Drive & Notion)

#### Google Drive Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Drive API**.
3. Go to **IAM & Admin > Service Accounts** and create a new service account.
4. Go to the "Keys" tab, click "Add Key" > "Create new key" (JSON). Download this file.
5. In Google Drive, share the folder you want to index with the service account's email address.

#### Notion Setup
1. Go to [Notion My Integrations](https://www.notion.so/my-integrations).
2. Create a new "Internal Integration".
3. Copy the "Internal Integration Secret" (this is your `NOTION_API_KEY`).
4. In Notion, go to the root page/database you want to index, click the `...` menu, select "Add Connections", and choose your integration.

### 5. Configure Environment Variables
Create a `.env` file by copying the provided example:
```bash
cp .env.example .env
```

#### Environment Variables Reference
| Variable | Description | Default | Required |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/enterprise_mcp` | Yes |
| `UPLOAD_DIR` | Directory for local file uploads | `./uploads` | No |
| `MAX_FILE_SIZE_MB` | Maximum file size for uploads | `50` | No |
| `ENABLE_RERANKER` | Enable Cross-Encoder reranking | `true` | No |
| `RERANKER_MODEL` | HuggingFace model for reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | No |
| `RETRIEVAL_TOP_K` | Initial chunks retrieved from pgvector | `20` | No |
| `RETRIEVAL_FINAL_K` | Final chunks returned after reranking | `5` | No |
| `GOOGLE_DRIVE_CREDENTIALS_JSON`| Path to downloaded service account JSON | N/A | For GDrive |
| `GOOGLE_DRIVE_FOLDER_ID` | ID of the shared Google Drive folder | N/A | For GDrive |
| `GOOGLE_DRIVE_SYNC_INTERVAL_MINUTES` | Frequency of Drive auto-sync | `30` | No |
| `NOTION_API_KEY` | Notion Internal Integration Secret | N/A | For Notion |
| `NOTION_ROOT_PAGE_ID` | Root Notion page ID to index | N/A | For Notion |
| `NOTION_SYNC_INTERVAL_MINUTES`| Frequency of Notion auto-sync | `30` | No |

### 6. Run Database Migrations
Initialize your database schema using Alembic:
```bash
alembic upgrade head
```

## 🚀 Running the Server

### Starting the MCP Server
You can run the server directly using your virtual environment's Python interpreter:
```bash
python mcp_server.py
```
*(Note: MCP servers communicate over stdio, so you won't see traditional web server logs unless you redirect stderr. Background sync tasks will log to `mcp_server.log`).*

### Connecting to Claude Desktop
To add this server to your Claude Desktop application, edit your `claude_desktop_config.json` file:
```json
{
  "mcpServers": {
    "enterprise-knowledge": {
      "command": "/absolute/path/to/Enterprise-mcp/venv/bin/python",
      "args": ["/absolute/path/to/Enterprise-mcp/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/Enterprise-mcp"
      }
    }
  }
}
```

## 🧰 Available MCP Tools

When connected, the server exposes the following tools to the LLM:

| Tool Name | Description | Parameters |
|---|---|---|
| `search_knowledge` | Performs semantic search across all indexed documents. | `query` (str), `source_type` (optional), `content_type` (optional), `document_id` (optional), `document_title` (optional), `limit` (int) |
| `list_documents` | Lists indexed documents matching the criteria. | `search` (str), `source_type` (optional), `content_type` (optional), `limit` (int), `offset` (int) |

## 💡 Usage Examples

### Querying via Claude
Once the MCP server is attached, prompt Claude:
> "Search our enterprise knowledge for the main takeaways from the recent 'FTX Scandal' report."

**Sample Output from Claude:**
> Based on the retrieved documents, the main takeaway is that inadequate risk management led to rapid liquidity issues [1]. Furthermore, customer funds were inappropriately mingled with trading capital [2].
> 
> ### Sources
> [1] FTX Scandal Report (page 3)
> [2] FTX Scandal Report (page 5)

### Uploading Local Files
While Notion and Google Drive sync automatically, local files can be ingested via the built-in FastAPI upload endpoint. Assuming you are running the FastAPI app (e.g., via `uvicorn`), you can upload files using `curl`:
```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"
```

## 🐛 Troubleshooting

- **`NameError: name 'Literal' is not defined`**: Ensure that `Literal` is imported from `typing` in `mcp_server.py`.
- **`pgvector` missing error**: Ensure you have successfully run `CREATE EXTENSION vector;` in your PostgreSQL database.
- **Claude doesn't see tools**: Verify that the path to the Python interpreter and `mcp_server.py` are absolute and correct in your `claude_desktop_config.json`.
- **Missing search results**: Ensure the background ingestion tasks have run (check `mcp_server.log`) and that documents were successfully chunked and embedded.

## 📁 Project Structure

```text
Enterprise-mcp/
├── app/
│   ├── connectors/     # Google Drive & Notion sync services
│   ├── embedding/      # Sentence-Transformer models setup
│   ├── ingestion/      # Pipeline for hashing & processing
│   ├── models/         # SQLAlchemy DB models (Document, DocumentChunk)
│   ├── parsers/        # Extractor logic for PDF, DOCX, XLSX
│   ├── retrieval/      # pgvector search & cross-encoder reranking
│   └── schemas/        # Pydantic validation schemas
├── mcp_server.py       # Main entry point & MCP tool definitions
├── requirements.txt    # Project dependencies
├── alembic.ini         # Alembic configuration
└── README.md           # This file
```
