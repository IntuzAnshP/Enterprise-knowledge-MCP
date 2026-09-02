1.Complete System Overview

┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                            │
│                                                                 │
│   Local Files              External Sources                     │
│   ├── PDF                  ├── Notion                          │
│   ├── DOCX                 └── Google Drive                    │
│   └── XLSX                                                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SOURCE ACCESS LAYER                         │
│                                                                 │
│  Local Upload Service     Notion Connector    Google Drive      │
│                                                Connector        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                          SOURCE ITEM
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CONTENT PROCESSING LAYER                      │
│                                                                 │
│              Content Type Detection / Routing                   │
│                                                                 │
│      ┌────────────┬────────────┬────────────┬─────────────┐    │
│      ▼            ▼            ▼            ▼             │    │
│   PDF Parser   DOCX Parser  XLSX Parser  Notion Extractor │    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                        EXTRACTED DOCUMENT
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NORMALIZATION LAYER                          │
│                                                                 │
│                 Source-specific data                            │
│                         ↓                                       │
│                    Normalizer                                   │
│                         ↓                                       │
│                 NormalizedDocument                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CHANGE DETECTION                            │
│                                                                 │
│              Source ID + Timestamp + Content Hash               │
│                                                                 │
│        ┌───────────────┬───────────────┬───────────────┐        │
│        ▼               ▼               ▼                │        │
│       NEW          UNCHANGED        UPDATED          DELETED     │
│        │               │               │                │        │
│        ▼               ▼               ▼                ▼        │
│      INDEX            SKIP          RE-INDEX          REMOVE     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                         New / Updated
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INDEXING PIPELINE                           │
│                                                                 │
│                   NormalizedDocument                            │
│                           │                                     │
│                           ▼                                     │
│                 Structure-aware Chunking                        │
│                           │                                     │
│                           ▼                                     │
│                    Document Chunks                              │
│                           │                                     │
│                           ▼                                     │
│                  Embedding Generation                           │
│                           │                                     │
│                           ▼                                     │
│                   Chunk + Embedding                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                            │
│                                                                 │
│                    PostgreSQL + pgvector                        │
│                                                                 │
│   Documents                                                     │
│      ├── Source Information                                     │
│      ├── Metadata                                               │
│      ├── Content Hash                                           │
│      └── Source URL                                             │
│                                                                 │
│   Document Chunks                                               │
│      ├── Chunk Content                                          │
│      ├── Chunk Metadata                                         │
│      ├── Citation Information                                   │
│      └── Embedding Vector                                       │
└─────────────────────────────────────────────────────────────────┘




2. Ingestion 

The ingestion pipeline is responsible for converting raw knowledge from different sources into searchable vectors.

DATA SOURCE
    │
    ▼
SOURCE ACCESS
    │
    ▼
SOURCE ITEM
    │
    ▼
CONTENT TYPE DETECTION
    │
    ▼
PARSER / EXTRACTOR
    │
    ▼
EXTRACTED DOCUMENT
    │
    ▼
NORMALIZER
    │
    ▼
NORMALIZED DOCUMENT
    │
    ▼
CHANGE DETECTION
    │
    ├── Unchanged → Skip
    │
    ├── New → Index
    │
    └── Updated → Re-index
                     │
                     ▼
                CHUNKING
                     │
                     ▼
                EMBEDDING
                     │
                     ▼
             POSTGRESQL + PGVECTOR
3. Local Document Pipeline
User
  │
  ▼
Upload PDF / DOCX / XLSX
  │
  ▼
FastAPI Upload API
  │
  ▼
Local File Storage
  │
  ▼
Content Type Detection
  │
  ├── PDF  → PDF Parser
  │
  ├── DOCX → DOCX Parser
  │
  └── XLSX → XLSX Parser
              │
              ▼
       ExtractedDocument
              │
              ▼
          Normalizer
              │
              ▼
       NormalizedDocument
              │
              ▼
       Change Detection
              │
              ▼
       Chunk + Embed + Store
4. Notion Pipeline
Notion
  │
  ▼
Notion API
  │
  ▼
Notion Connector
  │
  ▼
Fetch Pages + Metadata
  │
  ▼
Notion Content Extractor
  │
  ▼
Convert Blocks → Structured Text
  │
  ▼
ExtractedDocument
  │
  ▼
Normalizer
  │
  ▼
NormalizedDocument
  │
  ▼
Change Detection
  │
  ├── Unchanged → Skip
  │
  └── New / Updated
           │
           ▼
      Chunk + Embed
           │
           ▼
 PostgreSQL + pgvector
5. Google Drive Pipeline

Google Drive can contain different document types, so it uses both a connector and your existing parsers.

Google Drive
  │
  ▼
Google Drive API
  │
  ▼
Google Drive Connector
  │
  ▼
Fetch File + Metadata
  │
  ▼
Content Type Detection
  │
  ├── PDF
  │     ▼
  │  PDF Parser
  │
  ├── DOCX
  │     ▼
  │  DOCX Parser
  │
  └── XLSX
        ▼
     XLSX Parser
        │
        ▼
 ExtractedDocument
        │
        ▼
    Normalizer
        │
        ▼
 NormalizedDocument
        │
        ▼
 Change Detection
        │
        ▼
 Chunk + Embed + Store
6. Database Structure

At a high level:

┌──────────────────────┐
│      DOCUMENTS       │
├──────────────────────┤
│ id                   │
│ source_type          │
│ source_id            │
│ title                │
│ content_type         │
│ content_hash         │
│ source_url           │
│ source_updated_at    │
│ metadata             │
│ created_at           │
│ updated_at           │
└───────────┬──────────┘
            │
            │ 1
            │
            │ N
            ▼
┌──────────────────────┐
│   DOCUMENT CHUNKS    │
├──────────────────────┤
│ id                   │
│ document_id          │
│ chunk_index          │
│ content              │
│ metadata             │
│ embedding            │
│ citation_metadata    │
└──────────────────────┘

One document can have many chunks.

Each chunk has its own embedding.

7. Query / Retrieval Pipeline

This is the most important pipeline during user interaction.

Remember:

Your MCP server retrieves information. Claude generates the final answer.

USER
  │
  ▼
CLAUDE
  │
  │ "I need information from enterprise knowledge"
  │
  ▼
MCP TOOL CALL
  │
  ▼
┌─────────────────────────────┐
│      YOUR MCP SERVER        │
│                             │
│    search_knowledge()       │
└──────────────┬──────────────┘
               │
               ▼
        RETRIEVAL SERVICE
               │
               ▼
        QUERY EMBEDDING
               │
               ▼
       PGVECTOR SEARCH
               │
               ▼
      TOP-K RELEVANT CHUNKS
               │
               ▼
       METADATA FILTERING
               │
               ▼
      FINAL RELEVANT CHUNKS
               │
               ▼
      CITATION PREPARATION
               │
               ▼
          MCP RESPONSE
               │
               ▼
            CLAUDE
               │
               ▼
      FINAL USER ANSWER
8. Retrieval With Optional Reranking

Your advanced pipeline can look like this:

User Query
    │
    ▼
Claude
    │
    ▼
search_knowledge()
    │
    ▼
Query Embedding
    │
    ▼
pgvector Similarity Search
    │
    ▼
Top 20 Candidate Chunks
    │
    ▼
Optional Reranker
    │
    ▼
Top 5 Relevant Chunks
    │
    ▼
Citation Formatting
    │
    ▼
Return MCP Response
    │
    ▼
Claude
    │
    ▼
Final Answer

For your initial implementation, you can skip reranking:

Query
  ↓
Embedding
  ↓
pgvector Search
  ↓
Top 5–10
  ↓
Claude
9. Document Update / Synchronization Pipeline

This handles updates in Notion and Google Drive.

Scheduled Sync / Webhook
          │
          ▼
      Connector
          │
          ▼
Fetch Source Metadata
          │
          ▼
Compare Source ID
          │
          ▼
Compare Modified Timestamp
          │
          ▼
Fetch Updated Content
          │
          ▼
Generate Content Hash
          │
          ▼
Compare With Stored Hash
          │
     ┌────┴─────┐
     │          │
     ▼          ▼
   SAME      CHANGED
     │          │
     ▼          ▼
    SKIP     RE-INDEX
                │
                ▼
           Re-extract
                │
                ▼
            Re-chunk
                │
                ▼
            Re-embed
                │
                ▼
       Replace Old Chunks
                │
                ▼
        Update Document Record
10. Background Processing Pipeline

External synchronization and document ingestion should eventually run in the background.

Upload / Connector Sync
         │
         ▼
   Create Ingestion Job
         │
         ▼
   Background Worker
         │
         ├── Extract
         ├── Normalize
         ├── Detect Changes
         ├── Chunk
         ├── Generate Embeddings
         └── Store in Database

This prevents large documents from blocking API requests.

11. Complete End-to-End Architecture
                         INGESTION SIDE

┌───────────────────────────────────────────────────────────────┐
│                       DATA SOURCES                            │
│                                                               │
│  Local PDF/DOCX/XLSX       Notion       Google Drive          │
└───────────────┬───────────────┬──────────────┬────────────────┘
                │               │              │
                ▼               ▼              ▼
        Upload Service      Connector      Connector
                │               │              │
                └───────────────┼──────────────┘
                                ▼
                           SourceItem
                                │
                                ▼
                      Parser / Extractor
                                │
                                ▼
                        ExtractedDocument
                                │
                                ▼
                           Normalizer
                                │
                                ▼
                        NormalizedDocument
                                │
                                ▼
                        Change Detection
                                │
                                ▼
                            Chunking
                                │
                                ▼
                           Embeddings
                                │
                                ▼
                     PostgreSQL + pgvector


                         RETRIEVAL SIDE

User
 │
 ▼
Claude
 │
 ▼
MCP Tool Call
 │
 ▼
┌───────────────────────────┐
│     ENTERPRISE KNOWLEDGE  │
│        MCP SERVER         │
│                           │
│   Retrieval Layer         │
└──────────────┬────────────┘
               │
               ▼
         Query Embedding
               │
               ▼
       pgvector Search
               │
               ▼
       Top-K Candidates
               │
               ▼
       Optional Reranking
               │
               ▼
       Final Relevant Chunks
               │
               ▼
         MCP Response
               │
               ▼
             Claude
               │
               ▼
        Final User Answer
Core Principle of Your Architecture
CONNECTORS
    ↓
Bring data into the system

PARSERS / EXTRACTORS
    ↓
Extract meaningful content

NORMALIZER
    ↓
Convert everything into one internal format

INGESTION PIPELINE
    ↓
Chunk + Embed + Store

RETRIEVAL LAYER
    ↓
Find relevant chunks

MCP SERVER
    ↓
Expose retrieval as MCP tools

CLAUDE
    ↓
Generate the final answer