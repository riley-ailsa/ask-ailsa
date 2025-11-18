# INTELLIGENT LINK FOLLOWING: Claude Code Implementation Guide

## Quick Start: What You're Building

You're enhancing the NIHR grant scraper to capture 2.5-3.5x more content by:
1. **Fetching PDFs** from grant pages (application forms, specifications)
2. **Following relevant links** selectively (guidance pages, eligibility info)
3. **Detecting partnerships** and fetching partner requirements

Current state: 10K chars per grant → Target: 25-35K chars per grant

---

## PHASE 1: PDF FETCHING (Implement First)

### Step 1.1: Create PDF Parser Module

**File:** `src/ingest/pdf_parser.py`

```python
"""
PDF text extraction with multiple fallback methods.
Start with PyPDF2, fallback to pdfplumber if needed.
"""

from typing import Optional
import logging
from io import BytesIO
import PyPDF2
import pdfplumber

logger = logging.getLogger(__name__)


class PDFParser:
    """Extract text from PDF bytes with robust error handling."""
    
    def __init__(self, use_ocr: bool = False):
        self.use_ocr = use_ocr
    
    def extract_text(self, pdf_bytes: bytes) -> Optional[str]:
        """
        Extract text from PDF bytes using multiple methods.
        
        Returns None if extraction fails completely.
        """
        # Method 1: PyPDF2 (fastest, works for 90% of PDFs)
        text = self._extract_with_pypdf2(pdf_bytes)
        if text and len(text.strip()) > 100:
            return self._clean_text(text)
        
        # Method 2: pdfplumber (better for tables/complex layouts)
        text = self._extract_with_pdfplumber(pdf_bytes)
        if text and len(text.strip()) > 100:
            return self._clean_text(text)
        
        logger.warning("PDF extraction failed")
        return None
    
    def _extract_with_pypdf2(self, pdf_bytes: bytes) -> Optional[str]:
        try:
            pdf_file = BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.debug(f"PyPDF2 failed: {e}")
            return None
    
    def _extract_with_pdfplumber(self, pdf_bytes: bytes) -> Optional[str]:
        try:
            pdf_file = BytesIO(pdf_bytes)
            text_parts = []
            
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.debug(f"pdfplumber failed: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        return "\n".join(lines)
```

### Step 1.2: Create Resource Fetcher

**File:** `src/ingest/resource_fetcher.py`

```python
"""
Fetch resources (PDFs, webpages) with caching and rate limiting.
"""

import requests
import hashlib
import time
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ResourceFetcher:
    """Fetch external resources with caching and rate limiting."""
    
    def __init__(self, cache: Optional['FetchCache'] = None):
        self.cache = cache
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; GrantBot/1.0)'
        })
        self.last_request_time = {}  # Domain-based rate limiting
    
    def fetch_pdf(self, url: str) -> Optional[bytes]:
        """
        Fetch PDF from URL.
        
        Returns PDF bytes or None if fetch fails.
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(url)
            if cached and cached.get('content_type') == 'application/pdf':
                logger.debug(f"PDF cache hit: {url}")
                return cached['content']
        
        # Rate limit
        self._rate_limit(url)
        
        try:
            response = self.session.get(
                url,
                timeout=30,
                stream=True
            )
            response.raise_for_status()
            
            # Verify it's actually a PDF
            content_type = response.headers.get('content-type', '')
            if 'pdf' not in content_type.lower():
                logger.warning(f"Not a PDF: {url} ({content_type})")
                return None
            
            # Read content (max 50MB)
            max_size = 50 * 1024 * 1024
            content = b''
            for chunk in response.iter_content(chunk_size=1024*1024):
                content += chunk
                if len(content) > max_size:
                    logger.warning(f"PDF too large: {url}")
                    return None
            
            # Cache the result
            if self.cache:
                self.cache.set(url, content, 'application/pdf')
            
            logger.info(f"Fetched PDF: {url} ({len(content)} bytes)")
            return content
            
        except Exception as e:
            logger.error(f"Failed to fetch PDF {url}: {e}")
            return None
    
    def fetch_webpage(self, url: str) -> Optional[str]:
        """
        Fetch webpage HTML.
        
        Returns HTML string or None if fetch fails.
        """
        # Check cache
        if self.cache:
            cached = self.cache.get(url)
            if cached and cached.get('content_type') == 'text/html':
                logger.debug(f"Webpage cache hit: {url}")
                return cached['content'].decode('utf-8')
        
        # Rate limit
        self._rate_limit(url)
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            html = response.text
            
            # Cache the result
            if self.cache:
                self.cache.set(url, html.encode('utf-8'), 'text/html')
            
            logger.info(f"Fetched webpage: {url}")
            return html
            
        except Exception as e:
            logger.error(f"Failed to fetch webpage {url}: {e}")
            return None
    
    def _rate_limit(self, url: str):
        """Apply rate limiting per domain."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < 1.0:  # 1 second per domain
                time.sleep(1.0 - elapsed)
        
        self.last_request_time[domain] = time.time()
```

