"""Railway 명령을 모의 CLI로 대체하여 변수 동기화의 의미만 검증한다."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_absent_optional_secrets_are_explicitly_cleared_or_defaulted(tmp_path):
    workflow = (ROOT / ".github/workflows/cd.yml").read_text()
    start = workflow.index(
        '          SERVICE="${SERVICE:-ai-chatbot-service}"',
        workflow.index("- name: Secrets → Railway 변수 동기화"),
    )
    end = workflow.index("\n      - name: 배포 (railway up)", start)
    script = "\n".join(line[10:] for line in workflow[start:end].splitlines())
    binary = tmp_path / "bin"
    binary.mkdir()
    recorder = binary / "railway"
    recorder.write_text("#!" + sys.executable + """
import json,os,sys
with open(os.environ['TEST_RECORD'], 'a') as out:
    out.write(json.dumps(sys.argv[1:])+'\\n')
""")
    recorder.chmod(0o700)
    env = dict(
        os.environ,
        PATH=str(binary) + os.pathsep + os.environ["PATH"],
        TEST_RECORD=str(tmp_path / "record.jsonl"),
    )
    for key in [
        "AI_API_KEY",
        "AI_BASE_URL",
        "AI_MODEL",
        "AI_TIMEOUT_SEC",
        "AI_MAX_RETRIES",
        "CONTEXT_TURNS",
        "MAX_QUESTION_LENGTH",
        "DATABASE_URL",
        "SERVICE",
        "RAIL_ENV",
    ]:
        env[key] = ""
    env["SESSION_SECRET"] = "local-synthetic-not-a-production-secret"
    run = subprocess.run(["bash", "-e", "-c", script], env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    commands = [json.loads(x) for x in (tmp_path / "record.jsonl").read_text().splitlines()]
    values = dict(command[2].split("=", 1) for command in commands)
    assert values["AI_API_KEY"] == ""
    assert values["DEBUG"] == "false"
    assert values["AI_TIMEOUT_SEC"] == "45"
    assert values["AI_MAX_RETRIES"] == "1"
    assert values["MAX_QUESTION_LENGTH"] == "1000"
    assert values["CONTEXT_TURNS"] == "5"
    assert values["DATABASE_URL"] == "sqlite:////data/app.db"
    assert values["CHAT_RATE_PER_MIN"] == "10"
    assert values["LOGIN_MAX_FAILS"] == "5"
    assert values["LOGIN_LOCKOUT_SEC"] == "900"
    assert values["SESSION_MAX_AGE_HOURS"] == "24"
    assert values["DOCS_ENABLED"] == "false"
    assert all("--skip-deploys" in command for command in commands)
