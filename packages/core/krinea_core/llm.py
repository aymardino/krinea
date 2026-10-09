"""
llm.py — One function to call any supported LLM provider and get JSON back,
with token usage so the application can meter it (Krinea decision D-16).

    from krinea_core import llm
    data, usage = llm.call_json(prompt, provider="claude", api_key=key, model="claude-haiku-5-5")

Providers: "claude" (Anthropic), "gemini" (Google), "deepseek" (OpenAI-compatible).
The provider SDKs are imported lazily, so this module imports without them.
Prompts that contain the marker "STUDY TEXT:" are split there: the part before
is sent as a cacheable system prompt (cheaper on repeated calls).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

PROVIDERS = ("claude", "gemini", "deepseek")
DEFAULT_MODELS = {
    "screening": {"claude": "claude-haiku-5-5", "gemini": "gemini-2.5-flash", "deepseek": "deepseek-v4-flash"},
    "extraction": {"claude": "claude-sonnet-5-5", "gemini": "gemini-2.5-pro", "deepseek": "deepseek-v4-pro"},
}
MARKER = "STUDY TEXT:"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMError(RuntimeError):
    pass


def parse_json(raw: str) -> dict:
    """Parse model output as JSON, tolerating fences, stray text and truncation."""
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    a, b = raw.find("{"), raw.rfind("}")
    if a != -1 and b != -1:
        try:
            return json.loads(raw[a:b + 1])
        except json.JSONDecodeError:
            pass
    if a != -1:                                   # truncated: salvage complete entries
        for m in reversed(list(re.finditer(r"\}", raw))[-200:]):
            candidate = raw[a:m.end()].rstrip().rstrip(",") + "}"
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("No JSON object in model output", raw, 0)


def _split(prompt: str) -> tuple[str, str]:
    if MARKER in prompt:
        head, tail = prompt.split(MARKER, 1)
        return head.strip(), MARKER + tail
    return "", prompt


def _call_claude(prompt: str, api_key: str, model: str, max_tokens: int) -> tuple[str, Usage]:
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    system, user = _split(prompt)
    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": user}]}
    if system:
        kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    resp = client.messages.create(**kwargs)
    text = "".join(getattr(b, "text", "") for b in resp.content)
    u = getattr(resp, "usage", None)
    usage = Usage(int(getattr(u, "input_tokens", 0) or 0) + int(getattr(u, "cache_read_input_tokens", 0) or 0)
                  + int(getattr(u, "cache_creation_input_tokens", 0) or 0),
                  int(getattr(u, "output_tokens", 0) or 0))
    return text, usage


def _call_gemini(prompt: str, api_key: str, model: str, max_tokens: int) -> tuple[str, Usage]:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gm = genai.GenerativeModel(model)
    resp = gm.generate_content(prompt, generation_config={
        "temperature": 0, "response_mime_type": "application/json", "max_output_tokens": max_tokens})
    um = getattr(resp, "usage_metadata", None)
    usage = Usage(int(getattr(um, "prompt_token_count", 0) or 0), int(getattr(um, "candidates_token_count", 0) or 0))
    return resp.text or "", usage


def _call_deepseek(prompt: str, api_key: str, model: str, max_tokens: int) -> tuple[str, Usage]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    system, user = _split(prompt)
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0,
                                          max_tokens=max_tokens, response_format={"type": "json_object"})
    u = getattr(resp, "usage", None)
    usage = Usage(int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0))
    return resp.choices[0].message.content or "", usage


_CALLERS = {"claude": _call_claude, "gemini": _call_gemini, "deepseek": _call_deepseek}


def call_json(prompt: str, provider: str, api_key: str, model: str | None = None,
              purpose: str = "screening", max_tokens: int = 8192, max_retries: int = 1) -> tuple[dict, Usage]:
    """Call the provider and return (parsed JSON, usage summed over retries)."""
    if provider not in _CALLERS:
        raise LLMError(f"Unknown provider {provider!r}; use one of {', '.join(PROVIDERS)}")
    if not api_key:
        raise LLMError(f"No API key available for {provider}")
    model = model or DEFAULT_MODELS[purpose][provider]
    total = Usage()
    last_err: Exception | None = None
    for _ in range(max_retries + 1):
        text, usage = _CALLERS[provider](prompt, api_key, model, max_tokens)
        total.input_tokens += usage.input_tokens
        total.output_tokens += usage.output_tokens
        try:
            return parse_json(text), total
        except json.JSONDecodeError as e:
            last_err = e
    raise LLMError(f"{provider}/{model} did not return valid JSON: {last_err}")