### Step 1.3: Create Fetch Cache

**File:** `src/storage/fetch_cache.py`

```python
"""
SQLite-based cache for fetched resources.
Prevents re-fetching PDFs and webpages.
"""

import sqlite3
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class FetchCache:
    """Cache for fetched resources with TTL support."""
    
    def __init__(self, db_path: str = "fetch_cache.db", ttl_days: int = 30):
        self.db_path = db_path
        self.ttl_days = ttl_days
        self._init_db()
    
    def _init_db(self):
        """Initialize cache database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fetch_cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                content BLOB,
                content_type TEXT,
                fetched_at TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fetched_at 
            ON fetch_cache(fetched_at)
        """)
        conn.commit()
        conn.close()
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached resource if not expired."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT content, content_type, fetched_at, metadata
            FROM fetch_cache
            WHERE url_hash = ?
        """, (url_hash,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        content, content_type, fetched_at, metadata = row
        
        # Check TTL
        fetched_dt = datetime.fromisoformat(fetched_at)
        if datetime.now() - fetched_dt > timedelta(days=self.ttl_days):
            logger.debug(f"Cache expired for {url}")
            return None
        
        return {
            'content': content,
            'content_type': content_type,
            'metadata': json.loads(metadata) if metadata else {}
        }
    
    def set(self, url: str, content: bytes, content_type: str, 
            metadata: Optional[Dict] = None):
        """Store resource in cache."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO fetch_cache
            (url_hash, url, content, content_type, fetched_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            url_hash,
            url,
            content,
            content_type,
            datetime.now().isoformat(),
            json.dumps(metadata) if metadata else None
        ))
        conn.commit()
        conn.close()
        
        logger.debug(f"Cached {content_type}: {url}")
    
    def cleanup_expired(self):
        """Remove expired entries."""
        cutoff = datetime.now() - timedelta(days=self.ttl_days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM fetch_cache
            WHERE fetched_at < ?
        """, (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired cache entries")
```

### Step 1.4: Create PDF Enhancement Orchestrator

**File:** `src/enhance/pdf_enhancer.py`

```python
"""
Orchestrate PDF fetching and parsing for grant enhancement.
"""

from typing import List, Dict, Any
from src.models import IndexableDocument
from src.ingest.resource_fetcher import ResourceFetcher
from src.ingest.pdf_parser import PDFParser
import logging
import hashlib

logger = logging.getLogger(__name__)


class PDFEnhancer:
    """Enhance grants by fetching and parsing linked PDFs."""
    
    def __init__(self, fetcher: ResourceFetcher):
        self.fetcher = fetcher
        self.parser = PDFParser(use_ocr=False)  # OCR too slow for bulk
    
    def enhance(self, grant_id: str, resources: List[Dict]) -> List[IndexableDocument]:
        """
        Fetch and parse all PDF resources for a grant.
        
        Args:
            grant_id: Grant identifier
            resources: List of resource dicts from scraper
            
        Returns:
            List of IndexableDocument objects from PDFs
        """
        documents = []
        pdf_resources = [r for r in resources if r.get('type') == 'pdf']
        
        logger.info(f"Processing {len(pdf_resources)} PDFs for grant {grant_id}")
        
        for resource in pdf_resources:
            url = resource.get('url')
            title = resource.get('title', 'PDF Document')
            
            if not url:
                continue
            
            # Fetch PDF
            pdf_bytes = self.fetcher.fetch_pdf(url)
            if not pdf_bytes:
                logger.warning(f"Failed to fetch PDF: {url}")
                continue
            
            # Parse PDF
            text = self.parser.extract_text(pdf_bytes)
            if not text:
                logger.warning(f"Failed to extract text from PDF: {url}")
                continue
            
            # Create document
            doc_id = hashlib.sha256(f"{grant_id}:{url}".encode()).hexdigest()[:16]
            
            doc = IndexableDocument(
                id=f"{grant_id}_pdf_{doc_id}",
                grant_id=grant_id,
                type="pdf",
                title=title,
                text=text,
                metadata={
                    'source_url': url,
                    'source_type': 'pdf',
                    'original_title': title,
                    'byte_size': len(pdf_bytes),
                    'char_count': len(text)
                }
            )
            
            documents.append(doc)
            logger.info(f"Extracted {len(text)} chars from PDF: {title}")
        
        return documents
```

---

## PHASE 2: SMART LINK FOLLOWING

### Step 2.1: Create Link Classifier

**File:** `src/enhance/link_classifier.py`

