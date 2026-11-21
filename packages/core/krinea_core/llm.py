"""
llm.py — One function to call any supported LLM provider and get JSON back,
with token usage so the application can meter it (Krinea decision D-16).

    from krinea_core import llm
    data, usage = llm.call_json(prompt, provider="claude", api_key=key, model="claude-haiku-5-5")

Providers: "claude" (Anthropic), "gemini" (Google, through the google-genai SDK),
"deepseek" (OpenAI-compatible). The provider SDKs are imported lazily, so this module
imports without them. Prompts that contain the marker "STUDY TEXT:" are split there: the
part before is sent as a cacheable system prompt (cheaper on repeated calls).

When a call fails, `error_kind` says what it means for the user (key refused, model not
available, quota, credit...) and `retry_after` whether waiting would help.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

PROVIDERS = ("claude", "gemini", "deepseek")
# New reviews start on Gemini, with 3.8 Flash for screening and extraction alike (Krinea
# decision D-38). Since 18 September 2026 Google opens the 2.5 models only to projects that
# used them before.
DEFAULT_PROVIDER = "gemini"
DEFAULT_MODELS = {
    "screening": {"claude": "claude-haiku-5-5", "gemini": "gemini-3.8-flash", "deepseek": "deepseek-v4-flash"},
    "extraction": {"claude": "claude-sonnet-5-5", "gemini": "gemini-3.8-flash", "deepseek": "deepseek-v4-pro"},
}
MARKER = "STUDY TEXT:"
# Gemini models think before they answer and the thinking counts against max_output_tokens:
# under a small cap the call ends before the answer starts, with an empty reply, and a long
# answer is cut off. The thinking gets this room on top of the answer's.
GEMINI_THINKING_TOKENS = 8192
# The largest answer the DeepSeek models are asked for.
DEEPSEEK_MAX_OUTPUT_TOKENS = 8192


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
    from google import genai
    from google.genai import types
    # One client per call: the key goes with this request only, never into process-wide state,
    # so calls made at the same time with different users' keys cannot swap them. No
    # temperature: Gemini 3 models are meant to run at their default one.
    with genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=300_000)) as client:
        resp = client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(
            response_mime_type="application/json", max_output_tokens=max_tokens + GEMINI_THINKING_TOKENS))
    um = getattr(resp, "usage_metadata", None)
    usage = Usage(int(getattr(um, "prompt_token_count", 0) or 0),          # thinking is billed as output
                  int(getattr(um, "candidates_token_count", 0) or 0) + int(getattr(um, "thoughts_token_count", 0) or 0))
    return resp.text or "", usage


def _call_deepseek(prompt: str, api_key: str, model: str, max_tokens: int) -> tuple[str, Usage]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    system, user = _split(prompt)
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0,
                                          max_tokens=min(max_tokens, DEEPSEEK_MAX_OUTPUT_TOKENS),
                                          response_format={"type": "json_object"})
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


_KEY_WORDS = ("api key", "api_key", "x-api-key", "authentication", "unauthenticated", "access_token_type")
_GONE_WORDS = ("not found", "no longer", "not available", "unavailable", "not supported", "not exist", "retired")


def error_kind(e: BaseException) -> str:
    """What a failed provider call means for the user, so that the application can say what to
    do: "key" (the key is refused), "model" (unknown, retired, or not open to this key), "quota"
    (a rate or usage limit), "credit" (no balance left), "output" (no usable answer) or "other".
    Read from the HTTP status the SDKs carry (`status_code` for Anthropic and OpenAI, `code` for
    Google) and from the provider's message."""
    code = next((c for c in (getattr(e, "status_code", None), getattr(e, "code", None))
                 if isinstance(c, int) and not isinstance(c, bool)), None)
    text = str(e).lower()
    if code == 402 or "credit balance" in text or "insufficient balance" in text:
        return "credit"
    if code == 429 or "resource_exhausted" in text or "rate limit" in text or "quota" in text:
        return "quota"
    if code == 401 or any(w in text for w in _KEY_WORDS):
        return "key"
    if code == 404 or ("model" in text and any(w in text for w in _GONE_WORDS)):
        return "model"
    if code == 403:                       # permission refused to this key (API not enabled...)
        return "key"
    if "valid json" in text or "no json" in text:
        return "output"
    return "other"


def retry_after(e: BaseException, default: float = 20.0, cap: float = 60.0) -> float | None:
    """Seconds to wait before calling again after a rate limit, or None when waiting would not
    help: not a rate limit, or a daily quota (it resets the next day). Uses the delay the
    provider asks for when its message gives one (Gemini: "retryDelay': '31s'")."""
    if error_kind(e) != "quota":
        return None
    text = str(e)
    if re.search(r"per ?day|daily", text, re.IGNORECASE):
        return None
    m = re.search(r"retry(?:[ _-]?delay)?\W+(?:in\s+)?(\d+(?:\.\d+)?)\s*s\b", text, re.IGNORECASE)
    return min(cap, float(m.group(1)) + 1) if m else default
