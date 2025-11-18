# Integration Guide: Tab-Aware NIHR Scraping

## Problem Summary
- **NIHR**: 450 grants, 8,234 embeddings → ~18 embeddings/grant
- **IUK**: 36 grants, 32,641 embeddings → ~907 embeddings/grant

**Root cause**: NIHR scraper only captures first/default tab content. Pages have tabs like `#tab-overview`, `#tab-applications`, `#tab-eligibility` but we're missing 80%+ of the content.

## Solution
Add tab detection and explicit tab-panel extraction (similar to how IUK scraper uses navigation).

---

## Step 1: Test the approach (5 minutes)

```bash
# Run the test script to verify tabs exist on NIHR pages
python3 test_tab_parsing.py
```

**Expected output:**
```
📑 Tabs detected:
    - Overview              → #tab-overview
    - Applications          → #tab-applications
    - Eligibility           → #tab-eligibility
    ...

📊 Total content from h2 approach: 2,500 chars
📊 Total content from tab approach: 15,000 chars
📈 Improvement: 500% more content

🎉 EXCELLENT! Tab-based extraction captures significantly more content!
```

If you see this, proceed to Step 2. If not, we need to adjust the detection logic.

---

## Step 2: Back up current scraper

```bash
cp src/ingest/nihr_funding.py src/ingest/nihr_funding.py.backup
```

---

## Step 3: Add new methods to NihrFundingScraper class

Open `src/ingest/nihr_funding.py` and find the `NihrFundingScraper` class.

### 3a. Add these new methods BEFORE `_parse_sections_from_headings`

```python
class NihrFundingScraper:
    # ... existing __init__ and other methods ...
    
    # ADD THESE NEW METHODS HERE (around line 250-300)
    
    def _find_tab_navigation(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Detect tab-based navigation in NIHR pages.
        
        NIHR pages often use tabs with structure like:
            <ul class="nav nav-tabs">
              <li><a href="#tab-overview">Overview</a></li>
              <li><a href="#tab-applications">Applications</a></li>
            </ul>
        
        Returns:
            List of (tab_name, tab_id) tuples
        """
        tabs = []
        
        # Strategy 1: Look for <ul> with class containing "tab" or "nav"
        tab_containers = soup.find_all("ul", class_=re.compile(r"(tab|nav)", re.I))
        
        for container in tab_containers:
            for link in container.find_all("a", href=True):
                href = link.get("href", "").strip()
                
                if not href.startswith("#"):
                    continue
                
                tab_id = href[1:]
                tab_name = link.get_text(strip=True)
                
                if not tab_name or not tab_id:
                    continue
                
                tabs.append((tab_name, tab_id))
                logger.debug(f"Found tab: {tab_name} -> #{tab_id}")
        
        # Strategy 2: Look for links with href="#tab-*" pattern
        if not tabs:
            for link in soup.find_all("a", href=re.compile(r"^#tab-")):
                href = link.get("href", "").strip()
                tab_id = href[1:]
                tab_name = link.get_text(strip=True)
                
                if tab_name and tab_id:
                    tabs.append((tab_name, tab_id))
                    logger.debug(f"Found tab (pattern): {tab_name} -> #{tab_id}")
        
        # Deduplicate by tab_id
        seen_ids = set()
        unique_tabs = []
        for name, tid in tabs:
            if tid not in seen_ids:
                seen_ids.add(tid)
                unique_tabs.append((name, tid))
        
        if unique_tabs:
            logger.info(f"Detected {len(unique_tabs)} tabs on page")
        
        return unique_tabs
    
    def _extract_tab_content(self, soup: BeautifulSoup, tab_id: str) -> Optional[dict]:
        """
        Extract HTML and text content from a specific tab panel.
        
        Args:
            soup: Parsed HTML
            tab_id: Tab panel ID (without #), e.g., "tab-overview"
        
        Returns:
            dict with 'html' and 'text' keys, or None if not found
        """
        tab_panel = soup.find(id=tab_id)
        
        if not tab_panel:
            logger.warning(f"Tab panel not found: #{tab_id}")
            return None
        
        html = str(tab_panel)
        text = " ".join(tab_panel.stripped_strings)
        
        logger.debug(f"Tab #{tab_id}: {len(html)} chars HTML, {len(text)} chars text")
        
        return {"html": html, "text": text}
    
    def _parse_sections_with_tabs(self, soup: BeautifulSoup, page_url: str) -> List[NihrSection]:
        """
        Parse sections with tab awareness.
        
        Strategy:
        1. Detect if page has tab navigation
        2. If yes: Extract content from each tab panel
        3. If no: Fall back to h2 heading-based parsing
        """
        tabs = self._find_tab_navigation(soup)
        
        if tabs:
            logger.info(f"Using tab-based extraction ({len(tabs)} tabs)")
            return self._parse_sections_from_tabs(soup, page_url, tabs)
        else:
            logger.info("No tabs detected, using h2-based extraction")
            return self._parse_sections_from_headings(soup, page_url)
    
    def _parse_sections_from_tabs(
        self, 
        soup: BeautifulSoup, 
        page_url: str, 
        tabs: List[Tuple[str, str]]
    ) -> List[NihrSection]:
        """Extract sections by walking through each tab panel."""
        sections = []
        
        for tab_name, tab_id in tabs:
            content = self._extract_tab_content(soup, tab_id)
            
            if not content:
                logger.warning(f"Skipping tab {tab_name} (no content)")
                continue
            
            slug = _slugify(tab_name)
            source_url = f"{page_url}#{tab_id}"
            
            section = NihrSection(
                name=tab_name,
                slug=slug,
                html=content["html"],
                text=content["text"],
                source_url=source_url
            )
            
            sections.append(section)
            logger.debug(f"Extracted tab: {tab_name} ({len(content['text'])} chars)")
        
        return sections
```

