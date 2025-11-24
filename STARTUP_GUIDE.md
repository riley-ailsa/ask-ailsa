# Grant Discovery Startup Guide

## System Architecture

The Grant Discovery system uses a **Hybrid RAG architecture**:

- **Vector Search**: Pinecone (cloud-hosted, 112k+ vectors)
- **Metadata Storage**: PostgreSQL (Docker, 4,260+ grants)
- **Cache**: SQLite (explanation_cache)
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: GPT-4o-mini

## Prerequisites

1. **PostgreSQL Container** must be running:
   ```bash
   docker ps | grep ailsa-postgres
   ```

   If not running, start it:
   ```bash
   docker start ailsa-postgres
   ```

2. **Environment Variables** in `.env`:
   ```
   DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/ailsa
   PINECONE_API_KEY=pcsk_...
   OPENAI_API_KEY=sk-proj-...
   PINECONE_INDEX_NAME=ailsa-grants
   ```

## Starting the System

### Option 1: Full Stack (Recommended)
```bash
./start.sh
```

This will:
1. Check PostgreSQL is running
2. Start the API server (port 8000)
3. Wait for API to be healthy
4. Start the Streamlit UI (port 8501)

**Press Ctrl+C** to stop both services.

### Option 2: Manual Start (For Development)

**Terminal 1 - API Server:**
```bash
./start_api.sh
```

**Terminal 2 - Streamlit UI:**
```bash
./start_ui.sh
```

## Verifying the System

### 1. Check Health Endpoint
```bash
curl http://localhost:8000/health | python -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "postgres_grants": 4260,
  "pinecone_vectors": 112468,
  "hybrid_rag": {
    "enabled": true,
    "has_data": true,
    "ratio_ok": true,
    "avg_vectors_per_grant": 26.4
  }
}
```

### 2. Test Search
```bash
curl "http://localhost:8000/search?query=NIHR+grants&top_k=5&active_only=false"
```

### 3. Run Evaluation Suite
```bash
python run_eval.py
```

Expected results:
- ✅ 3-4 passing tests (37.5%+)
- ⚠️ 3-4 partial matches (37.5%+)
- ❌ 1-2 failing tests (25%)

## Troubleshooting

### "PostgreSQL container is not running"
```bash
docker start ailsa-postgres
```

### "Database connection failed"
Check DATABASE_URL in `.env` matches the container:
```bash
docker inspect ailsa-postgres | grep IPAddress
```

### "Pinecone connection failed"
Verify API key in `.env`:
```bash
grep PINECONE_API_KEY .env
```

### "Search returns 0 results"
This was fixed in commit fixing the grant_id extraction from Pinecone metadata. The issue was:
- Pinecone stores document chunks with IDs like `nihr_123_chunk_5`
- The actual grant ID is in `metadata['grant_id']`
- We now correctly extract and deduplicate grant IDs

### API server won't start
Check logs:
```bash
tail -f logs/api.log  # if logging to file
```

Or run directly to see errors:
```bash
python -m src.scripts.run_api
```

## System Status

**Current State (as of 2025-11-21):**
- ✅ PostgreSQL migration complete (4,260 grants)
- ✅ Pinecone migration complete (112,468 vectors)
- ✅ Hybrid RAG search working
- ✅ API health checks passing
- ✅ Search evaluation: 75% passing/partial
- ✅ start.sh fixed to use correct paths

**Known Issues:**
- Some evaluation queries still need refinement
- Innovate UK queries have lower match rates
- Need to improve synonym/term expansion

## API Endpoints

- `GET /health` - System health check
- `GET /grants` - List all grants
- `GET /grants/{grant_id}` - Get grant details
- `GET /search` - Hybrid semantic search
- `POST /chat/enhanced/stream` - Conversational interface with streaming
- `GET /docs` - Interactive API documentation

## UI Access

Once started:
- **Frontend**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Development Notes

### Search Architecture
The `/search` endpoint uses hybrid retrieval:

1. **Generate embedding** for query (OpenAI)
2. **Vector search** in Pinecone (over-fetch 3x for filtering)
3. **Extract grant IDs** from metadata (not chunk IDs!)
4. **Bulk fetch** full grants from PostgreSQL
5. **Apply filters** (active_only, funding, source)
6. **Deduplicate** grants (same grant may have multiple chunks)
7. **Sort by relevance** score (Pinecone cosine similarity)

### File Structure
- `start.sh` - Main startup script
- `start_api.sh` - API-only startup
- `start_ui.sh` - UI-only startup (checks API first)
- `run_eval.py` - Search quality evaluation
- `evaluation_queries.json` - Test queries
- `src/api/server.py` - FastAPI backend
- `ui/app.py` - Streamlit frontend
- `src/storage/postgres_store.py` - PostgreSQL adapter
- `src/storage/pinecone_index.py` - Pinecone adapter

### Database Schema
PostgreSQL stores grants with fields:
- `id` (primary key, e.g., "nihr_123")
- `external_id` (source system ID)
- `source` (nihr, innovate_uk, etc.)
- `title`, `description`
- `opens_at`, `closes_at`
- `status`, `scope`
- `total_fund_gbp`
- JSON metadata fields

Pinecone stores document chunks with:
- Vector ID: `{grant_id}_{doc_type}_{hash}_chunk_{n}`
- Metadata includes: `grant_id`, `source`, `status`, `title`, etc.
- Each grant has ~26 vectors on average

## Support

For issues or questions:
1. Check this guide
2. Review recent commits for related fixes
3. Check API logs for errors
4. Test individual components (PostgreSQL, Pinecone, API)
