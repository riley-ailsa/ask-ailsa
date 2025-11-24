"""
PostgreSQL adapter for grant storage.

Replaces the old SQLite GrantStore with PostgreSQL backend.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from src.core.domain_models import Grant

logger = logging.getLogger(__name__)


class PostgresGrantStore:
    """PostgreSQL adapter for grant data storage."""

    def __init__(self):
        """Initialize PostgreSQL connection."""
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        try:
            # Create connection pool for better performance
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.database_url
            )
            logger.info("PostgreSQL connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise

    def _get_connection(self):
        """Get a connection from the pool."""
        try:
            return self.pool.getconn()
        except Exception as e:
            logger.error(f"Failed to get connection from pool: {e}")
            raise

    def _release_connection(self, conn):
        """Return a connection to the pool."""
        if conn:
            self.pool.putconn(conn)

    def _row_to_grant(self, row: Dict[str, Any]) -> Grant:
        """Convert a database row dictionary to a Grant domain object."""
        # Determine if grant is active based on status
        is_active = row['status'] in ('Open', 'Forthcoming')

        # Convert funding to display string
        budget_min = row.get('budget_min')
        budget_max = row.get('budget_max')
        total_fund = None
        total_fund_gbp = None

        if budget_max:
            total_fund_gbp = budget_max
            # Format as string (millions if large)
            if budget_max >= 1_000_000:
                total_fund = f"£{budget_max / 1_000_000:.1f}M"
            else:
                total_fund = f"£{budget_max:,}"
        elif budget_min:
            total_fund_gbp = budget_min
            if budget_min >= 1_000_000:
                total_fund = f"£{budget_min / 1_000_000:.1f}M"
            else:
                total_fund = f"£{budget_min:,}"

        return Grant(
            id=row['grant_id'],
            source=row['source'],
            title=row['title'],
            description=row.get('description_summary', ''),
            url=row['url'],
            external_id=row.get('call_id'),
            opens_at=row.get('open_date'),
            closes_at=row.get('close_date'),
            is_active=is_active,
            total_fund=total_fund,
            total_fund_gbp=total_fund_gbp,
            tags=row.get('tags', []) or [],
            updated_at=row.get('updated_at', datetime.utcnow())
        )

    def get_grant(self, grant_id: str) -> Optional[Grant]:
        """
        Get a single grant by ID.

        Args:
            grant_id: The grant identifier

        Returns:
            Grant object or None if not found
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    grant_id, source, title, url, status,
                    open_date, close_date, programme, tags,
                    description_summary, budget_min, budget_max,
                    eligible_countries, duration, updated_at,
                    call_id, programme_area, action_type,
                    funding_rate_percent, organization_types,
                    consortium_required, min_partners
                FROM grants
                WHERE grant_id = %s
            """

            cursor.execute(query, (grant_id,))
            result = cursor.fetchone()
            cursor.close()

            if result:
                return self._row_to_grant(dict(result))
            return None

        except Exception as e:
            logger.error(f"Error getting grant {grant_id}: {e}")
            raise
        finally:
            self._release_connection(conn)

    def list_grants(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        active_only: bool = False
    ) -> List[Grant]:
        """
        List grants with optional filtering.

        Args:
            source: Filter by source (e.g., "horizon_europe", "nihr")
            status: Filter by status (e.g., "Open", "Closed", "Forthcoming")
            limit: Maximum number of results
            offset: Number of results to skip
            active_only: Filter for only active (Open/Forthcoming) grants

        Returns:
            List of Grant objects
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Build query with filters
            query = """
                SELECT
                    grant_id, source, title, url, status,
                    open_date, close_date, programme, tags,
                    description_summary, budget_min, budget_max,
                    eligible_countries, duration, updated_at,
                    call_id, programme_area, action_type,
                    funding_rate_percent, organization_types,
                    consortium_required, min_partners
                FROM grants
                WHERE 1=1
            """
            params = []

            if source:
                query += " AND source = %s"
                params.append(source)

            if status:
                query += " AND status = %s"
                params.append(status)

            if active_only:
                query += " AND status IN ('Open', 'Forthcoming')"

            # Sort by status priority and close date
            query += """
                ORDER BY
                    CASE status
                        WHEN 'Open' THEN 1
                        WHEN 'Forthcoming' THEN 2
                        WHEN 'Closed' THEN 3
                        ELSE 4
                    END,
                    close_date ASC NULLS LAST
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

            return [self._row_to_grant(dict(row)) for row in results]

        except Exception as e:
            logger.error(f"Error listing grants: {e}")
            raise
        finally:
            self._release_connection(conn)

    def get_grants_by_ids(self, grant_ids: List[str]) -> List[Grant]:
        """
        Bulk fetch grants by their IDs.

        Useful for retrieving grants from search results.

        Args:
            grant_ids: List of grant identifiers

        Returns:
            List of Grant objects
        """
        if not grant_ids:
            return []

        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    grant_id, source, title, url, status,
                    open_date, close_date, programme, tags,
                    description_summary, budget_min, budget_max,
                    eligible_countries, duration, updated_at,
                    call_id, programme_area, action_type,
                    funding_rate_percent, organization_types,
                    consortium_required, min_partners
                FROM grants
                WHERE grant_id = ANY(%s)
                ORDER BY
                    CASE status
                        WHEN 'Open' THEN 1
                        WHEN 'Forthcoming' THEN 2
                        WHEN 'Closed' THEN 3
                        ELSE 4
                    END,
                    close_date ASC NULLS LAST
            """

            cursor.execute(query, (grant_ids,))
            results = cursor.fetchall()
            cursor.close()

            return [self._row_to_grant(dict(row)) for row in results]

        except Exception as e:
            logger.error(f"Error getting grants by IDs: {e}")
            raise
        finally:
            self._release_connection(conn)

    def count_grants(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """
        Count grants with optional filtering.

        Args:
            source: Filter by source
            status: Filter by status

        Returns:
            Total count of matching grants
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM grants WHERE 1=1"
            params = []

            if source:
                query += " AND source = %s"
                params.append(source)

            if status:
                query += " AND status = %s"
                params.append(status)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            cursor.close()

            return count

        except Exception as e:
            logger.error(f"Error counting grants: {e}")
            raise
        finally:
            self._release_connection(conn)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get grant statistics grouped by source and status.

        Returns:
            Dictionary with statistics:
            {
                "total": 4500,
                "by_source": {"horizon_europe": 2000, "nihr": 2500},
                "by_status": {"Open": 1500, "Closed": 2000, "Forthcoming": 1000}
            }
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) FROM grants")
            total = cursor.fetchone()[0]

            # By source
            cursor.execute("""
                SELECT source, COUNT(*)
                FROM grants
                GROUP BY source
                ORDER BY source
            """)
            by_source = {row[0]: row[1] for row in cursor.fetchall()}

            # By status
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM grants
                GROUP BY status
                ORDER BY status
            """)
            by_status = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.close()

            return {
                "total": total,
                "by_source": by_source,
                "by_status": by_status
            }

        except Exception as e:
            logger.error(f"Error getting grant stats: {e}")
            raise
        finally:
            self._release_connection(conn)

    def close(self):
        """Close all connections in the pool."""
        try:
            if hasattr(self, 'pool') and self.pool:
                self.pool.closeall()
                logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