```python
"""
Classify links as relevant or irrelevant for following.
"""

import re
from urllib.parse import urlparse
from typing import Dict, List


class LinkClassifier:
    """Determine which links are worth following."""
    
    # High-value URL patterns (always follow)
    HIGH_VALUE_PATTERNS = [
        r'/guidance/',
        r'/eligibility',
        r'/how-to-apply',
        r'/application',
        r'/specification',
        r'/requirements',
        r'/faqs?',
        r'/resources',
        r'/documents',
        r'/forms?',
        r'/timeline',
        r'/key-dates'
    ]
    
    # Low-value URL patterns (never follow)
    LOW_VALUE_PATTERNS = [
        r'/news/',
        r'/events/',
        r'/contact',
        r'/about',
        r'/careers',
        r'/privacy',
        r'/terms',
        r'/cookie',
        r'/accessibility',
        r'/sitemap',
        r'\.pdf$',  # PDFs handled separately
        r'\.(jpg|jpeg|png|gif|svg)$',  # Images
        r'/login',
        r'/register',
        r'/search\?',
        r'#'  # Anchors
    ]
    
    # High-value link text patterns
    HIGH_VALUE_LINK_TEXT = [
        'guidance',
        'eligibility',
        'application',
        'specification',
        'requirements',
        'how to apply',
        'download',
        'form',
        'template',
        'criteria',
        'assessment',
        'evaluation'
    ]
    
    def classify(self, url: str, link_text: str = "", 
                 source_domain: str = "") -> Dict[str, Any]:
        """
        Classify a link's relevance for following.
        
        Returns dict with:
            - should_follow: bool
            - confidence: float (0-1)
            - reason: str
        """
        # Parse URL
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Check if same domain (prefer same-domain links)
        same_domain = source_domain and parsed.netloc == source_domain
        
        # Check high-value patterns
        for pattern in self.HIGH_VALUE_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return {
                    'should_follow': True,
                    'confidence': 0.9,
                    'reason': f'High-value URL pattern: {pattern}'
                }
        
        # Check low-value patterns
        for pattern in self.LOW_VALUE_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return {
                    'should_follow': False,
                    'confidence': 0.9,
                    'reason': f'Low-value URL pattern: {pattern}'
                }
        
        # Check link text
        link_text_lower = link_text.lower()
        for keyword in self.HIGH_VALUE_LINK_TEXT:
            if keyword in link_text_lower:
                return {
                    'should_follow': True,
                    'confidence': 0.7,
                    'reason': f'High-value link text: {keyword}'
                }
        
        # Default: follow if same domain, skip if external
        if same_domain:
            return {
                'should_follow': True,
                'confidence': 0.4,
                'reason': 'Same domain link'
            }
        else:
            return {
                'should_follow': False,
                'confidence': 0.6,
                'reason': 'External domain, no clear value indicators'
            }
```

### Step 2.2: Create Content Extractor

**File:** `src/enhance/content_extractor.py`

```python
"""
Extract main content from HTML pages, removing navigation/footer.
"""

from bs4 import BeautifulSoup
import re
from typing import Optional


class ContentExtractor:
    """Extract main content from webpages."""
    
    # Elements that typically contain main content
    CONTENT_SELECTORS = [
        'main',
        'article',
        '[role="main"]',
        '#main-content',
        '#content',
        '.main-content',
        '.content',
        '.article-content',
        '.page-content'
    ]
    
    # Elements to remove (navigation, ads, etc.)
    REMOVE_SELECTORS = [
        'nav',
        'header',
        'footer',
        'aside',
        '.sidebar',
        '.navigation',
        '.menu',
        '.breadcrumb',
        '.social-share',
        '.related-links',
        '.advertisement',
        '#cookie-banner',
        '.newsletter-signup',
        'script',
        'style',
        'noscript'
    ]
    
    def extract(self, html: str, url: str = "") -> Optional[str]:
        """
        Extract main content from HTML.
        
        Returns extracted text or None if extraction fails.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()
        
        # Try to find main content container
        main_content = None
        for selector in self.CONTENT_SELECTORS:
            elements = soup.select(selector)
            if elements:
                main_content = elements[0]
                break
        
        # Fallback: use body
        if not main_content:
            main_content = soup.body or soup
        
        # Extract text
        text = self._extract_text_with_structure(main_content)
        
        # Clean up
        text = self._clean_text(text)
        
        # Validate minimum content
        if len(text) < 200:  # Too short to be useful
            return None
        
        return text
    
    def _extract_text_with_structure(self, element) -> str:
        """Extract text preserving some structure."""
        lines = []
        
        for elem in element.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'td']):
            text = elem.get_text(strip=True)
            if text:
                # Add appropriate spacing for headers
                if elem.name.startswith('h'):
                    lines.append(f"\n{text}\n")
                else:
                    lines.append(text)
        
        return "\n".join(lines)
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Remove common boilerplate
        boilerplate = [
            r'Cookie settings',
            r'Accept cookies',
            r'Skip to main content',
            r'JavaScript is disabled',
            r'Back to top'
        ]
        
        for pattern in boilerplate:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
```

### Step 2.3: Create Relevance Scorer

**File:** `src/enhance/relevance_scorer.py`

