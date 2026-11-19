#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8,<9", "pyyaml>=6,<7"]
# ///
"""The pipeline's mechanical rules (CODING_STANDARDS.md "The pipeline"), checked offline.

    uv run scripts/test_pipeline.py

Reads both billed workflows and runs their steps, and the README's secret snippets, with
a fake `rce` and `gh`: starts no Run, calls no RCE, sets no secret. `scripts/check` runs it.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = ["roku-test.yml", "roku-test-pool.yml"]
STARTED = json.dumps({"id": 375, "status": "running", "run": {"id": 9000}})


def workflow(name: str) -> dict:
    return yaml.safe_load((REPO / ".github/workflows" / name).read_text())


def job(name: str) -> dict:
    (only,) = workflow(name)["jobs"].values()
    return only


def role(step: dict) -> str:
    """What a step does, as the standards name it."""
    run = step.get("run", "")
    if "rce device start" in run:
        return "start"
    if "rce device stop" in run:
        return "stop"
    if "tests/test_app.py" in run:
        return "tests"
    if "Dev Password" in step.get("name", ""):
        return "password"
    return step.get("name") or step["uses"]


def step(name: str, wanted: str) -> dict:
    (found,) = [s for s in job(name)["steps"] if role(s) == wanted]
    return found


def holders(name: str, needle: str) -> set[str]:
    """The steps whose `env` mentions `needle`."""
    return {role(s) for s in job(name)["steps"] if needle in json.dumps(s.get("env", {}))}


def guard(start_id: str) -> str:
    ran = f"""contains(fromJSON('["success", "failure", "cancelled"]'), steps.{start_id}.outcome)"""
    return f"always() && {ran} && steps.{start_id}.outputs.refused != 'true'"


def fake(bin_: Path, name: str, code: str) -> None:
    """A Python fake for the command `name`."""
    bin_.mkdir(exist_ok=True)
    (bin_ / name).write_text(f"#!{sys.executable}\nimport json, sys\nargs = sys.argv[1:]\n{code}")
    (bin_ / name).chmod(0o755)


def run_step(tmp_path, name: str, wanted: str, rce_exit=0, rce_stdout="", context=None):
    """Run one step's script as GitHub does, its `env:` filled from `context` (expression -> value).
    Returns the process, its $GITHUB_OUTPUT as a dict, and each rce call's arguments."""
    calls = tmp_path / "calls"
    calls.write_text("")
    fake(tmp_path / "bin", "rce",
         f"open({str(calls)!r}, 'a').write(' '.join(args) + '\\n')\n"
         f"print({rce_stdout!r}, end='')\nsys.exit({rce_exit})\n")
    out = tmp_path / "output"
    out.write_text("")
    s = step(name, wanted)
    env = {**job(name).get("env", {}), **s.get("env", {})}
    env = {k: re.sub(r"\$\{\{ ([\w.]+) \}\}", lambda e: (context or {}).get(e[1], ""), str(v)) for k, v in env.items()}
    done = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", s["run"]],
        env={**os.environ, "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out), **env},
        cwd=tmp_path, capture_output=True, text=True,
    )
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines())
    return done, outputs, calls.read_text().splitlines()


# The workflows' shape.


@pytest.mark.parametrize("name", WORKFLOWS)
def test_every_action_is_pinned_to_a_commit_sha_with_its_version_in_a_comment(name):
    """A tag can be moved to other code; a SHA cannot, and these jobs hold the RCE token."""
    text = (REPO / ".github/workflows" / name).read_text()
    lines = re.findall(r"^\s*(?:- )?uses: (.*)$", text, re.M)
    assert len(lines) == sum("uses" in s for s in job(name)["steps"])
    for line in lines:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(\.\d+)*", line), line


@pytest.mark.parametrize("name", WORKFLOWS)
def test_steps_run_with_bash_so_pipefail_keeps_rces_exit_code(name):
    """Without `shell: bash`, the start's `| tee` hides exit 4 and a refused start passes."""
    assert job(name)["defaults"]["run"]["shell"] == "bash"


