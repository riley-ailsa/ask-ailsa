# ASK AILSA - STREAMING FIX SUMMARY

## 🔴 PROBLEM: Raw JSON Displayed Instead of Streaming Markdown

### What You See:
```
{ "answer_markdown": "Currently, there are no suitable grants available 
for comparing academic versus commercial applicants. However, understanding 
the general landscape of funding options can help you identify potential 
opportunities in the future.\n\n### Academic vs. Commercial Applicants..."
```

### What You Should See:
```
Currently, there are no suitable grants available for comparing academic 
versus commercial applicants. However, understanding the general landscape 
can help you identify future opportunities.

## Academic vs. Commercial Applicants

When considering funding, academic and commercial applicants face different 
eligibility criteria:

- **Academic Applicants**: Focus on research and scientific merit...
- **Commercial Applicants**: Emphasize market viability...
```

## 🔍 ROOT CAUSE

### The Data Flow (BROKEN):
```
User Question
    ↓
Backend /chat/stream endpoint
    ↓
SYSTEM_PROMPT says: "Return JSON with answer_markdown key"
    ↓
GPT outputs: {"answer_markdown": "text...", "recommended_grants": [...]}
    ↓
Streams character-by-character: { " a n s w e r _ m a r k d o w n " : . . .
    ↓
UI displays raw JSON string with green monospace font
```

### The Problem:
- Backend tells GPT to output JSON
- But streaming JSON character-by-character looks terrible
- User sees the raw JSON structure instead of formatted content

## ✅ SOLUTION

### The Data Flow (FIXED):
```
User Question
    ↓
Backend /chat/stream endpoint
    ↓
STREAMING_SYSTEM_PROMPT says: "Output PLAIN MARKDOWN (not JSON!)"
    ↓
GPT outputs: Currently, there are no suitable grants...
    ↓
Streams token-by-token: Currently there are no suitable grants...
    ↓
UI displays formatted markdown with proper styling
```

### The Fix:
- Change SYSTEM_PROMPT for streaming to request markdown
- Remove JSON parsing logic
- Stream markdown tokens directly to UI

## 🛠️ HOW TO FIX

### Fix #1: UI (Type Error)
**Problem:** Comparing string with int causes TypeError
**Solution:** Add type checking before numeric comparison

```bash
cp /home/claude/ui_app_fixed.py ui/app.py
```

### Fix #2: Backend (Streaming Endpoint)
**Problem:** Streaming JSON looks terrible
**Solution:** Output markdown instead of JSON for streaming

**Manual Steps:**
1. Open `src/api/server.py`
2. Find `@app.post("/chat/stream")` (around line 400)
3. Replace entire function with code from `/home/claude/fixed_streaming_endpoint.py`

**Key Change:**
```python
# OLD (returns JSON):
SYSTEM_PROMPT = """Return a JSON object with answer_markdown and recommended_grants keys..."""

# NEW (returns markdown):
STREAMING_SYSTEM_PROMPT = """Output PLAIN MARKDOWN only (NOT JSON!). 
This will be displayed directly to users as it streams..."""
```

### Fix #3: Restart
```bash
./start_api.sh   # Terminal 1
./start_ui.sh    # Terminal 2
```

## 📊 BEFORE vs AFTER

### BEFORE:
❌ Raw JSON displayed: `{ "answer_markdown": "..."`
❌ Green monospace font
❌ No streaming effect
❌ Very long responses (2000+ words)
❌ TypeError on grant cards

### AFTER:
✅ Clean markdown formatting
✅ Token-by-token streaming with cursor (●)
✅ Professional appearance
✅ Concise responses (300-500 words)
✅ Grant cards with proper metadata

## ⚡ QUICK START

### Option A: Semi-Automated
```bash
cd ~/grant-analyst-v2
/home/claude/apply_fixes.sh
# Then manually update /chat/stream in server.py
./start_api.sh
./start_ui.sh
```

### Option B: Manual
```bash
# 1. Fix UI
cp /home/claude/ui_app_fixed.py ui/app.py

# 2. Fix Backend
# Open src/api/server.py
# Replace /chat/stream function with code from:
# /home/claude/fixed_streaming_endpoint.py

# 3. Restart
./start_api.sh
./start_ui.sh
```

## 📚 DOCUMENTATION

- `/home/claude/COMPLETE_FIX_GUIDE.md` - Comprehensive guide
- `/home/claude/fixed_streaming_endpoint.py` - Complete fixed code
- `/home/claude/ui_app_fixed.py` - Fixed UI
- `/home/claude/STREAMING_FIX.txt` - Technical explanation

## ✨ SUCCESS CRITERIA

After applying fixes, test with: "Show me NIHR grants for clinical trials"

You should see:
1. Response appears token-by-token
2. Cursor (●) shows streaming in progress
3. Clean markdown with headers and bullets
4. ~300-500 words (concise)
5. Grant cards below with funding/deadline info
6. No TypeError messages
7. No raw JSON visible

If you see any of the old problems, refer to COMPLETE_FIX_GUIDE.md for debugging.