```python
"""
Score content relevance to determine if it should be indexed.
"""

import re
from typing import Dict, List


class RelevanceScorer:
    """Score webpage content relevance for grant context."""
    
    # Keywords that indicate grant-relevant content
    GRANT_KEYWORDS = [
        # Funding terms
        'funding', 'grant', 'award', 'budget', 'finance', 'cost',
        'million', 'pounds', '£', 'GBP',
        
        # Application terms
        'application', 'apply', 'submit', 'deadline', 'closing date',
        'eligibility', 'eligible', 'criteria', 'requirement',
        
        # Process terms
        'assessment', 'evaluation', 'review', 'selection', 'decision',
        'interview', 'panel', 'committee',
        
        # Document terms
        'form', 'template', 'guidance', 'specification', 'proposal',
        
        # Research terms
        'research', 'study', 'project', 'programme', 'collaboration',
        'partnership', 'consortium', 'institution',
        
        # NIHR/IUK specific
        'NIHR', 'Innovate UK', 'NHS', 'health', 'clinical', 'innovation'
    ]
    
    # Negative indicators (content probably not relevant)
    NEGATIVE_KEYWORDS = [
        'news', 'blog', 'press release', 'annual report',
        'vacancy', 'job', 'career', 'recruitment',
        'event', 'conference', 'workshop', 'webinar',
        'twitter', 'facebook', 'linkedin', 'social media'
    ]
    
    def score(self, text: str, source_url: str = "") -> Dict[str, Any]:
        """
        Score content relevance (0-1).
        
        Returns dict with:
            - score: float (0-1)
            - is_relevant: bool (score > threshold)
            - keyword_matches: List of matched keywords
            - reason: str
        """
        text_lower = text.lower()
        
        # Count keyword matches
        positive_matches = []
        for keyword in self.GRANT_KEYWORDS:
            if keyword in text_lower:
                positive_matches.append(keyword)
        
        negative_matches = []
        for keyword in self.NEGATIVE_KEYWORDS:
            if keyword in text_lower:
                negative_matches.append(keyword)
        
        # Calculate base score
        positive_score = len(positive_matches) / len(self.GRANT_KEYWORDS)
        negative_score = len(negative_matches) / len(self.NEGATIVE_KEYWORDS)
        
        # Weighted score
        score = (positive_score * 2) - negative_score
        score = max(0, min(1, score))  # Clamp to 0-1
        
        # Boost score for high keyword density
        if len(positive_matches) > 10:
            score = min(1, score * 1.5)
        
        # Determine relevance
        is_relevant = score > 0.3  # Threshold
        
        # Generate reason
        if is_relevant:
            reason = f"Relevant: {len(positive_matches)} grant keywords found"
        else:
            if negative_matches:
                reason = f"Not relevant: appears to be {negative_matches[0]} content"
            else:
                reason = "Not relevant: insufficient grant-related content"
        
        return {
            'score': round(score, 2),
            'is_relevant': is_relevant,
            'keyword_matches': positive_matches[:10],  # Top 10
            'reason': reason
        }
```

### Step 2.4: Create Link Follower Orchestrator

**File:** `src/enhance/link_follower.py`

```python
"""
Orchestrate intelligent link following with depth control.
"""

from typing import List, Dict, Any
from urllib.parse import urlparse, urljoin
from src.models import IndexableDocument
from src.ingest.resource_fetcher import ResourceFetcher
from src.enhance.link_classifier import LinkClassifier
from src.enhance.content_extractor import ContentExtractor
from src.enhance.relevance_scorer import RelevanceScorer
import hashlib
import logging

logger = logging.getLogger(__name__)


class LinkFollower:
    """Follow relevant links from grant pages."""
    
    def __init__(self, fetcher: ResourceFetcher, max_links: int = 10):
        self.fetcher = fetcher
        self.classifier = LinkClassifier()
        self.extractor = ContentExtractor()
        self.scorer = RelevanceScorer()
        self.max_links = max_links
    
    def follow_links(self, grant_id: str, resources: List[Dict], 
                    source_url: str) -> List[IndexableDocument]:
        """
        Follow relevant webpage links from resources.
        
        Args:
            grant_id: Grant identifier
            resources: List of resource dicts from scraper
            source_url: Original grant page URL
            
        Returns:
            List of IndexableDocument objects from followed links
        """
        documents = []
        source_domain = urlparse(source_url).netloc
        
        # Get webpage resources
        webpage_resources = [
            r for r in resources 
            if r.get('type') == 'webpage'
        ]
        
        # Classify and sort by relevance
        classified = []
        for resource in webpage_resources:
            url = resource.get('url')
            title = resource.get('title', '')
            
            if not url:
                continue
            
            # Make URL absolute
            url = urljoin(source_url, url)
            
            # Classify
            classification = self.classifier.classify(
                url, title, source_domain
            )
            
            if classification['should_follow']:
                classified.append({
                    'resource': resource,
                    'url': url,
                    'confidence': classification['confidence'],
                    'reason': classification['reason']
                })
        
        # Sort by confidence and take top N
        classified.sort(key=lambda x: x['confidence'], reverse=True)
        to_follow = classified[:self.max_links]
        
        logger.info(f"Following {len(to_follow)} links for grant {grant_id}")
        
        # Follow each link
        for item in to_follow:
            doc = self._follow_single_link(
                grant_id,
                item['url'],
                item['resource'].get('title', 'Linked Page')
            )
            
            if doc:
                documents.append(doc)
                logger.info(f"Added {len(doc.text)} chars from: {item['url']}")
        
        return documents
    
    def _follow_single_link(self, grant_id: str, url: str, 
                           title: str) -> Optional[IndexableDocument]:
        """Follow a single link and create document if relevant."""
        
        # Fetch webpage
        html = self.fetcher.fetch_webpage(url)
        if not html:
            logger.warning(f"Failed to fetch webpage: {url}")
            return None
        
        # Extract content
        text = self.extractor.extract(html, url)
        if not text:
            logger.warning(f"Failed to extract content from: {url}")
            return None
        
        # Score relevance
        relevance = self.scorer.score(text, url)
        if not relevance['is_relevant']:
            logger.info(f"Content not relevant: {url} ({relevance['reason']})")
            return None
        
        # Create document
        doc_id = hashlib.sha256(f"{grant_id}:{url}".encode()).hexdigest()[:16]
        
        doc = IndexableDocument(
            id=f"{grant_id}_link_{doc_id}",
            grant_id=grant_id,
            type="linked_page",
            title=title,
            text=text,
            metadata={
                'source_url': url,
                'source_type': 'webpage',
                'relevance_score': relevance['score'],
                'keyword_matches': relevance['keyword_matches'],
                'char_count': len(text)
            }
        )
        
        return doc
```