@pytest.mark.parametrize("name, secret, steps", [
    ("roku-test.yml", "RCE_TOKEN", {"start", "tests", "stop"}),
    ("roku-test.yml", "RCE_DEV_PASSWORD", {"tests"}),
    ("roku-test-pool.yml", "RCE_TOKEN", {"start", "tests", "stop"}),
    ("roku-test-pool.yml", "RCE_DEV_PASSWORDS", {"password"}),
])  # fmt: skip
def test_a_secret_reaches_only_the_steps_that_need_it(name, secret, steps):
    """Every other step (`npm ci`, a build, the upload, the summary) runs code that cannot read it."""
    assert holders(name, f"secrets.{secret} }}}}") == steps


@pytest.mark.parametrize("name", WORKFLOWS)
def test_secrets_appear_only_in_a_steps_env(name):
    in_env = sum(json.dumps(s.get("env", {})).count("secrets.") for s in job(name)["steps"])
    assert json.dumps(workflow(name)).count("secrets.") == in_env


def test_the_claimed_members_dev_password_reaches_only_the_test_step():
    password = step("roku-test-pool.yml", "password")
    wanted = "${{ steps.%s.outputs.password }}" % password["id"]
    assert holders("roku-test-pool.yml", "outputs.password") == {"tests"}
    assert step("roku-test-pool.yml", "tests")["env"]["RCE_DEV_PASSWORD"] == wanted


@pytest.mark.parametrize("name", WORKFLOWS)
def test_no_step_that_holds_a_secret_writes_to_github_env(name):
    for s in job(name)["steps"]:
        if re.search(r"secrets\.|outputs\.password", json.dumps(s.get("env", {}))):
            assert "GITHUB_ENV" not in s["run"], role(s)


def test_the_dev_password_is_masked_before_anything_else_is_written(tmp_path):
    """GitHub masks a secret's whole value, not a value taken out of it: unmasked, the Dev
    Password shows in any later output."""
    passwords = json.dumps({"375": "s3cret-375", "376": "other-376"})
    done, outputs, _ = run_step(tmp_path, "roku-test-pool.yml", "password",
                                context={"steps.start.outputs.id": "375", "secrets.RCE_DEV_PASSWORDS": passwords})
    assert done.returncode == 0, done.stderr
    assert done.stdout == "::add-mask::s3cret-375\n" and done.stderr == ""
    assert outputs == {"password": "s3cret-375"}


def test_a_member_missing_from_the_secret_fails_and_prints_no_password(tmp_path):
    passwords = json.dumps({"376": "other-376"})
    done, outputs, _ = run_step(tmp_path, "roku-test-pool.yml", "password",
                                context={"steps.start.outputs.id": "375", "secrets.RCE_DEV_PASSWORDS": passwords})
    assert done.returncode != 0 and outputs == {}
    assert "other-376" not in done.stdout + done.stderr


@pytest.mark.parametrize("name", WORKFLOWS)
def test_the_stop_runs_always_once_the_start_ran_unless_it_was_refused(tmp_path, name):
    """Without `always()` a failed or cancelled job leaves its Run billing; after a refused
    start (exit 4) the Run on the Cloud Device, if any, is someone else's."""
    start = step(name, "start")
    done, refused, _ = run_step(tmp_path, name, "start", rce_exit=4)
    assert done.returncode == 4 and refused == {"refused": "true"}
    assert step(name, "stop")["if"] == guard(start["id"])


@pytest.mark.parametrize("name", WORKFLOWS)
def test_the_stop_stops_only_the_run_its_start_recorded(tmp_path, name):
    """Without `--run` it stops a Run someone else started after this job's Run ended."""
    _, started, _ = run_step(tmp_path, name, "start", rce_stdout=STARTED)
    context = {f"steps.start.outputs.{k}": v for k, v in started.items()} | {"vars.RCE_DEVICE": "375"}
    done, _, calls = run_step(tmp_path, name, "stop", context=context)
    assert done.returncode == 0, done.stderr
    assert calls == ["device stop 375 --run 9000 --json"]


@pytest.mark.parametrize("name", WORKFLOWS)
@pytest.mark.parametrize("code", [1, 5])
def test_the_stop_does_nothing_without_a_run_id(tmp_path, name, code):
    _, started, _ = run_step(tmp_path, name, "start", rce_exit=code)
    context = {f"steps.start.outputs.{k}": v for k, v in started.items()} | {"vars.RCE_DEVICE": "375"}
    done, _, calls = run_step(tmp_path, name, "stop", context=context)
    assert done.returncode == 0 and calls == []


