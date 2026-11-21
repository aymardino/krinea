"""Provider calls and what their failures mean (krinea_core.llm), with no network and no key:
the Gemini call goes through a fake google-genai client, and the errors are shaped like the
SDKs' own (an HTTP status in `code` or `status_code`, the provider's message)."""
from types import SimpleNamespace

import pytest

from krinea_core import llm


class ProviderError(Exception):
    def __init__(self, message, code=None, status_code=None):
        super().__init__(message)
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


@pytest.mark.parametrize("error, kind", [
    # Gemini, as its API answers made-up keys (old "AIza" and new "AQ." formats)
    (ProviderError("400 INVALID_ARGUMENT. {'message': 'API key not valid. Please pass a valid API key.', "
                   "'reason': 'API_KEY_INVALID'}", code=400), "key"),
    (ProviderError("401 UNAUTHENTICATED. {'message': 'API key not valid. Please pass a valid API key.', "
                   "'reason': 'ACCESS_TOKEN_TYPE_UNSUPPORTED'}", code=401), "key"),
    (ProviderError("404 NOT_FOUND. models/gemini-2.5-flash is not found for API version v1beta", code=404), "model"),
    (ProviderError("403 PERMISSION_DENIED. This model is no longer available to new users.", code=403), "model"),
    (ProviderError("403 PERMISSION_DENIED. Generative Language API has not been used in project 1", code=403), "key"),
    (ProviderError("429 RESOURCE_EXHAUSTED. You exceeded your current quota, please check your plan and "
                   "billing details.", code=429), "quota"),
    # Anthropic and DeepSeek (OpenAI SDK)
    (ProviderError("Error code: 401 - {'type': 'authentication_error', 'message': 'invalid x-api-key'}",
                   status_code=401), "key"),
    (ProviderError("Error code: 400 - Your credit balance is too low to access the Anthropic API.",
                   status_code=400), "credit"),
    (ProviderError("Error code: 402 - Insufficient Balance", status_code=402), "credit"),
    (ProviderError("Error code: 400 - Model Not Exist", status_code=400), "model"),
    (ProviderError("Error code: 429 - rate_limit_error", status_code=429), "quota"),
    # no usable answer, and the rest
    (llm.LLMError("gemini/gemini-x did not return valid JSON: Expecting value"), "output"),
    (TimeoutError("The read operation timed out"), "other"),
])
def test_error_kind(error, kind):
    assert llm.error_kind(error) == kind


def test_retry_after_waits_out_rate_limits_but_not_daily_quotas():
    per_minute = ProviderError("429 RESOURCE_EXHAUSTED. {'details': [{'quotaId': "
                               "'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'}, {'@type': "
                               "'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '31s'}]}", code=429)
    assert llm.retry_after(per_minute) == 32.0
    assert llm.retry_after(ProviderError("Quota exceeded. Please retry in 7.5s.", code=429)) == 8.5
    assert llm.retry_after(ProviderError("rate_limit_error", status_code=429)) == 20.0     # no delay given
    assert llm.retry_after(ProviderError("'retryDelay': '600s'", code=429)) == 60.0       # capped
    daily = ProviderError("429 RESOURCE_EXHAUSTED. {'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
                          "'retryDelay': '31s'}", code=429)
    assert llm.retry_after(daily) is None                                                 # resets tomorrow
    assert llm.retry_after(ProviderError("API key not valid", code=400)) is None


def test_gemini_call_uses_its_own_client_and_leaves_room_for_thinking(monkeypatch):
    from google import genai
    seen = {}

    class Models:
        def generate_content(self, *, model, contents, config):
            seen.update(model=model, contents=contents, config=config)
            usage = SimpleNamespace(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=300)
            return SimpleNamespace(text='{"decision": "include"}', usage_metadata=usage)

    class Client:
        def __init__(self, *, api_key, http_options=None):
            seen["key"] = api_key
            self.models = Models()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            seen["closed"] = True

    monkeypatch.setattr(genai, "Client", Client)
    data, usage = llm.call_json("Screen this record", "gemini", "AQ.test-key", purpose="screening", max_tokens=1024)

    assert data == {"decision": "include"}
    assert (usage.input_tokens, usage.output_tokens) == (100, 320)     # thinking is billed as output
    assert seen["key"] == "AQ.test-key" and seen["closed"]
    assert seen["model"] == llm.DEFAULT_MODELS["screening"]["gemini"] == "gemini-3.8-flash"
    config = seen["config"]
    assert config.max_output_tokens == 1024 + llm.GEMINI_THINKING_TOKENS    # 1024 would leave no room to answer
    assert config.response_mime_type == "application/json" and config.temperature is None


def test_no_default_model_is_one_google_closed_to_new_projects():
    for purpose in ("screening", "extraction"):
        assert not llm.DEFAULT_MODELS[purpose]["gemini"].startswith(("gemini-2.", "gemini-1."))