---

## PHASE 3: PARTNERSHIP DETECTION

### Step 3.1: Create Partnership Detector

**File:** `src/enhance/partnership_detector.py`

```python
"""
Detect partnership grants and extract partner information.
"""

import re
from typing import Optional, Dict, List
from bs4 import BeautifulSoup


class PartnershipDetector:
    """Detect and extract partnership information from grants."""
    
    # Patterns that indicate a partnership
    PARTNERSHIP_INDICATORS = [
        r'partnership',
        r'collaboration',
        r'joint',
        r'consortium',
        r'co-fund',
        r'match fund',
        r'partner organisation',
        r'lead organisation'
    ]
    
    # Known partner organizations
    KNOWN_PARTNERS = {
        'mrc': {
            'name': 'Medical Research Council',
            'domain': 'mrc.ukri.org',
            'url_pattern': r'mrc\.ukri\.org'
        },
        'wellcome': {
            'name': 'Wellcome Trust',
            'domain': 'wellcome.org',
            'url_pattern': r'wellcome\.org'
        },
        'cruk': {
            'name': 'Cancer Research UK',
            'domain': 'cancerresearchuk.org',
            'url_pattern': r'cancerresearchuk\.org'
        },
        'bhf': {
            'name': 'British Heart Foundation',
            'domain': 'bhf.org.uk',
            'url_pattern': r'bhf\.org\.uk'
        },
        'epsrc': {
            'name': 'EPSRC',
            'domain': 'epsrc.ukri.org',
            'url_pattern': r'epsrc\.ukri\.org'
        }
    }
    
    def detect(self, title: str, html: str, resources: List[Dict]) -> Optional[Dict]:
        """
        Detect if grant is a partnership and extract partner info.
        
        Returns dict with:
            - is_partnership: bool
            - confidence: float
            - partner_name: str
            - partner_url: str (if found)
            - indicators: List of matched patterns
        """
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text().lower()
        title_lower = title.lower()
        
        # Check for partnership indicators
        indicators = []
        for pattern in self.PARTNERSHIP_INDICATORS:
            if re.search(pattern, title_lower) or re.search(pattern, text[:2000]):
                indicators.append(pattern)
        
        if not indicators:
            return None
        
        # Look for partner organization
        partner_info = self._find_partner_org(soup, resources)
        
        if partner_info:
            return {
                'is_partnership': True,
                'confidence': 0.9,
                'partner_name': partner_info['name'],
                'partner_url': partner_info.get('url'),
                'indicators': indicators
            }
        
        # Partnership likely but partner not identified
        return {
            'is_partnership': True,
            'confidence': 0.6,
            'partner_name': None,
            'partner_url': None,
            'indicators': indicators
        }
    
    def _find_partner_org(self, soup: BeautifulSoup, 
                         resources: List[Dict]) -> Optional[Dict]:
        """Find partner organization from links and text."""
        
        # Check resources for partner links
        for resource in resources:
            url = resource.get('url', '')
            for partner_key, partner_info in self.KNOWN_PARTNERS.items():
                if re.search(partner_info['url_pattern'], url):
                    return {
                        'name': partner_info['name'],
                        'url': url
                    }
        
        # Check all links in HTML
        for link in soup.find_all('a', href=True):
            href = link['href']
            for partner_key, partner_info in self.KNOWN_PARTNERS.items():
                if re.search(partner_info['url_pattern'], href):
                    return {
                        'name': partner_info['name'],
                        'url': href
                    }
        
        return None
```

