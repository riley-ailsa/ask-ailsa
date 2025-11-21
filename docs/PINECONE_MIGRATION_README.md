# Pinecone Migration Guide

This guide explains how to migrate all your grants and embeddings from SQLite to Pinecone.

## Current Database Status

- **486 grants** (450 NIHR + 36 Innovate UK)
- **5,853 documents**
- **108,658 embeddings** (pre-generated, ready to upload!)
- **Existing Pinecone index**: `ailsa-grants` (currently has 3,734 vectors)

## Migration Script

The script [`scripts/migrate_all_to_pinecone.py`](scripts/migrate_all_to_pinecone.py) handles the complete migration.

### What it does:

1. ✅ Reads all grants from SQLite `grants.db`
2. ✅ Reads all documents from SQLite
3. ✅ Reads all pre-generated embeddings (no re-computation needed!)
4. ✅ Uploads everything to your Pinecone index: `ailsa-grants`
5. ✅ Preserves all metadata (grant_id, doc_id, text, URLs, etc.)
6. ✅ Creates a JSON backup of metadata
7. ✅ Shows progress bars and statistics

### Features:

- **Batch uploads** (default: 100 vectors per batch)
- **Resume capability** (restartable if interrupted)
- **Dry-run mode** for previewing
- **Error handling** with detailed logging
- **Progress tracking** with tqdm

## Quick Start

### 1. Preview the migration (dry-run)

```bash
export PINECONE_API_KEY="pcsk_6R6Zuv_JR2YcZgUN58HfuoC1mNGnKgEofzEQQh3fmumQTCas9vZGdLQeAbuQJr9tHJmE5p"
python scripts/migrate_all_to_pinecone.py --dry-run
```

This will:
- Connect to Pinecone
- Show database statistics
- Preview 5 sample vectors
- NOT upload anything

### 2. Run the full migration

```bash
python scripts/migrate_all_to_pinecone.py
```

This will:
- Upload all 108,658 embeddings to Pinecone
- Create a metadata backup file: `pinecone_metadata_backup_YYYYMMDD_HHMMSS.json`
- Show progress bars
- Print detailed statistics

**Estimated time**: ~18 minutes (100 vectors/sec upload rate)

### 3. Test the connection first (optional)

```bash
python scripts/test_pinecone_connection.py
```

This verifies:
- Pinecone API key is valid
- Connection works
- Lists existing indexes
- Shows current index stats

## Advanced Options

### Custom batch size

Upload 200 vectors per batch (faster):
```bash
python scripts/migrate_all_to_pinecone.py --batch-size 200
```

### Custom index name

If you want to use a different index:
```bash
python scripts/migrate_all_to_pinecone.py --index-name my-custom-index
```

### Different region

```bash
python scripts/migrate_all_to_pinecone.py --region us-west-2
```

### Skip metadata backup

```bash
python scripts/migrate_all_to_pinecone.py --skip-backup
```

## Full Command Line Options

```bash
python scripts/migrate_all_to_pinecone.py --help

Options:
  --db PATH              SQLite database path (default: grants.db)
  --index-name NAME      Pinecone index name (default: ailsa-grants)
  --dimension N          Embedding dimension (default: 1536)
  --metric METRIC        Distance metric: cosine|euclidean|dotproduct (default: cosine)
  --cloud PROVIDER       Cloud provider: aws|gcp|azure (default: aws)
  --region REGION        Cloud region (default: us-east-1)
  --batch-size N         Vectors per batch (default: 100)
  --dry-run              Preview only, don't upload
  --skip-backup          Skip metadata backup file
  --pinecone-api-key KEY API key (or use PINECONE_API_KEY env var)
```

## What Gets Uploaded to Pinecone

Each vector in Pinecone contains:

### Vector ID
- Format: `{grant_id}_section_{section_name}_chunk_{chunk_index}`
- Example: `nihr_22-22-NIHR132342_section_overview_chunk_0`

### Vector Values
- 1536-dimensional embedding (text-embedding-3-small)
- Pre-computed from SQLite (no API calls needed!)

