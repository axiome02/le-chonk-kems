import os
import pytest

from kems.llm.client import LLMClient
from kems.llm.env import load_env
from kems.llm.mistral import MistralClient


def test_load_env(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('FOO_KEY=abc123\n# comment\nBAR="ok"\n', encoding="utf-8")
    monkeypatch.delenv("FOO_KEY", raising=False)
    monkeypatch.delenv("BAR", raising=False)
    load_env(str(f))
    assert os.environ["FOO_KEY"] == "abc123"
    assert os.environ["BAR"] == "ok"


def test_load_env_missing_file_does_not_raise():
    load_env("non_existent_file.env")


def test_mistral_client_is_llm_client():
    m = MistralClient(api_key="fake")
    assert isinstance(m, LLMClient)
    assert m.name == "mistral"


def test_client_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        MistralClient()