# The README's secret snippets, run with a fake rce and gh.


def snippet(section: str) -> str:
    readme = (REPO / "README.md").read_text()
    after = readme.split(f"\n### {section}\n", 1)[1]
    return re.search(r"```sh\n(.*?)```", after, re.S)[1]  # the section's first sh block


def run_snippet(tmp_path, section: str, devices: dict):
    """Run a README snippet with an rce that knows `devices` (Device Name -> [RCE id,
    Dev Snapshot id or None, Dev Password or None]) and a gh that records each call."""
    gh_calls = tmp_path / "gh_calls"
    fake(tmp_path / "bin", "rce", f"""
dev_id, snapshot, password = {devices!r}[args[2]]
if args[:2] == ["device", "show"] and "--dev-password" in args:
    if password is None:
        sys.exit(f"rce: no Dev Password is stored for {{args[2]}}.")
    print(f"ID:             {{dev_id}}")
    print(password, file=sys.stderr)  # as rce does: the password and a newline, on stderr
elif args[:2] == ["device", "show"]:
    print(json.dumps({{"id": dev_id}}))
elif args[:2] == ["snapshot", "list"]:
    dev = [{{"id": snapshot, "dev_snapshot": True}}] if snapshot else []
    print(json.dumps([{{"id": 1, "dev_snapshot": False}}] + dev))
""")
    fake(tmp_path / "bin", "gh", f"""
stdin = sys.stdin.read() if args[:2] == ["secret", "set"] else None
with open({str(gh_calls)!r}, "a") as calls:
    calls.write(json.dumps({{"argv": args, "stdin": stdin}}) + "\\n")
""")
    done = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", snippet(section)],
        env={**os.environ, "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}"},
        cwd=tmp_path, capture_output=True, text=True, input="",
    )
    calls = [json.loads(line) for line in gh_calls.read_text().splitlines()] if gh_calls.exists() else []
    return done, calls


def gh_set(calls: list, kind: str, name: str) -> dict:
    (found,) = [c for c in calls if c["argv"][:3] == [kind, "set", name]]
    return found


def test_the_dev_password_line_hands_gh_the_bare_password_and_prints_none(tmp_path):
    """`rce` ends the Dev Password with a newline and `gh secret set` stores its input as is:
    a secret with the newline fails the sideload with a 401."""
    done, calls = run_snippet(tmp_path, "Set it up for your own Cloud Device", {"player": [351, 2001, "s3cret"]})
    assert done.returncode == 0, done.stderr
    assert gh_set(calls, "secret", "RCE_DEV_PASSWORD")["stdin"] == "s3cret"
    assert "s3cret" not in done.stdout + done.stderr + json.dumps([c["argv"] for c in calls])


POOL = "Parallel jobs on a Pool"


def test_the_pool_snippet_sets_the_pool_and_its_dev_passwords_and_prints_none(tmp_path):
    done, calls = run_snippet(tmp_path, POOL, {"player": [375, 2001, "pw-player"], "tv": [376, 2002, "pw-tv"]})
    assert done.returncode == 0, done.stderr
    pool = gh_set(calls, "variable", "RCE_POOL")["argv"]
    assert json.loads(pool[pool.index("--body") + 1]) == {"375": 2001, "376": 2002}
    assert json.loads(gh_set(calls, "secret", "RCE_DEV_PASSWORDS")["stdin"]) == {"375": "pw-player", "376": "pw-tv"}
    assert "pw-" not in done.stdout + done.stderr + json.dumps([c["argv"] for c in calls])


@pytest.mark.parametrize("devices, message", [
    ({"player": [375, 2001, "pw-player"], "tv": [376, 2002, None]}, "no Dev Password from rce for tv"),
    ({"player": [375, 2001, "pw-player"], "tv": [376, None, "pw-tv"]}, "no Dev Snapshot found for tv"),
])  # fmt: skip
def test_the_pool_snippet_sets_nothing_when_a_member_is_not_set_up(tmp_path, devices, message):
    """Otherwise an error message is stored as a Dev Password, or a Pool lacks a member."""
    done, calls = run_snippet(tmp_path, POOL, devices)
    assert done.returncode != 0 and calls == []
    assert message in done.stderr and "pw-" not in done.stdout + done.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-p", "no:cacheprovider"] + sys.argv[1:]))
