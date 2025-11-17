# Ask Ailsa - UI Streaming & Response Length Fixes

## Issues Identified

1. **Streaming Not Working**: Responses showing as raw JSON with green monospace font
2. **Responses Too Long**: Generating 2000+ token responses that are overwhelming
3. **Poor UX**: Raw JSON visible to users instead of formatted markdown

## Root Causes

### Issue 1: Streaming Display Problem
- The backend IS streaming correctly (SSE format)
- But the UI has a bug in error handling that causes it to show raw JSON
- The `render_ailsa_response()` function was removed/broken

### Issue 2: Verbose Responses  
- System prompt encourages "thorough, comprehensive" responses
- `max_tokens=2000` allows very long outputs
- No guidance for conciseness

## Fixes Provided

### Fix 1: Updated UI (`ui_app_fixed.py`)

**What was fixed:**
✅ Robust SSE stream parsing with better error handling
✅ Proper logging to debug stream issues  
✅ Simplified markdown rendering (removed complex `render_ailsa_response`)
✅ Better error messages when streaming fails
✅ Increased timeout from 60s to 120s

**Key improvements:**
```python
# Better SSE parsing
for line in response.iter_lines(decode_unicode=True):
    if line.startswith("data: "):
        data = json.loads(line[6:])  # Remove "data: " prefix
        yield data

# Simpler rendering - just use st.markdown()
st.markdown(full_response)  # Instead of complex custom renderer
```

### Fix 2: Concise System Prompt (`backend_concise_prompt.txt`)

**What changed:**
✅ Reduced max_tokens from 2000 → 800
✅ Reduced temperature from 0.5 → 0.3 (more focused)
✅ New prompt emphasizes conciseness (300-500 words target)
✅ Clear structure: Summary → Top Grants → Next Steps
✅ Explicit instruction to avoid repeating metadata

**Target response format:**
```
[1-2 sentence summary]

## Grant Name
Brief description
**Why it fits:** ...
**Key tip:** ...

**Next steps:**
1. Action 1
2. Action 2
```

## Implementation Steps

### Step 1: Replace UI File

```bash
# Backup current file
cp ui/app.py ui/app.py.backup

# Replace with fixed version
cp /home/claude/ui_app_fixed.py ui/app.py
```

### Step 2: Update Backend Prompt

Open `src/api/server.py` and find line ~line 40 where it says:

```python
SYSTEM_PROMPT = """You are Ailsa, an expert UK research funding advisor...
```

Replace it with the `SYSTEM_PROMPT_CONCISE` from `/home/claude/backend_concise_prompt.txt`

### Step 3: Update Generation Settings

In `src/api/server.py`, find the `/chat/stream` endpoint around line ~400:

```python
# Find this:
for chunk in chat_llm_client.chat_stream(
    messages=messages,
    temperature=0.5,  # OLD
    max_tokens=2000,  # OLD
):

# Change to:
for chunk in chat_llm_client.chat_stream(
    messages=messages,
    temperature=0.3,  # NEW - more focused
    max_tokens=800,   # NEW - more concise
):
```

### Step 4: Restart Everything

```bash
# Stop current instances (Ctrl+C)

# Restart backend
./start_api.sh

# In another terminal, restart UI
./start_ui.sh
```

## Testing the Fixes

### Test 1: Verify Streaming Works
1. Ask: "Show me NIHR grants for clinical trials"
2. **Expected**: See tokens appearing one-by-one (with cursor ●)
3. **NOT**: See raw JSON like `{"answer_markdown": "...`

### Test 2: Verify Conciseness
1. Ask the same question
2. **Expected**: Response is 300-500 words (about 1-2 screen heights)
3. **NOT**: Multiple pages of text

### Test 3: Verify Formatting
1. Check that responses have:
   - Clear section headers (##)
   - Bullet points
   - Bold emphasis
   - Grant cards below response

## Debugging Tips

If streaming still shows JSON:
```bash
# Check backend logs
tail -f /path/to/api.log

# Check if SSE events are being sent correctly
curl -N http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "history": [], "active_only": true}'
```

If responses are still too long:
- Verify `max_tokens=800` was applied
- Check that SYSTEM_PROMPT mentions "300-500 words"
- Try temperature=0.2 for even more focused responses

## File Locations

**Fixed UI:**
```
/home/claude/ui_app_fixed.py
→ Copy to: ui/app.py
```

**Backend Prompt:**
```
/home/claude/backend_concise_prompt.txt
→ Apply to: src/api/server.py
```

## Before & After Example

**Before (what you were seeing):**
```
json { "answer_markdown": "You have 4 open NIHR grants for clinical trials...
[2000+ words of verbose text with lots of repetition]
...closing in the next 3 months. Here are the most relevant opportunities..."
```

**After (what you should see):**
```
You have 3 open NIHR clinical trial grants, closing between Dec 2 and Jan 7.
The HTA researcher-led grant is your strongest match.

## HTA researcher-led – primary research
Funds clinical trials within the Health Technology Assessment framework.

**Why it fits:** Perfect for researchers conducting clinical trials with HTA alignment.
**Key tip:** Emphasize collaboration and recent initiative building in your application.

[Grant cards appear below with funding/deadline metadata]

**Next steps:**
1. Prioritize Dec 2 deadlines - start applications now
2. Review HTA framework requirements on the grant page  
3. Consider EME Programme as backup - similar scope, later deadline
```

## Summary

**UI Fixes:**
- Robust streaming with proper error handling
- Simplified markdown rendering
- Better logging for debugging

**Backend Fixes:**
- Concise system prompt (300-500 word target)
- Reduced token limit (800 vs 2000)
- Lower temperature (0.3 vs 0.5)
- Clear response structure

**Result:**
- Proper streaming without raw JSON
- Concise, actionable responses
- Better user experience

---

Need help implementing? Let me know which step you're on!
