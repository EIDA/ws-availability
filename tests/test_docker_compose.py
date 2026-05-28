"""Static checks on docker-compose.yml.

These tests don't spin Docker up; they parse the YAML and assert structural
invariants we never want to silently regress. Tobias's beta test exposed a
class of bugs where someone added an env var to the api/cacher block whose
*hardcoded default* overrode the operator's config.py. We don't want that
shape to come back.
"""
from pathlib import Path
import re

import pytest

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover - PyYAML ships with the dev env
    pytest.skip("PyYAML is not installed", allow_module_level=True)


COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yml"

# Keys that must live in config.py only. If any of these appear in the
# api/cacher service env block, the operator's config.py will be silently
# overridden — the LMU/Tobias bug.
CONFIG_PY_ONLY_KEYS = {
    "MONGODB_HOST",
    "MONGODB_PORT",
    "MONGODB_USR",
    "MONGODB_PWD",
    "MONGODB_NAME",
    "MONGODB_AUTH_SOURCE",
    "FDSNWS_STATION_URL",
    "SENTRY_DSN",
    "SENTRY_TRACES_SAMPLE_RATE",
    "SENTRY_ENVIRONMENT",
}


@pytest.fixture(scope="module")
def compose():
    with COMPOSE_PATH.open() as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("service", ["api", "cacher"])
def test_no_config_py_keys_in_env_block(compose, service):
    env = compose["services"][service].get("environment", {}) or {}
    if isinstance(env, list):
        # docker-compose accepts either {KEY: VAL} or ["KEY=VAL"] form
        keys = {item.split("=", 1)[0] for item in env}
    else:
        keys = set(env.keys())
    leaked = keys & CONFIG_PY_ONLY_KEYS
    assert not leaked, (
        f"docker-compose.yml `{service}.environment` contains keys that must "
        f"be set in config.py only: {sorted(leaked)}. Adding them here makes "
        f"config.py silently lose (see the comment in apps/settings.py "
        f"build_settings)."
    )


def test_no_leaked_credentials_in_compose():
    """Catch the specific NOA values that were once committed: `wfrepouser`,
    `2023wf`, and the NOA-internal station URL. These should never be in
    docker-compose.yml again — they belong in operator-local config.py."""
    text = COMPOSE_PATH.read_text()
    for needle, why in [
        ("wfrepouser", "NOA-specific MONGODB_USR default"),
        ("2023wf", "NOA MongoDB password leaked in v1.0.x"),
        ("eida.gein.noa.gr", "NOA-internal station URL hardcoded"),
    ]:
        assert needle not in text, f"`{needle}` appeared in docker-compose.yml — {why}"


# --- BETA.md doc invariants ---------------------------------------------------

BETA_MD_PATH = Path(__file__).resolve().parents[1] / "BETA.md"


def test_beta_md_uses_cp_n_for_config():
    """Tobias's PR #62 review comment: use `cp -n config.py.sample config.py`
    instead of the two-line `[ -f config.py ] || cp ...` pattern.
    `cp -n` won't overwrite an existing config.py, which is exactly the
    upgrade-safe semantics we want."""
    text = BETA_MD_PATH.read_text()
    assert "cp -n config.py.sample config.py" in text, (
        "BETA.md must instruct operators to use `cp -n config.py.sample config.py` "
        "(safe no-clobber copy). Bare `cp` would overwrite an existing config.py."
    )
    assert "[ -f config.py ] || cp" not in text, (
        "BETA.md still has the old `[ -f config.py ] || cp ...` conditional. "
        "Switch to `cp -n config.py.sample config.py`."
    )


def test_beta_md_example_snippets_use_safe_getter_pattern():
    """Examples in BETA.md must use `os.environ.get('X', DEFAULT)`, never
    `os.environ.get('X') or DEFAULT`. Anything we teach in docs becomes
    cargo-culted into other operators' config.py files (PR #62)."""
    text = BETA_MD_PATH.read_text()
    import re
    bad = re.findall(r'os\.environ\.get\([^)]+\)\s+or\b', text)
    assert not bad, (
        f"BETA.md uses the leaky `os.environ.get(...) or X` pattern in "
        f"{len(bad)} place(s): {bad}. Use `os.environ.get('X', X)` instead."
    )


# --- Single source of truth for deps ----------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_no_stale_requirements_files():
    """Dependency pins live in uv.lock (built from pyproject.toml).
    The old hand-maintained `requirements-api.txt` / `requirements-cacher.txt`
    were obsolete pin sets (Flask 2.3.2, gunicorn 20.1, etc.) that Dependabot
    still scanned — they inflated the alert count with duplicates and led
    new contributors to wonder which lockfile was canonical."""
    for stale in ("requirements-api.txt", "requirements-cacher.txt"):
        assert not (REPO_ROOT / stale).exists(), (
            f"{stale} is back. Deps belong in pyproject.toml + uv.lock; "
            f"the Dockerfiles install via `uv sync --frozen`. If you really "
            f"need a pip-format lockfile, generate it with `uv export` at "
            f"build time instead of hand-maintaining a parallel one."
        )
