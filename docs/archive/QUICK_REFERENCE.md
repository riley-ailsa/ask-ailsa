# Quick Reference: Tab-Aware NIHR Scraping

## The Problem (One Line)
NIHR scraper only gets first tab → missing 80% of content → 50x fewer embeddings than IUK

## The Solution (One Line)
Detect tabs and extract each tab panel explicitly (like IUK's nav-based approach)

---

## Files You Need

1. **nihr_tab_aware_parsing.py** - Complete implementation with detailed comments
2. **test_tab_parsing.py** - Test script to verify tabs are detected
3. **INTEGRATION_GUIDE.md** - Full step-by-step instructions
4. **THIS FILE** - Quick code snippets for copy/paste

---

## Quick Test (2 minutes)

```bash
python3 test_tab_parsing.py
```

Look for: `🎉 EXCELLENT! Tab-based extraction captures significantly more content!`

---

## Code Changes (5 minutes)

### Location: `src/ingest/nihr_funding.py`

### Add 4 new methods to `NihrFundingScraper` class:

**Insert these around line 250-300, before `_parse_sections_from_headings`:**

```python
def _find_tab_navigation(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
    """Detect tab navigation and return list of (tab_name, tab_id)."""
    tabs = []
    
    # Find <ul> with tab/nav classes
    for container in soup.find_all("ul", class_=re.compile(r"(tab|nav)", re.I)):
        for link in container.find_all("a", href=True):
            href = link.get("href", "").strip()
            if href.startswith("#"):
                tabs.append((link.get_text(strip=True), href[1:]))
    
    # Fallback: direct #tab-* pattern search
    if not tabs:
        for link in soup.find_all("a", href=re.compile(r"^#tab-")):
            tabs.append((link.get_text(strip=True), link["href"][1:]))
    
    # Deduplicate
    return list(dict.fromkeys(tabs))

def _extract_tab_content(self, soup: BeautifulSoup, tab_id: str) -> Optional[dict]:
    """Extract content from a single tab panel."""
    panel = soup.find(id=tab_id)
    if not panel:
        return None
    return {
        "html": str(panel),
        "text": " ".join(panel.stripped_strings)
    }

def _parse_sections_with_tabs(self, soup: BeautifulSoup, page_url: str) -> List[NihrSection]:
    """Main parser: detect tabs and route accordingly."""
    tabs = self._find_tab_navigation(soup)
    if tabs:
        return self._parse_sections_from_tabs(soup, page_url, tabs)
    else:
        return self._parse_sections_from_headings(soup, page_url)

def _parse_sections_from_tabs(self, soup: BeautifulSoup, page_url: str, tabs: List[Tuple[str, str]]) -> List[NihrSection]:
    """Extract content from each tab panel."""
    sections = []
    for tab_name, tab_id in tabs:
        content = self._extract_tab_content(soup, tab_id)
        if content:
            sections.append(NihrSection(
                name=tab_name,
                slug=_slugify(tab_name),
                html=content["html"],
                text=content["text"],
                source_url=f"{page_url}#{tab_id}"
            ))
    return sections
```

### Update 1 existing method:

**Find and replace `_parse_sections_from_nav` (around line 350):**

```python
def _parse_sections_from_nav(self, base_url: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Main entry point - NOW TAB-AWARE."""
    sections = self._parse_sections_with_tabs(soup, base_url)  # Changed this line
    
    # Convert to dict for backward compatibility
    return [
        {"title": s.name, "url": s.source_url, "text": s.text, 
         "html": s.html, "slug": s.slug}
        for s in sections
    ]
```

---

## Quick Test Command

```python
from src.ingest.nihr_funding import NihrFundingScraper

scraper = NihrFundingScraper()
opp = scraper.scrape("https://www.nihr.ac.uk/funding/nihr-james-lind-alliance-priority-setting-partnerships-rolling-funding-opportunity-hsdr-programme/2025331")

print(f"Sections: {len(opp.sections)}")  # Should be 4-8, not 1-2
for s in opp.sections:
    print(f"  {s['title']:30s} {len(s['text']):6,} chars")
```

---

## Full Re-scrape Commands

```bash
# Backup
cp src/ingest/nihr_funding.py src/ingest/nihr_funding.py.backup
cp grants.db grants.db.backup

# Reset NIHR data
python3 scripts/reset_nihr_data.py --db grants.db --confirm

# Re-scrape
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# Verify
python3 check_data_balance.py
```

---

## Expected Results

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Sections per grant | 1-2 | 4-8 | +300% |
| Text per section | ~800 chars | ~3,000 chars | +275% |
| Embeddings per grant | 18 | 150-200 | +10x |
| Total NIHR embeddings | 8,234 | 60,000-90,000 | +10x |

---

## Debugging

If tabs not detected:
```python
# Check raw HTML
import requests
from bs4 import BeautifulSoup

soup = BeautifulSoup(requests.get(url).text, "lxml")
print(soup.find_all("a", href=lambda x: x and "#tab" in x))
```

If tab panels not found:
```python
# Check panel IDs
soup = BeautifulSoup(requests.get(url).text, "lxml")
print([div.get("id") for div in soup.find_all("div", id=True) if "tab" in div.get("id")])
```

---

## Rollback

```bash
cp src/ingest/nihr_funding.py.backup src/ingest/nihr_funding.py
cp grants.db.backup grants.db
```

---

## Done!

After implementing:
1. ✅ NIHR grants have proper content
2. ✅ Embedding imbalance reduced
3. ✅ Ailsa gives better NIHR recommendations
4. ✅ System is balanced and production-ready
