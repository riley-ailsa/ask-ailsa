# Archived SQLite Implementation

**Status:** DEPRECATED as of November 20, 2025

## Overview
This directory contains the original SQLite-based implementation of Ask Ailsa.
Replaced by PostgreSQL + Pinecone production architecture.

## Why Archived
- ❌ SQLite not suitable for production scale
- ❌ Scrapers moved to separate repositories
- ❌ No concurrent access support
- ✅ Replaced with PostgreSQL (scalable)
- ✅ Replaced with Pinecone (vector search)

## Current Implementation
See main codebase:
- `/src/storage/postgres_store.py` - Production database
- `/src/storage/pinecone_index.py` - Production search
- `/src/api/server.py` - Updated API

## Contents
- `storage/` - Old SQLite storage implementations
- `index/` - Old SQLite vector index
- `ingest/` - Old scraper code (now in separate repos)

## Rollback (Emergency Only)
If needed:
1. Check out git tag: `v1.0-sqlite-legacy`
2. Copy files back from archive
3. Revert server.py changes

## Migration Date
- Deprecated: November 20, 2025
- Archived by: Technical team
- Production replacement: PostgreSQL + Pinecone

⚠️ DO NOT USE THIS CODE IN PRODUCTION