### Step 3.2: Create Partnership Handler

**File:** `src/enhance/partnership_handler.py`

```python
"""
Handle partnership grants by fetching partner requirements.
"""

from typing import List, Optional
from src.models import IndexableDocument
from src.ingest.resource_fetcher import ResourceFetcher
from src.enhance.partnership_detector import PartnershipDetector
from src.enhance.content_extractor import ContentExtractor
import hashlib
import logging

logger = logging.getLogger(__name__)


class PartnershipHandler:
    """Handle partnership grants by fetching partner pages."""
    
    def __init__(self, fetcher: ResourceFetcher):
        self.fetcher = fetcher
        self.detector = PartnershipDetector()
        self.extractor = ContentExtractor()
    
    def enhance_partnership_grant(
        self, 
        grant_id: str,
        title: str,
        html: str,
        resources: List[Dict]
    ) -> List[IndexableDocument]:
        """
        Enhance partnership grants with partner information.
        
        Returns list of documents from partner pages.
        """
        # Detect partnership
        partnership = self.detector.detect(title, html, resources)
        
        if not partnership or not partnership['is_partnership']:
            return []
        
        logger.info(f"Partnership detected for grant {grant_id}: {partnership}")
        
        documents = []
        
        # If partner URL found, fetch it
        if partnership.get('partner_url'):
            doc = self._fetch_partner_page(
                grant_id,
                partnership['partner_url'],
                partnership.get('partner_name', 'Partner Organization')
            )
            if doc:
                documents.append(doc)
        
        # Create a summary document about the partnership
        if partnership.get('partner_name'):
            summary_doc = self._create_partnership_summary(
                grant_id,
                partnership
            )
            documents.append(summary_doc)
        
        return documents
    
    def _fetch_partner_page(self, grant_id: str, url: str, 
                           partner_name: str) -> Optional[IndexableDocument]:
        """Fetch and process partner organization page."""
        
        html = self.fetcher.fetch_webpage(url)
        if not html:
            logger.warning(f"Failed to fetch partner page: {url}")
            return None
        
        text = self.extractor.extract(html, url)
        if not text:
            logger.warning(f"Failed to extract partner content: {url}")
            return None
        
        # Create document
        doc_id = hashlib.sha256(f"{grant_id}:partner:{url}".encode()).hexdigest()[:16]
        
        doc = IndexableDocument(
            id=f"{grant_id}_partner_{doc_id}",
            grant_id=grant_id,
            type="partner_page",
            title=f"{partner_name} Requirements",
            text=text,
            metadata={
                'source_url': url,
                'partner_name': partner_name,
                'source_type': 'partner_webpage',
                'char_count': len(text)
            }
        )
        
        logger.info(f"Fetched partner page: {partner_name} ({len(text)} chars)")
        return doc
    
    def _create_partnership_summary(self, grant_id: str, 
                                   partnership: Dict) -> IndexableDocument:
        """Create a summary document about the partnership."""
        
        summary_text = f"""
Partnership Grant Information

This is a partnership grant with {partnership['partner_name']}.

Key Information:
- Partner Organization: {partnership['partner_name']}
- Partnership Type: Collaborative funding opportunity
- Confidence: {partnership['confidence']}

Important Note:
This grant involves collaboration between NIHR and {partnership['partner_name']}.
Applicants should review requirements from both organizations.
There may be additional eligibility criteria or application processes
specific to the partner organization.

Partnership Indicators Found:
{', '.join(partnership['indicators'])}
"""
        
        doc_id = hashlib.sha256(f"{grant_id}:partnership:summary".encode()).hexdigest()[:16]
        
        return IndexableDocument(
            id=f"{grant_id}_partnership_{doc_id}",
            grant_id=grant_id,
            type="partnership_summary",
            title="Partnership Information",
            text=summary_text.strip(),
            metadata={
                'partner_name': partnership['partner_name'],
                'partnership_confidence': partnership['confidence'],
                'indicators': partnership['indicators']
            }
        )
```

---

## INTEGRATION: Backfill Script

### Complete Enhancement Script

**File:** `scripts/enhance_nihr_grants.py`

