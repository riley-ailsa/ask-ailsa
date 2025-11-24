"""
Pinecone vector search adapter.

Replaces the old SQLite VectorIndex with Pinecone cloud backend.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI

logger = logging.getLogger(__name__)


class PineconeVectorIndex:
    """Pinecone adapter for vector similarity search."""

    def __init__(self):
        """Initialize Pinecone and OpenAI clients."""
        # Get API keys from environment
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        if not self.pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable is required")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        try:
            # Initialize Pinecone client
            self.pc = Pinecone(api_key=self.pinecone_api_key)
            self.index_name = "ailsa-grants"
            self.index = self.pc.Index(self.index_name)

            # Initialize OpenAI client for embeddings
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            self.embedding_model = "text-embedding-3-small"

            logger.info(f"Pinecone index '{self.index_name}' connected successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone/OpenAI clients: {e}")
            raise

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using OpenAI.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 10,
        source: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for grants using vector similarity.

        Args:
            query: Search query text
            top_k: Number of results to return (default: 10)
            source: Optional filter by source (e.g., "nihr", "horizon_europe")
            status: Optional filter by status (e.g., "Open", "Closed", "Forthcoming")

        Returns:
            List of dictionaries with grant_id, score, and metadata:
            [
                {
                    "grant_id": "nihr:XXX",
                    "score": 0.85,
                    "metadata": {"source": "nihr", "title": "...", "status": "Open"}
                },
                ...
            ]
        """
        try:
            # Generate embedding for the query
            query_embedding = self._generate_embedding(query)

            # Build metadata filters
            filters = {}
            if source:
                filters["source"] = source
            if status:
                filters["status"] = status

            # Query Pinecone
            query_params = {
                "vector": query_embedding,
                "top_k": top_k,
                "include_metadata": True
            }

            # Only add filter if we have any filters
            if filters:
                query_params["filter"] = filters

            results = self.index.query(**query_params)

            # Log detailed search results for debugging
            logger.info(f"=== PINECONE RESULTS FOR: {query[:50]}... ===")
            for i, match in enumerate(results.matches[:10], 1):
                metadata = match.metadata or {}
                title = metadata.get('title', metadata.get('grant_title', 'N/A'))
                source = metadata.get('source', 'N/A')
                grant_id = metadata.get('grant_id', match.id)
                logger.info(f"  {i}. [{match.score:.3f}] {title[:60]} ({source}) - {grant_id}")
            logger.info(f"=== END RESULTS (showing top 10 of {len(results.matches)}) ===")

            # Format results
            # IMPORTANT: match.id is the chunk ID (e.g., "nihr_123_chunk_5")
            # The actual grant_id is in metadata['grant_id']
            formatted_results = []
            for match in results.matches:
                metadata = match.metadata or {}
                grant_id = metadata.get('grant_id', match.id)  # Fallback to match.id if no grant_id in metadata
                formatted_results.append({
                    "grant_id": grant_id,
                    "score": float(match.score),
                    "metadata": metadata
                })

            logger.info(f"Vector search returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Error performing vector search: {e}")
            raise

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get Pinecone index statistics.

        Returns:
            Dictionary with index statistics:
            {
                "total_vectors": 4500,
                "dimension": 1536,
                "index_fullness": 0.05,
                "namespaces": {...}
            }
        """
        try:
            stats = self.index.describe_index_stats()

            # Convert to dictionary format
            result = {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": {}
            }

            # Add namespace information if available
            if hasattr(stats, 'namespaces') and stats.namespaces:
                result["namespaces"] = {
                    ns: {"vector_count": info.vector_count}
                    for ns, info in stats.namespaces.items()
                }

            logger.info(f"Index stats: {result['total_vectors']} vectors, dimension {result['dimension']}")
            return result

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            raise

    def close(self):
        """
        Close connections (if needed).

        Pinecone client handles connection pooling internally,
        but this method is provided for interface compatibility.
        """
        logger.info("Pinecone client closed (connection pooling handled internally)")
