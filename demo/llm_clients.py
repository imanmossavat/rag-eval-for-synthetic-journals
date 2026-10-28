"""
llm_clients.py — the model calls the demo needs, and nothing else.

  api_json(prompt, schema)   Claude via the Anthropic API, JSON guaranteed by a schema.
                             Used for GENERATING data (the "big model writes the world" step).
  local_json(prompt, model)  Same contract on a local Ollama model — the fallback when no
                             API key is set (`--backend local`).
  chat(model, system, user)  A local Ollama model answering a question. Used by the chatbots
                             UNDER TEST — these are the small/large models we compare.
  embed(texts, kind)         Local embeddings (nomic-embed-text) for the vector-search chatbot.
"""

import json
import os
import time

import requests

OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
API_MODEL = os.environ.get("DEMO_API_MODEL", "claude-opus-5-5")
LOCAL_GEN_MODEL = os.environ.get("DEMO_LOCAL_GEN_MODEL", "qwen3:30b")
EMBED_MODEL = "nomic-embed-text"


def api_json(prompt: str, schema: dict, effort: str = "medium") -> dict:
    import anthropic

    client = anthropic.Anthropic()
    # Server-side fallbacks: if a safety classifier declines, the API re-routes the
    # request instead of returning a refusal. Synthetic journal text should never
    # trip it; this is a cheap safety net, not something the demo relies on.
    message = client.beta.messages.create(
        model=API_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort,
                       "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if message.stop_reason == "refusal":
        raise RuntimeError("API declined the request (stop_reason=refusal)")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("API response truncated at max_tokens")
    text = next(b.text for b in message.content if b.type == "text")
    return json.loads(text)


def local_json(prompt: str, schema: dict, model: str = LOCAL_GEN_MODEL) -> dict:
    # Ollama accepts a JSON schema in `format` and constrains decoding to it.
    body = _ollama("generate", {
        "model": model, "prompt": prompt, "stream": False, "format": schema,
        "think": False, "options": {"num_ctx": 16384, "temperature": 0.7},
    })
    return json.loads(body["response"])


def chat(model: str, system: str, user: str, num_ctx: int = 16384) -> str:
    if model.startswith("qwen3:"):
        # Some qwen3 builds ignore Ollama's think=False and reason inline in the
        # answer; qwen3's own soft switch turns that off reliably.
        user += " /no_think"
    body = _ollama("chat", {
        "model": model, "stream": False, "think": False,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "options": {"num_ctx": num_ctx, "temperature": 0},
    })
    if body.get("done_reason") == "length":
        raise RuntimeError(f"{model}: output hit the context limit (num_ctx={num_ctx})")
    text = body["message"]["content"]
    return text.split("</think>")[-1].strip()


def embed(texts: list[str], kind: str) -> list[list[float]]:
    # nomic-embed-text was trained with these task prefixes; leaving them off
    # measurably lowers retrieval quality.
    prefix = "search_query: " if kind == "query" else "search_document: "
    body = _ollama("embed", {"model": EMBED_MODEL, "input": [prefix + t for t in texts]})
    return body["embeddings"]


def _ollama(endpoint: str, payload: dict, retries: int = 3) -> dict:
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(f"{OLLAMA}/api/{endpoint}", json=payload, timeout=1800)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Ollama is not reachable at {OLLAMA} — run `ollama serve`")
        except requests.exceptions.HTTPError:
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