```python
#!/usr/bin/env python3
"""
Enhance existing NIHR grants with PDFs, links, and partnerships.

Usage:
    python scripts/enhance_nihr_grants.py --test 5  # Test on 5 grants
    python scripts/enhance_nihr_grants.py --all     # Enhance all grants
"""

import argparse
import logging
import time
from typing import List, Tuple
from datetime import datetime

from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore
from src.storage.fetch_cache import FetchCache
from src.ingest.resource_fetcher import ResourceFetcher
from src.enhance.pdf_enhancer import PDFEnhancer
from src.enhance.link_follower import LinkFollower
from src.enhance.partnership_handler import PartnershipHandler
from src.api.embeddings import create_embeddings_batch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def enhance_single_grant(grant_id: str, 
                        grant_store: GrantStore,
                        doc_store: DocumentStore,
                        enhancers: dict) -> dict:
    """
    Enhance a single grant with all three phases.
    
    Returns dict with enhancement statistics.
    """
    start_time = time.time()
    
    # Get grant and existing documents
    grant = grant_store.get_grant(grant_id)
    if not grant:
        logger.error(f"Grant not found: {grant_id}")
        return {'error': 'Grant not found'}
    
    existing_docs = doc_store.get_documents_for_grant(grant_id)
    base_char_count = sum(len(doc.text) for doc in existing_docs)
    
    logger.info(f"Enhancing grant: {grant.title}")
    logger.info(f"  Existing: {len(existing_docs)} docs, {base_char_count:,} chars")
    
    # Get resources from grant metadata
    resources = grant.metadata.get('resources', [])
    source_url = grant.metadata.get('source_url', '')
    raw_html = grant.metadata.get('raw_html', '')  # If stored
    
    new_documents = []
    
    # Phase 1: PDF Enhancement
    try:
        pdf_docs = enhancers['pdf'].enhance(grant_id, resources)
        new_documents.extend(pdf_docs)
        logger.info(f"  PDFs: Added {len(pdf_docs)} documents")
    except Exception as e:
        logger.error(f"  PDF enhancement failed: {e}")
    
    # Phase 2: Link Following
    try:
        link_docs = enhancers['link'].follow_links(
            grant_id, resources, source_url
        )
        new_documents.extend(link_docs)
        logger.info(f"  Links: Added {len(link_docs)} documents")
    except Exception as e:
        logger.error(f"  Link following failed: {e}")
    
    # Phase 3: Partnership Detection
    try:
        if raw_html:
            partner_docs = enhancers['partnership'].enhance_partnership_grant(
                grant_id, grant.title, raw_html, resources
            )
            new_documents.extend(partner_docs)
            logger.info(f"  Partnerships: Added {len(partner_docs)} documents")
    except Exception as e:
        logger.error(f"  Partnership detection failed: {e}")
    
    # Store new documents
    for doc in new_documents:
        doc_store.add_document(doc)
    
    # Create embeddings for new documents
    if new_documents:
        logger.info(f"  Creating embeddings for {len(new_documents)} new documents")
        embeddings = create_embeddings_batch(
            [doc.text for doc in new_documents]
        )
        
        for doc, embedding in zip(new_documents, embeddings):
            doc_store.add_embedding(doc.id, embedding)
    
    # Calculate statistics
    new_char_count = sum(len(doc.text) for doc in new_documents)
    total_char_count = base_char_count + new_char_count
    improvement = (total_char_count / base_char_count - 1) if base_char_count > 0 else 0
    
    elapsed_time = time.time() - start_time
    
    stats = {
        'grant_id': grant_id,
        'title': grant.title[:50],
        'base_docs': len(existing_docs),
        'new_docs': len(new_documents),
        'base_chars': base_char_count,
        'new_chars': new_char_count,
        'total_chars': total_char_count,
        'improvement': improvement,
        'pdf_docs': len([d for d in new_documents if d.type == 'pdf']),
        'link_docs': len([d for d in new_documents if d.type == 'linked_page']),
        'partner_docs': len([d for d in new_documents if 'partner' in d.type]),
        'elapsed_seconds': elapsed_time
    }
    
    logger.info(f"  COMPLETE: {improvement:.1%} improvement in {elapsed_time:.1f}s")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Enhance NIHR grants')
    parser.add_argument('--test', type=int, help='Test on N grants')
    parser.add_argument('--all', action='store_true', help='Enhance all grants')
    parser.add_argument('--grant-id', help='Enhance specific grant')
    args = parser.parse_args()
    
    # Initialize storage
    grant_store = GrantStore()
    doc_store = DocumentStore()
    cache = FetchCache()
    
    # Initialize enhancers
    fetcher = ResourceFetcher(cache)
    enhancers = {
        'pdf': PDFEnhancer(fetcher),
        'link': LinkFollower(fetcher, max_links=10),
        'partnership': PartnershipHandler(fetcher)
    }
    
    # Get grants to enhance
    if args.grant_id:
        grant_ids = [args.grant_id]
    elif args.test:
        all_grants = grant_store.list_grants(source='nihr')
        grant_ids = [g['id'] for g in all_grants[:args.test]]
    elif args.all:
        all_grants = grant_store.list_grants(source='nihr')
        grant_ids = [g['id'] for g in all_grants]
    else:
        parser.error("Specify --test N, --all, or --grant-id")
    
    logger.info(f"Enhancing {len(grant_ids)} grants")
    
    # Process grants
    all_stats = []
    for i, grant_id in enumerate(grant_ids, 1):
        logger.info(f"\n[{i}/{len(grant_ids)}] Processing {grant_id}")
        
        stats = enhance_single_grant(
            grant_id,
            grant_store,
            doc_store,
            enhancers
        )
        
        all_stats.append(stats)
        
        # Rate limit
        if i < len(grant_ids):
            time.sleep(0.5)
    
    # Summary statistics
    successful = [s for s in all_stats if 'error' not in s]
    
    if successful:
        avg_improvement = sum(s['improvement'] for s in successful) / len(successful)
        total_new_docs = sum(s['new_docs'] for s in successful)
        total_new_chars = sum(s['new_chars'] for s in successful)
        avg_time = sum(s['elapsed_seconds'] for s in successful) / len(successful)
        
        print(f"\n{'='*60}")
        print("ENHANCEMENT COMPLETE")
        print(f"{'='*60}")
        print(f"Grants enhanced: {len(successful)}/{len(grant_ids)}")
        print(f"Average improvement: {avg_improvement:.1%}")
        print(f"Total new documents: {total_new_docs:,}")
        print(f"Total new characters: {total_new_chars:,}")
        print(f"Average time per grant: {avg_time:.1f}s")
        print(f"PDF documents: {sum(s['pdf_docs'] for s in successful)}")
        print(f"Link documents: {sum(s['link_docs'] for s in successful)}")
        print(f"Partner documents: {sum(s['partner_docs'] for s in successful)}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
```

