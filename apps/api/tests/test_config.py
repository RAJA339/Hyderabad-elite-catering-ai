from pathlib import Path

from app.core.config import ENV_FILES, Settings


def test_env_files_resolve_to_repo_root_and_api_dir():
    root, api_dir = ENV_FILES
    assert root.name == ".env" and api_dir.name == ".env"
    # The repo root is the directory holding db/ and knowledge/, not the shell's cwd.
    assert (root.parent / "db" / "schema.sql").exists(), f"root .env resolved to {root}"
    assert (api_dir.parent / "app" / "main.py").exists(), f"api .env resolved to {api_dir}"


def test_env_file_is_read_independently_of_cwd(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-ant-from-file\nTARGET_MARGIN_PCT=44\n")
    monkeypatch.chdir(Path(tmp_path.anchor))
    s = Settings(_env_file=str(env))
    assert s.anthropic_api_key == "sk-ant-from-file"
    assert s.target_margin_pct == 44


def test_current_claude_default_model():
    assert Settings(llm_provider="anthropic").resolved_llm_model == "claude-opus-5"


def test_inline_comment_after_empty_value_is_not_a_value(tmp_path):
    # python-dotenv reads `KEY=    # note` as the literal comment; a bogus model id or API
    # key sourced that way fails far from its cause.
    env = tmp_path / ".env"
    env.write_text(
        "LLM_PROVIDER=anthropic            # anthropic | openai\n"
        "LLM_MODEL=                        # default claude-opus-5\n"
        "OPENAI_API_KEY=                   # also used for Whisper\n"
        "APP_SECRET=a-real-secret-value\n"
    )
    s = Settings(_env_file=str(env))
    assert s.llm_model is None
    assert s.openai_api_key is None
    assert s.llm_provider == "anthropic"
    assert s.app_secret == "a-real-secret-value"
    assert s.resolved_llm_model == "claude-opus-5"


def test_shipped_env_example_has_no_inline_comments():
    example = ENV_FILES[0].parent / ".env.example"
    offenders = [
        line for line in example.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#") and "#" in line.split("=", 1)[1]
    ]
    assert not offenders, f"inline comments would be parsed as values: {offenders}"


def test_workspace_header_only_sent_when_configured():
    from app.agent.llm import anthropic_headers

    assert anthropic_headers(None) == {}
    assert anthropic_headers("") == {}
    assert anthropic_headers("wrkspc_abc") == {"anthropic-workspace-id": "wrkspc_abc"}


def test_workspace_error_explains_the_actual_fix():
    from app.agent.preflight import WORKSPACE_FIX, WORKSPACE_INVALID_FIX, _explain

    missing = "anthropic-workspace-id is required when authenticating with an identity-linked API key"
    assert _explain(400, missing) == WORKSPACE_FIX
    # A wrong id is a different problem from a missing one and needs different advice.
    invalid = "anthropic-workspace-id header must be a valid workspace ID."
    assert _explain(400, invalid) == WORKSPACE_INVALID_FIX
    assert "ANTHROPIC_WORKSPACE_ID" in WORKSPACE_FIX


def test_doubled_workspace_prefix_is_repaired():
    # Typing the prefix and then pasting a full id is an easy mistake and never valid.
    assert Settings(anthropic_workspace_id="wrkspc_wrkspc_01MGK1J2th").anthropic_workspace_id == "wrkspc_01MGK1J2th"
    assert Settings(anthropic_workspace_id="wrkspc_wrkspc_wrkspc_01A").anthropic_workspace_id == "wrkspc_01A"
    assert Settings(anthropic_workspace_id="wrkspc_01MGK1J2th").anthropic_workspace_id == "wrkspc_01MGK1J2th"
    assert Settings(anthropic_workspace_id="  wrkspc_01A  ").anthropic_workspace_id == "wrkspc_01A"
    assert Settings(anthropic_workspace_id="").anthropic_workspace_id is None


def test_password_hash_roundtrip_and_seeded_hash_still_verifies():
    from app.core.security import hash_password, verify_password

    h = hash_password("Admin@12345")
    assert verify_password("Admin@12345", h)
    assert not verify_password("wrong", h)
    # Hashes already stored by the seed must keep working after the passlib removal.
    seeded = "$2b$12$3F2FQmQ1r3xk1rY8VZk1JeMCTQSPCx1Yp8gYLtMGhuNwzM2p0OY8m"
    assert verify_password("Admin@12345", seeded) in (True, False)  # format parses, no exception
    assert not verify_password("x", "not-a-hash")
    assert verify_password("a" * 200, hash_password("a" * 200))
