"""
LLM Node execution with streaming:
Supports:
- OpenAI (stream=True via /v1/chat/completions)
- Anthropic (stream=True via /v1/messages)
- Ollama (stream=True via /api/chat at http://localhost:11434)
- Upstream item expression resolution
- Message history handling
- Real-time token streaming callback
"""

import json
import os
from typing import Any, Callable, Coroutine
import httpx

from .expressions import ExpressionContext, evaluate_string, evaluate_value
from .models import make_item


async def execute_llm_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    node_context: dict[str, Any],
    credentials: dict[str, str],
    on_token: Callable[[str], Coroutine[Any, Any, None]] | None = None,
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Executes the LLM node using upstream items as context and input.
    Calls LLM API with streaming and yields token callbacks.
    Returns output items containing the LLM response.
    """
    first_item = items[0] if items else make_item({})
    first_json = first_item.get("json", {})

    ctx = ExpressionContext(
        current_item=first_item,
        all_items=items,
        node_outputs=node_context,
    )

    provider = (cfg.get("llmProvider") or cfg.get("provider") or "openai").lower()
    model = cfg.get("model") or ("gpt-4o-mini" if provider == "openai" else ("claude-3-5-sonnet-20241022" if provider == "anthropic" else "llama3"))
    temperature = float(cfg.get("temperature", 0.0))

    # Evaluate system prompt and user prompt templates against upstream items
    raw_sys = cfg.get("systemPrompt") or "You are a helpful AI assistant."
    system_prompt = str(evaluate_string(raw_sys, ctx))

    raw_user_prompt = cfg.get("prompt") or cfg.get("userPrompt")
    if raw_user_prompt:
        user_prompt = str(evaluate_string(raw_user_prompt, ctx))
    else:
        # Fallback to upstream input message or stringified JSON
        user_prompt = (
            first_json.get("message")
            or first_json.get("text")
            or first_json.get("input")
            or json.dumps(first_json)
        )

    # Build messages array, incorporating history if present
    messages = []
    history = first_json.get("messages") or cfg.get("messages")
    if isinstance(history, list):
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                messages.append({
                    "role": msg["role"],
                    "content": evaluate_string(str(msg["content"]), ctx),
                })

    # Add the current user prompt if not already the last message in history
    if not (messages and messages[-1].get("role") == "user" and messages[-1].get("content") == user_prompt):
        messages.append({"role": "user", "content": user_prompt})

    full_response = ""

    # ── 1. Ollama (Local LLM) ─────────────────────────────────────────────────
    if provider == "ollama":
        base_url = (
            cfg.get("ollamaBaseUrl")
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")

        ollama_messages = [{"role": "system", "content": system_prompt}] + messages
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": ollama_messages,
                        "stream": True,
                        "options": {"temperature": temperature},
                    },
                ) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        full_response = f"Ollama error ({resp.status_code}): {err_text.decode('utf-8')[:300]}"
                    else:
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                token = chunk.get("message", {}).get("content", "")
                                if token:
                                    full_response += token
                                    if on_token:
                                        await on_token(token)
                            except Exception:
                                pass
        except Exception as exc:
            full_response = f"Error connecting to Ollama at {base_url}: {exc}. Ensure Ollama is running ('ollama serve')."

    # ── 2. Anthropic ──────────────────────────────────────────────────────────
    elif provider == "anthropic":
        key = credentials.get("anthropic_key") or os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            full_response = "Error: No Anthropic API key configured. Provide it in Vault or ANTHROPIC_API_KEY."
        else:
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": key,
                            "anthropic-version": "2023-06-01",
                        },
                        json={
                            "model": model,
                            "max_tokens": int(cfg.get("maxTokens", 2048)),
                            "temperature": temperature,
                            "system": system_prompt,
                            "messages": messages,
                            "stream": True,
                        },
                    ) as resp:
                        if resp.status_code != 200:
                            err_body = await resp.aread()
                            full_response = f"Anthropic error ({resp.status_code}): {err_body.decode('utf-8')[:300]}"
                        else:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                raw_data = line[6:].strip()
                                if raw_data == "[DONE]":
                                    break
                                try:
                                    evt = json.loads(raw_data)
                                    evt_type = evt.get("type")
                                    if evt_type == "content_block_delta":
                                        delta_text = evt.get("delta", {}).get("text", "")
                                        if delta_text:
                                            full_response += delta_text
                                            if on_token:
                                                await on_token(delta_text)
                                except Exception:
                                    pass
            except Exception as exc:
                full_response = f"Anthropic connection error: {exc}"

    # ── 3. OpenAI (default) ───────────────────────────────────────────────────
    else:
        key = credentials.get("openai_key") or os.getenv("OPENAI_API_KEY", "")
        if not key:
            # Fallback for local testing if no key: provide a clean test response
            full_response = (
                f"[Simulated response from {model}]: Received input '{user_prompt[:80]}'. "
                f"Add your OpenAI or Anthropic API key in the Vault to get live completions, "
                f"or select Ollama for free 100% offline local inference."
            )
            if on_token:
                for word in full_response.split(" "):
                    await on_token(word + " ")
        else:
            openai_messages = [{"role": "system", "content": system_prompt}] + messages
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {key}",
                        },
                        json={
                            "model": model,
                            "temperature": temperature,
                            "messages": openai_messages,
                            "stream": True,
                        },
                    ) as resp:
                        if resp.status_code != 200:
                            err_body = await resp.aread()
                            full_response = f"OpenAI error ({resp.status_code}): {err_body.decode('utf-8')[:300]}"
                        else:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                raw_data = line[6:].strip()
                                if raw_data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(raw_data)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        full_response += delta
                                        if on_token:
                                            await on_token(delta)
                                except Exception:
                                    pass
            except Exception as exc:
                full_response = f"OpenAI connection error: {exc}"

    # Construct output item with response and metadata
    result_json = dict(first_json)
    result_json.update({
        "response": full_response,
        "text": full_response,
        "content": full_response,
        "model": model,
        "provider": provider,
    })

    return {0: [make_item(result_json)]}
