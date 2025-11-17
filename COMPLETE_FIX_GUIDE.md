# COMPLETE FIX GUIDE: Streaming & JSON Display Issues

## 🐛 Root Cause Analysis

**The Problem:** Responses appear as raw JSON instead of streaming markdown

**Why It Happens:**
1. Backend's SYSTEM_PROMPT tells GPT: "Return a JSON object with answer_markdown and recommended_grants"
2. GPT obeys and outputs: `{"answer_markdown": "Your text here...", "recommended_grants": [...]}`
3. This JSON gets streamed character-by-character to the UI
4. User sees: `{ "answer_markdown": "Currently, there are no...`

**The Core Issue:** You can't stream JSON nicely. You need to stream plain markdown.

## ✅ Complete Solution

### Fix 1: Update UI (Type Error)
The UI has a bug comparing strings with numbers.

```bash
cp /home/claude/ui_app_fixed.py ui/app.py
```

### Fix 2: Update Backend (Streaming Endpoint)
The backend needs to output markdown, not JSON, for the streaming endpoint.

**Open:** `src/api/server.py`

**Find:** The `@app.post("/chat/stream")` function (around line 400)

**Replace:** The entire function with the code from `/home/claude/fixed_streaming_endpoint.py`

**Quick way:**
```bash
# Backup first
cp src/api/server.py src/api/server.py.backup

# Then manually replace the /chat/stream function with the fixed version
```

**Key changes in the fixed version:**
- Uses a STREAMING_SYSTEM_PROMPT that requests markdown output (not JSON)
- Removes all JSON parsing logic
- Streams markdown tokens directly
- Adds better error handling
- Includes proper grant metadata enrichment

### Fix 3: Restart Everything

```bash
# Stop current processes (Ctrl+C in both terminals)

# Terminal 1: Start backend
./start_api.sh

# Terminal 2: Start UI
./start_ui.sh
```

## 📋 Testing Checklist

### Test 1: Verify Streaming Works
1. Ask: "Show me NIHR grants for clinical trials"
2. **Expected:** 
   - See markdown text appearing token-by-token
   - See cursor (●) while streaming
   - Clean formatted response
3. **NOT Expected:**
   - Raw JSON like `{"answer_markdown": ...`
   - Green monospace font
   - Response appears all at once

### Test 2: Verify Conciseness
1. Ask any question
2. **Expected:** Response is ~300-500 words (1-2 screen heights)
3. **NOT Expected:** Multiple pages of text

### Test 3: Verify Grant Cards
1. Check that grant cards appear below the response
2. **Expected:**
   - Grant title
   - Source badge (NIHR or INNOVATE UK)
   - Funding amount (if available)
   - Deadline date
3. **NOT Expected:**
   - TypeError about comparing strings and ints
   - Missing metadata

## 🔍 Debugging Tips

### If Still Showing JSON

**Check backend logs:**
```bash
# Look for errors in the API terminal
# Should see: "✓ Initialized GPT-4o-mini client for /chat/stream"
```

**Test the endpoint directly:**
```bash
curl -N http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "history": [], "active_only": true, "sources": null}' \
  | head -20
```

**Expected output:**
```
data: {"type": "token", "content": "Here"}
data: {"type": "token", "content": " are"}
data: {"type": "token", "content": " some"}
...
```

**NOT expected:**
```
data: {"type": "token", "content": "{\"answer_markdown\":"}
```

### If Responses Still Too Long

1. Verify `max_tokens=800` in the streaming endpoint
2. Verify `temperature=0.3` in the streaming endpoint
3. Check the STREAMING_SYSTEM_PROMPT says "300-500 words maximum"

### If TypeError Still Occurs

1. Verify you're using the fixed UI from `/home/claude/ui_app_fixed.py`
2. Check line ~203 has: `if funding and isinstance(funding, (int, float)):`

## 📁 File Locations

**Fixed UI:**
- Source: `/home/claude/ui_app_fixed.py`
- Destination: `ui/app.py`

**Fixed Backend Endpoint:**
- Source: `/home/claude/fixed_streaming_endpoint.py`
- Destination: Replace `/chat/stream` function in `src/api/server.py`

**Documentation:**
- `/home/claude/FIX_SUMMARY.md` - Original fix summary
- `/home/claude/STREAMING_FIX.txt` - Streaming-specific explanation
- `/home/claude/QUICK_FIX_INSTRUCTIONS.txt` - Type error fix

## 🎯 Expected Behavior After Fixes

### Before (Broken):
```
User asks question
→ Backend returns entire JSON object
→ JSON streamed character-by-character
→ User sees: { "answer_markdown": "text..." }
→ Green monospace font
→ Very long responses (2000+ words)
```

### After (Fixed):
```
User asks question
→ Backend streams markdown tokens
→ UI displays each token immediately
→ User sees: "You have 3 open grants for clinical trials..."
→ Normal formatting with headers and bullets
→ Concise responses (300-500 words)
→ Grant cards appear below with metadata
```

## ⚡ Quick Commands Summary

```bash
# Fix UI
cp /home/claude/ui_app_fixed.py ui/app.py

# Fix Backend (manual - copy /chat/stream function from fixed_streaming_endpoint.py)
# Edit src/api/server.py and replace the function

# Restart
./start_api.sh  # Terminal 1
./start_ui.sh   # Terminal 2
```

## 🆘 Still Having Issues?

1. Check that OPENAI_API_KEY is set in .env
2. Verify both backend and UI are using localhost:8000 and localhost:8501
3. Clear browser cache and hard refresh
4. Check for Python errors in both terminal windows
5. Try a different browser

## 📞 Next Steps

Once fixed, the system should:
- ✅ Stream responses smoothly with cursor
- ✅ Display clean formatted markdown
- ✅ Show concise 300-500 word responses
- ✅ Display grant cards with proper metadata
- ✅ No more raw JSON or TypeError messages

Test with the sample questions to verify everything works!
