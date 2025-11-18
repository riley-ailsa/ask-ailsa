# QUICK START: Intelligent Link Following for Claude Code

## PROJECT CONTEXT
Enhancing NIHR grant scraper to capture 2.5-3.5x more content by fetching PDFs and following relevant links.

## YOUR IMPLEMENTATION ORDER

### 🎯 PHASE 1: PDF FETCHING (Do This First!)
**Why**: Biggest impact, simplest implementation  
**Time**: 2-3 hours  
**Impact**: 10K → 20K chars per grant

#### Task 1.1: Install Dependencies
```bash
pip install PyPDF2==3.0.1 pdfplumber==0.10.3
```

#### Task 1.2: Create These Files

##### File 1: `src/storage/fetch_cache.py`
Create SQLite cache to prevent re-downloading:
- Store fetched PDFs/webpages with TTL
- Key methods: `get(url)`, `set(url, content, type)`
- Use SHA256 hash of URL as key

##### File 2: `src/ingest/pdf_parser.py`
Extract text from PDFs:
- Try PyPDF2 first (fast)
- Fallback to pdfplumber if needed
- Return None if extraction fails
- Clean text (remove excess whitespace)

##### File 3: `src/ingest/resource_fetcher.py`
Fetch resources with caching:
- `fetch_pdf(url)` - returns bytes or None
- `fetch_webpage(url)` - returns HTML string or None
- Rate limit: 1 second per domain
- Max PDF size: 50MB
- Use fetch_cache to avoid re-downloading

##### File 4: `src/enhance/pdf_enhancer.py`
Orchestrate PDF enhancement:
```python
def enhance(grant_id: str, resources: List[Dict]) -> List[IndexableDocument]:
    # 1. Filter resources where type='pdf'
    # 2. For each PDF:
    #    - Fetch using ResourceFetcher
    #    - Parse using PDFParser
    #    - Create IndexableDocument
    # 3. Return list of documents
```

#### Task 1.3: Test Script
```python
# test_pdf_enhancement.py
from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore
from src.storage.fetch_cache import FetchCache
from src.ingest.resource_fetcher import ResourceFetcher
from src.enhance.pdf_enhancer import PDFEnhancer

# Get a test NIHR grant
grant_store = GrantStore()
grants = grant_store.list_grants(source='nihr', limit=1)
test_grant = grants[0]

# Enhance with PDFs
cache = FetchCache()
fetcher = ResourceFetcher(cache)
enhancer = PDFEnhancer(fetcher)

# Get resources from grant metadata
resources = test_grant.metadata.get('resources', [])
pdf_docs = enhancer.enhance(test_grant.id, resources)

print(f"Added {len(pdf_docs)} PDFs")
for doc in pdf_docs:
    print(f"  - {doc.title}: {len(doc.text)} chars")
```

#### Task 1.4: Integration Script
```python
# scripts/enhance_pdfs.py
"""
Enhance NIHR grants with PDFs.

Usage:
    python scripts/enhance_pdfs.py --test 5
    python scripts/enhance_pdfs.py --all
"""
# [Use the full script from implementation guide]
```

---

### ⚡ QUICK WIN: Stop Here and Test!
After Phase 1, you should have:
- ✅ PDFs being fetched and cached
- ✅ Text extracted successfully  
- ✅ 2x content increase (10K → 20K chars)
- ✅ New documents stored with embeddings

**Test with 5 grants before proceeding to Phase 2**

---

### 🔗 PHASE 2: SMART LINK FOLLOWING (After Phase 1 Works)
**Time**: 3-4 hours  
**Impact**: Additional 5-10K chars per grant

#### Task 2.1: Create Link Intelligence

##### File 5: `src/enhance/link_classifier.py`
Classify which links to follow:
```python
HIGH_VALUE_PATTERNS = ['/guidance/', '/eligibility', '/how-to-apply']
LOW_VALUE_PATTERNS = ['/news/', '/events/', '/privacy']

def classify(url, link_text, source_domain):
    # Return: {should_follow: bool, confidence: float, reason: str}
```

##### File 6: `src/enhance/content_extractor.py`
Extract main content from HTML:
- Remove nav, footer, sidebar
- Find main content area
- Clean text
- Return None if < 200 chars

##### File 7: `src/enhance/relevance_scorer.py`
Score if content is grant-relevant:
```python
GRANT_KEYWORDS = ['funding', 'grant', 'application', 'deadline', 'eligibility']
def score(text):
    # Return: {score: 0-1, is_relevant: bool, reason: str}
```

