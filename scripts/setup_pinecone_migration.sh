#!/bin/bash
#
# Setup script for Pinecone migration
# Installs required dependencies and sets environment variables
#

set -e

echo "=========================================="
echo "Pinecone Migration Setup"
echo "=========================================="
echo ""

# Check Python version
echo "1. Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   ✓ Python $python_version"
echo ""

# Install Pinecone
echo "2. Installing Pinecone client..."
pip install -q pinecone-client
echo "   ✓ Pinecone client installed"
echo ""

# Install other dependencies
echo "3. Installing other dependencies..."
pip install -q tqdm
echo "   ✓ tqdm installed"
echo ""

# Set environment variable
echo "4. Setting up environment..."
export PINECONE_API_KEY="pcsk_6R6Zuv_JR2YcZgUN58HfuoC1mNGnKgEofzEQQh3fmumQTCas9vZGdLQeAbuQJr9tHJmE5p"
echo "   ✓ PINECONE_API_KEY set"
echo ""

# Verify database exists
echo "5. Checking database..."
if [ -f "grants.db" ]; then
    db_size=$(du -h grants.db | awk '{print $1}')
    echo "   ✓ Found grants.db ($db_size)"
else
    echo "   ✗ grants.db not found!"
    exit 1
fi
echo ""

# Count records
echo "6. Database statistics..."
grant_count=$(sqlite3 grants.db "SELECT COUNT(*) FROM grants;")
doc_count=$(sqlite3 grants.db "SELECT COUNT(*) FROM documents;")
emb_count=$(sqlite3 grants.db "SELECT COUNT(*) FROM embeddings;")

echo "   Grants:     $grant_count"
echo "   Documents:  $doc_count"
echo "   Embeddings: $emb_count"
echo ""

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Preview migration (no upload):"
echo "     python scripts/migrate_all_to_pinecone.py --dry-run"
echo ""
echo "  2. Run full migration:"
echo "     python scripts/migrate_all_to_pinecone.py"
echo ""
echo "  3. Or with custom settings:"
echo "     python scripts/migrate_all_to_pinecone.py --batch-size 200 --region us-west-2"
echo ""