### Metadata
- `grant_id`: Parent grant ID
- `doc_id`: Document ID
- `chunk_index`: Chunk number for long documents
- `text`: The actual text chunk
- `source_url`: Original source URL
- `doc_type`: Type (e.g., "competition_section", "briefing_pdf")
- `scope`: "competition" or "global"

## Monitoring Progress

During migration, you'll see:

```
DATABASE STATISTICS
================================================================================
total_grants                   486
grants_innovate_uk             36
grants_nihr                    450
total_documents                5853
total_embeddings               108658
================================================================================

Uploading vectors: 100%|████████████████| 108658/108658 [18:32<00:00, 97.64 vectors/s]

MIGRATION SUMMARY
================================================================================
Grants read:        486
Documents read:     5853
Embeddings read:    108658
Vectors uploaded:   108658
Errors:             0
Elapsed time:       1112.4s (18.5min)
Upload rate:        97.6 vectors/sec
================================================================================
```

## Logs

Migration logs are saved to:
- `migration_to_pinecone.log` - Detailed log file
- Console output - Real-time progress

## Important Notes

### ⚠️ The existing `ailsa-grants` index has 3,734 vectors

The migration will **ADD** vectors to the existing index. If you want a fresh start:

```python
from pinecone import Pinecone

pc = Pinecone(api_key="your-api-key")
pc.delete_index("ailsa-grants")  # Delete existing index
# Then run migration script (it will create a new index)
```

### 📦 Metadata Backup

A JSON backup is created with all grants and documents metadata:
- Filename: `pinecone_metadata_backup_YYYYMMDD_HHMMSS.json`
- Contains: All grants, documents, and statistics
- Use this to restore metadata if needed

### 🔄 Resumability

If the migration is interrupted:
1. Just re-run the script
2. Pinecone will skip duplicate vector IDs
3. Only new/missing vectors will be uploaded

## Querying Pinecone After Migration

Example Python code to query your migrated data:

```python
from pinecone import Pinecone
from openai import OpenAI

# Initialize clients
pc = Pinecone(api_key="your-pinecone-key")
openai_client = OpenAI(api_key="your-openai-key")
index = pc.Index("ailsa-grants")

# Create query embedding
query = "quantum computing research grants"
response = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=query
)
query_embedding = response.data[0].embedding

# Search Pinecone
results = index.query(
    vector=query_embedding,
    top_k=10,
    include_metadata=True
)

# Display results
for match in results.matches:
    print(f"Score: {match.score:.3f}")
    print(f"Grant: {match.metadata['grant_id']}")
    print(f"Text: {match.metadata['text'][:200]}...")
    print(f"URL: {match.metadata['source_url']}")
    print()
```

## Troubleshooting

### Error: "no such table: embeddings"
- Make sure you're pointing to the correct database file
- Default: `grants.db` in current directory

### Error: "Pinecone API key not provided"
- Set environment variable: `export PINECONE_API_KEY="your-key"`
- Or use `--pinecone-api-key` flag

### Slow upload speed
- Increase batch size: `--batch-size 200`
- Check network connection
- Pinecone free tier has rate limits

### Out of memory
- Decrease batch size: `--batch-size 50`
- The script loads batches incrementally, so memory should be stable

## Next Steps

After migration, you can:

1. **Delete the SQLite embeddings table** to save space (~300MB):
   ```sql
   sqlite3 grants.db "DROP TABLE embeddings;"
   ```

2. **Update your application** to query Pinecone instead of SQLite

3. **Add new grants** directly to Pinecone (no SQLite needed)

4. **Scale up** with Pinecone's managed infrastructure

## Support

Questions or issues? Check the migration log file:
```bash
tail -f migration_to_pinecone.log
```

---

**Ready to migrate?** Start with a dry-run:
```bash
export PINECONE_API_KEY="pcsk_6R6Zuv_JR2YcZgUN58HfuoC1mNGnKgEofzEQQh3fmumQTCas9vZGdLQeAbuQJr9tHJmE5p"
python scripts/migrate_all_to_pinecone.py --dry-run
```