### 3b. Update `_parse_sections_from_nav` method

Find the existing `_parse_sections_from_nav` method (around line 350) and REPLACE it with:

```python
def _parse_sections_from_nav(self, base_url: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Main entry point for section parsing.
    NOW TAB-AWARE: Detects and handles tabbed content.
    """
    # Use new tab-aware parser
    sections = self._parse_sections_with_tabs(soup, base_url)
    
    # Convert NihrSection objects to dicts for backward compatibility
    return [
        {
            "title": s.name,
            "url": s.source_url,
            "text": s.text,
            "html": s.html,
            "slug": s.slug
        }
        for s in sections
    ]
```

---

## Step 4: Test on a single URL

```python
from src.ingest.nihr_funding import NihrFundingScraper

scraper = NihrFundingScraper()
url = "https://www.nihr.ac.uk/funding/nihr-james-lind-alliance-priority-setting-partnerships-rolling-funding-opportunity-hsdr-programme/2025331"

opp = scraper.scrape(url)

print(f"\n✅ Scraping successful!")
print(f"Sections found: {len(opp.sections)}")
print(f"\nSection breakdown:")
for section in opp.sections:
    print(f"  - {section['title']:30s} ({len(section['text']):6,} chars)")
```

**Expected output:**
```
✅ Scraping successful!
Sections found: 5

Section breakdown:
  - Overview                     ( 3,200 chars)
  - Applications                 ( 4,500 chars)
  - Eligibility                  ( 2,800 chars)
  - Guidance                     ( 5,100 chars)
  - Key dates                    ( 1,200 chars)
```

**Before (old scraper):**
```
Sections found: 2
  - Overview                     (   800 chars)
  - Key dates                    (   400 chars)
```

---

## Step 5: Reset and re-scrape NIHR data

```bash
# Delete old NIHR data
python3 scripts/reset_nihr_data.py --db grants.db --confirm

# Re-scrape with new tab-aware parser
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt
```

---

## Step 6: Verify the fix

```bash
# Check new embedding counts
python3 check_data_balance.py
```

**Expected results:**
- **Before**: NIHR had ~18 embeddings/grant
- **After**: NIHR should have ~150-200 embeddings/grant

**Why not 907 like IUK?**
- IUK grants genuinely have MORE content (long PDFs, detailed guidance docs)
- NIHR pages are shorter, but we should capture ALL of what's there
- The imbalance will be reduced from 50x to maybe 4-6x (which is legitimate content difference)

---

## Rollback Plan

If something goes wrong:

```bash
# Restore backup
cp src/ingest/nihr_funding.py.backup src/ingest/nihr_funding.py

# Restore old database
# (Keep a backup of grants.db before Step 5!)
cp grants.db.backup grants.db
```

---

## Success Criteria

✅ Tab detection works on test NIHR URLs  
✅ Single URL test shows 4-8 sections instead of 1-2  
✅ Each section has substantial content (>1000 chars)  
✅ Full re-scrape completes without errors  
✅ NIHR embeddings increase from ~8K to ~60-90K total  
✅ Search quality improves (NIHR grants appear in relevant searches)

---

## Testing Checklist

- [ ] Run `test_tab_parsing.py` successfully
- [ ] Back up `nihr_funding.py` 
- [ ] Add new methods to scraper
- [ ] Update `_parse_sections_from_nav`
- [ ] Test on 1 URL - verify section count increases
- [ ] Test on 5 URLs - ensure no errors
- [ ] Back up current `grants.db`
- [ ] Reset NIHR data
- [ ] Full re-scrape of all 450 grants
- [ ] Verify embedding counts improved
- [ ] Test Ailsa with algae biofuel query - should show better NIHR results

---

## Need Help?

If you hit issues:
1. Check logs for "Detected N tabs" messages
2. Verify tab_id patterns match NIHR's HTML structure
3. Test with multiple NIHR URLs to ensure pattern holds
4. Share error messages for debugging