##### File 8: `src/enhance/link_follower.py`
Orchestrate link following:
- Max 10 links per grant
- Only depth 1 (don't follow links from followed pages)
- Only follow if relevance > 0.3

---

### 🤝 PHASE 3: PARTNERSHIP DETECTION (Optional)
**Time**: 2 hours  
**Impact**: Specialized for partnership grants

Only implement if Phases 1-2 are working well.

---

## CRITICAL IMPLEMENTATION RULES

### 1. Resource Extraction Structure
NIHR scraper already extracts resources like this:
```python
resources = [
    {
        'type': 'pdf',  # or 'webpage'
        'title': 'Application Form',
        'url': 'https://...',
        'description': '...'
    }
]
```
These are stored in `grant.metadata['resources']`

### 2. Database Integration
```python
# Your new documents must follow this structure:
from src.models import IndexableDocument

doc = IndexableDocument(
    id=f"{grant_id}_pdf_{hash[:16]}",  # Unique ID
    grant_id=grant_id,                  # Link to grant
    type="pdf",                         # or "linked_page"
    title=title,
    text=extracted_text,
    metadata={
        'source_url': url,
        'char_count': len(text)
    }
)

# Store and create embeddings
doc_store.add_document(doc)
embedding = create_embedding(doc.text)
doc_store.add_embedding(doc.id, embedding)
```

### 3. Error Handling Pattern
```python
try:
    result = fetch_or_parse_something()
except Exception as e:
    logger.error(f"Failed: {e}")
    continue  # Don't stop entire process
```

### 4. Rate Limiting Is Critical
```python
def _rate_limit(self, url):
    domain = urlparse(url).netloc
    if domain in self.last_request_time:
        elapsed = time.time() - self.last_request_time[domain]
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
    self.last_request_time[domain] = time.time()
```

---

## TESTING CHECKLIST

### After Phase 1 (PDFs):
```bash
python scripts/enhance_pdfs.py --test 5
```

Expected output:
```
Grant 1: Added 3 PDFs, 8,234 chars → 18,456 chars (124% increase)
Grant 2: Added 2 PDFs, 9,123 chars → 21,234 chars (133% increase)
...
Average improvement: 128%
```

### Debugging Commands:
```python
# Check if resources are extracted
grant = grant_store.get_grant(grant_id)
print(grant.metadata.get('resources'))

# Check cache
cache = FetchCache()
cached = cache.get('https://some-pdf-url.pdf')
print(f"Cached: {cached is not None}")

# Check PDF extraction
with open('test.pdf', 'rb') as f:
    parser = PDFParser()
    text = parser.extract_text(f.read())
    print(f"Extracted: {len(text)} chars")
```

---

## COMMON ISSUES & FIXES

### Issue: "No resources found"
**Fix**: Check grant.metadata['resources'] exists and has entries

### Issue: "PDF extraction returns None"
**Fix**: Try with pdfplumber, check PDF isn't corrupted, check size

### Issue: "Rate limit errors"
**Fix**: Ensure 1 second delay per domain, check fetcher._rate_limit()

### Issue: "Embeddings not created"
**Fix**: Ensure you call create_embeddings_batch() after storing documents

---

## SUCCESS METRICS

You know it's working when:
1. **Phase 1**: Each grant has 2-4 PDF documents added
2. **Content increase**: 10K → 20K+ characters per grant
3. **Cache working**: Second run is much faster
4. **No errors**: Clean logs, all grants processed
5. **Search improvement**: "application form" queries return PDF content

---

## FINAL DEPLOYMENT

Once tested on 5-10 grants:
```bash
# Full backfill (will take ~6 hours for 450 grants)
python scripts/enhance_nihr_grants.py --all

# Monitor progress
tail -f enhancement.log
```

---

## FILES YOU'LL CREATE

Phase 1 (Required):
1. `src/storage/fetch_cache.py` - Caching layer
2. `src/ingest/pdf_parser.py` - PDF text extraction  
3. `src/ingest/resource_fetcher.py` - HTTP fetching with cache
4. `src/enhance/pdf_enhancer.py` - PDF orchestration
5. `scripts/enhance_pdfs.py` - Backfill script

Phase 2 (After Phase 1 works):
6. `src/enhance/link_classifier.py` - Link relevance
7. `src/enhance/content_extractor.py` - HTML content extraction
8. `src/enhance/relevance_scorer.py` - Content scoring
9. `src/enhance/link_follower.py` - Link orchestration

Phase 3 (Optional):
10. `src/enhance/partnership_detector.py` - Detect partnerships
11. `src/enhance/partnership_handler.py` - Handle partnerships

---

Start with Phase 1, test thoroughly, then proceed. The PDF fetching alone will double your content and that's the biggest win!
