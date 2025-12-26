from packages.llm.client import LlmClient, LlmConfig


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_llm_client_parses_json(monkeypatch) -> None:
    payload = {
        "message": {
            "content": (
                '{"intent":"test","reply":"ok","questions":[],"actions":[],"evidence_needed":[]}'
            )
        }
    }
    monkeypatch.setattr(
        "packages.llm.client.httpx.post", lambda *args, **kwargs: _FakeResponse(payload)
    )
    client = LlmClient(
        LlmConfig(
            provider="ollama",
            base_url="http://fake",
            model_name="qwen2.5:7b-instruct-q4",
            temperature=0.3,
            max_tokens=200,
            json_mode=True,
        )
    )
    output = client.generate_structured("sys", "user", "ctx")
    assert output.intent == "test"


def test_llm_client_fallback_on_invalid_json(monkeypatch) -> None:
    payload = {"message": {"content": "not-json"}}
    monkeypatch.setattr(
        "packages.llm.client.httpx.post", lambda *args, **kwargs: _FakeResponse(payload)
    )
    client = LlmClient(
        LlmConfig(
            provider="ollama",
            base_url="http://fake",
            model_name="qwen2.5:7b-instruct-q4",
            temperature=0.3,
            max_tokens=200,
            json_mode=True,
        )
    )
    output = client.generate_structured("sys", "user", "ctx")
    assert output.intent == "ask_clarifying_question"
