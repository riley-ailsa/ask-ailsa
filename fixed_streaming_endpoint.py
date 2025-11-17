"""
COMPLETE FIXED /chat/stream ENDPOINT
Copy this entire function to replace the existing one in src/api/server.py (around line 400)
"""

@app.post("/chat/stream")
async def chat_with_grants_stream(req: ChatRequest):
    """
    Streaming chat endpoint with real-time responses.

    Returns Server-Sent Events with JSON chunks:
    - {"type": "token", "content": "..."}  - Streamed response text
    - {"type": "grants", "grants": [...]}  - Recommended grants at the end
    - {"type": "done"}                      - End of stream
    """
    import json

    global chat_llm_client

    query = req.message.strip()
    if not query:
        async def empty_generator():
            yield f"data: {json.dumps({'type': 'token', 'content': 'Ask me something about funding.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(empty_generator(), media_type="text/event-stream")

    logger.info(f"/chat/stream query: {query!r}")

    # Initialize LLM client if needed
    if chat_llm_client is None:
        try:
            from src.llm.client import LLMClient
            chat_llm_client = LLMClient(model="gpt-4o-mini")
            logger.info("✓ Initialized GPT-4o-mini client for /chat/stream")
        except Exception as e:
            logger.error(f"✗ Failed to initialize GPT client: {e}")
            async def error_generator():
                yield f"data: {json.dumps({'type': 'token', 'content': 'GPT client not configured. Set OPENAI_API_KEY environment variable.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Get search hits
    try:
        hits = vector_index.query(
            query_text=query,
            top_k=20,
            filter_scope=None
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        async def error_generator():
            yield f"data: {json.dumps({'type': 'token', 'content': 'Search failed unexpectedly. Try rephrasing or asking again in a moment.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    if not hits:
        async def no_results_generator():
            msg = "I don't see anything in the current Innovate UK or NIHR data that clearly matches that. You might need a different funding body or a more general innovation grant."
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(no_results_generator(), media_type="text/event-stream")

    # Generate streaming response
    async def generate():
        try:
            # Step 1: Select top grants
            grants = select_top_grants(hits, query=query)

            # Step 2: Build context
            context = build_llm_context(query, hits, grants)

            # Step 3: Create streaming-specific prompt (outputs MARKDOWN, not JSON!)
            grants_list = "\n".join([f"- {g['title']} ({g['source']})" for g in grants[:5]])
            
            STREAMING_SYSTEM_PROMPT = f"""You are Ailsa, a UK research funding advisor for NIHR and Innovate UK grants.

CRITICAL: Output PLAIN MARKDOWN only (NOT JSON!). This will be displayed directly to users as it streams.

STYLE:
- Be concise: 300-500 words maximum
- Start with 1-2 sentence summary
- Use ## for section headers
- Use **bold** for emphasis  
- Use bullet lists for key details
- NO repetition of funding amounts/deadlines (shown in grant cards below)

STRUCTURE:
1. Brief summary answering the main question (1-2 sentences)
2. Top 2-3 relevant grants:
   - Grant name and why it fits
   - 2-3 key bullets (eligibility, application tips, strategic advice)
3. Next steps (2-3 specific actions)

The grants that will be displayed to users in cards below your response:
{grants_list}

Focus on insights, eligibility requirements, and application strategy."""

            messages = [
                {"role": "system", "content": STREAMING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"USER QUERY: {query}\n\n"
                        f"RELEVANT GRANT CONTEXT:\n{context}\n\n"
                        f"Provide helpful, concise advice in plain markdown."
                    ),
                },
            ]

            # Stream the response tokens as they arrive from LLM
            full_response = ""
            for chunk in chat_llm_client.chat_stream(
                messages=messages,
                temperature=0.3,  # Lower = more focused/concise
                max_tokens=800,   # Reduced from 2000 for brevity
            ):
                full_response += chunk
                # Stream each token immediately to the client
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            # Prepare grant cards with enriched metadata
            grant_refs = []
            for g in grants[:5]:
                # Get full grant details for enrichment
                try:
                    full_grant = grant_store.get_grant(g["grant_id"])
                    if full_grant:
                        grant_refs.append({
                            "grant_id": g["grant_id"],
                            "title": g["title"],
                            "url": g["url"],
                            "source": g["source"],
                            "is_active": full_grant.is_active,
                            "total_fund_gbp": full_grant.total_fund_gbp,
                            "closes_at": full_grant.closes_at.isoformat() if full_grant.closes_at else None,
                            "score": g.get("best_score", 0.0)
                        })
                    else:
                        # Fallback without enrichment
                        grant_refs.append({
                            "grant_id": g["grant_id"],
                            "title": g["title"],
                            "url": g["url"],
                            "source": g["source"],
                            "is_active": True,
                            "total_fund_gbp": g.get("total_fund_gbp"),
                            "closes_at": g.get("closes_at"),
                            "score": g.get("best_score", 0.0)
                        })
                except Exception as e:
                    logger.warning(f"Failed to enrich grant {g['grant_id']}: {e}")
                    # Use basic info
                    grant_refs.append({
                        "grant_id": g["grant_id"],
                        "title": g["title"],
                        "url": g["url"],
                        "source": g["source"],
                        "is_active": True,
                        "total_fund_gbp": None,
                        "closes_at": None,
                        "score": g.get("best_score", 0.0)
                    })

            # Send grants
            yield f"data: {json.dumps({'type': 'grants', 'grants': grant_refs})}\n\n"

            # Done
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'token', 'content': 'I found relevant grants, but encountered an error generating the response. Try asking again or narrow your question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
