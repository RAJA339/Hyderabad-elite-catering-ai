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
