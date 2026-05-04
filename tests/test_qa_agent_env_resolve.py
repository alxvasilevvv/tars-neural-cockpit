import os

from scripts.qa_agent.env_resolve import resolved_ingest_api_key


def test_resolved_ingest_prefers_explicit_cli():
    os.environ.pop("TARS_INGEST_API_KEY", None)
    os.environ.pop("MEEET_API_KEY", None)
    assert resolved_ingest_api_key("from-cli") == "from-cli"


def test_resolved_ingest_tar_before_meeet():
    os.environ["TARS_INGEST_API_KEY"] = "tar"
    os.environ["MEEET_API_KEY"] = "meeet"
    try:
        assert resolved_ingest_api_key(None) == "tar"
        # CLI empty / whitespace-only is treated as unset — fall back to env.
        assert resolved_ingest_api_key("") == "tar"
        assert resolved_ingest_api_key("   ") == "tar"
    finally:
        os.environ.pop("TARS_INGEST_API_KEY", None)
        os.environ.pop("MEEET_API_KEY", None)


def test_resolved_ingest_falls_back_to_meeet():
    os.environ.pop("TARS_INGEST_API_KEY", None)
    os.environ["MEEET_API_KEY"] = "meeet-only"
    try:
        assert resolved_ingest_api_key(None) == "meeet-only"
    finally:
        os.environ.pop("MEEET_API_KEY", None)