---

## TESTING GUIDE

### Test Individual Components

```python
# test_components.py
"""Test individual enhancement components."""

def test_pdf_parser():
    """Test PDF text extraction."""
    from src.ingest.pdf_parser import PDFParser
    
    parser = PDFParser()
    
    # Test with a sample PDF
    with open('test_data/sample.pdf', 'rb') as f:
        pdf_bytes = f.read()
    
    text = parser.extract_text(pdf_bytes)
    print(f"Extracted {len(text)} characters")
    print(f"First 500 chars: {text[:500]}")


def test_link_classifier():
    """Test link classification."""
    from src.enhance.link_classifier import LinkClassifier
    
    classifier = LinkClassifier()
    
    test_urls = [
        ('https://nihr.ac.uk/guidance/how-to-apply', 'How to Apply'),
        ('https://nihr.ac.uk/news/latest', 'Latest News'),
        ('https://nihr.ac.uk/documents/form.pdf', 'Application Form'),
        ('https://example.com/privacy', 'Privacy Policy')
    ]
    
    for url, text in test_urls:
        result = classifier.classify(url, text, 'nihr.ac.uk')
        print(f"{url}: {result['should_follow']} ({result['reason']})")


def test_relevance_scorer():
    """Test content relevance scoring."""
    from src.enhance.relevance_scorer import RelevanceScorer
    
    scorer = RelevanceScorer()
    
    grant_text = """
    This funding opportunity provides £2 million for innovative research.
    Applications must be submitted by the deadline of March 31st.
    Eligibility criteria include UK-based institutions.
    """
    
    news_text = """
    Join us for our annual conference next month.
    Follow us on Twitter for the latest updates.
    Check out our blog for researcher stories.
    """
    
    grant_score = scorer.score(grant_text)
    news_score = scorer.score(news_text)
    
    print(f"Grant text: {grant_score}")
    print(f"News text: {news_score}")


if __name__ == "__main__":
    print("Testing PDF Parser...")
    test_pdf_parser()
    
    print("\nTesting Link Classifier...")
    test_link_classifier()
    
    print("\nTesting Relevance Scorer...")
    test_relevance_scorer()
```

---

## DEPLOYMENT CHECKLIST

### Pre-deployment
- [ ] Install dependencies: `pip install PyPDF2 pdfplumber`
- [ ] Create fetch cache database
- [ ] Test on 5 sample grants
- [ ] Verify embeddings are created
- [ ] Check error handling

### Deployment Steps
1. Deploy code to production
2. Run on 10 test grants: `python scripts/enhance_nihr_grants.py --test 10`
3. Review enhancement statistics
4. If successful, run full backfill: `python scripts/enhance_nihr_grants.py --all`
5. Monitor progress and errors

### Post-deployment
- [ ] Verify 2.5-3.5x content increase
- [ ] Check embedding creation
- [ ] Test search quality improvement
- [ ] Monitor cache size
- [ ] Set up monitoring alerts

---

## KEY IMPLEMENTATION NOTES FOR CLAUDE CODE

1. **Start with Phase 1 (PDFs)** - This is the highest value and simplest to implement
2. **Use the fetch cache** - Critical for not re-downloading content
3. **Rate limiting is essential** - 1 second per domain minimum
4. **Test with real NIHR grants** - The specification is based on actual NIHR grant structure
5. **Store raw HTML** in grant metadata if not already - Needed for partnership detection
6. **Handle errors gracefully** - Don't let one failed PDF stop the entire process
7. **Log everything** - You need visibility into what's being enhanced
8. **Create embeddings in batches** - More efficient than one at a time

## Expected Results

After implementation, you should see:
- NIHR grants growing from ~10K to 25-35K characters
- 3-7 additional documents per grant
- PDF documents adding application forms and specifications
- Relevant guidance pages being captured
- Partnership grants having partner requirements

The system is designed to be selective - it's better to miss some content than to add irrelevant noise that degrades search quality.
