"""Build distributions and check a consumer against an isolated installed wheel.

Run with Python 3.10+ and the tools in tests/typing/requirements.txt installed:
    python tests/check_installed_typing.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, check=True)


def main() -> None:
    env = os.environ.copy()
    for name in ("PYTHONPATH", "MYPYPATH", "PYTHONHOME"):
        env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="snakemd-typing-") as temp:
        work = Path(temp)
        dist = work / "dist"
        run(
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
            cwd=ROOT,
            env=env,
        )
        (wheel,) = dist.glob("*.whl")
        (sdist,) = dist.glob("*.tar.gz")
        with zipfile.ZipFile(wheel) as archive:
            assert "snakemd/py.typed" in archive.namelist(), "wheel lacks py.typed"
        with tarfile.open(sdist) as archive:
            assert any(
                name.endswith("/snakemd/py.typed") for name in archive.getnames()
            ), "sdist lacks py.typed"

        venv = work / "venv"
        run(sys.executable, "-m", "venv", str(venv), cwd=work, env=env)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheel),
            cwd=work,
            env=env,
        )
        run(
            str(python),
            "-c",
            "import importlib.metadata as m, snakemd; "
            "assert 'site-packages' in snakemd.__file__; "
            "assert not any(d.metadata['Name'].lower().replace('_', '-') == 'snakemd-stubs' for d in m.distributions())",
            cwd=work,
            env=env,
        )

        for name in ("consumer.py", "negative.py"):
            shutil.copy(ROOT / "tests" / "typing" / name, work / name)
        config = work / "mypy.ini"
        config.write_text("[mypy]\n", encoding="utf-8")
        # Each checker resolves imports from the clean wheel-only environment,
        # while its own tools live outside that environment.
        checkers = {
            "mypy": (
                sys.executable, "-m", "mypy", "--strict", "--no-incremental",
                "--config-file", str(config), "--python-executable", str(python),
            ),
            "pyright": (
                sys.executable, "-m", "pyright", "--outputjson",
                "--pythonpath", str(python),
            ),
            "ty": (
                sys.executable, "-m", "ty", "check", "--output-format", "concise",
                "--color", "never", "--error-on-warning", "--python", str(python),
            ),
        }
        negative_lines = [
            line for line, text in enumerate((work / "negative.py").read_text().splitlines(), 1)
            if 'link: str =' in text or 'Inline(123)' in text or '.add_row(' in text
        ]
        assert len(negative_lines) == 3, "negative fixture must exercise three errors"
        for name, command in checkers.items():
            run(*command, "consumer.py", cwd=work, env=env)
            negative = subprocess.run(
                (*command, "negative.py"), cwd=work, env=env,
                text=True, capture_output=True,
            )
            assert negative.returncode != 0, f"{name}: negative consumer unexpectedly passed"
            if name == "pyright":
                result = json.loads(negative.stdout)
                errors = {
                    (item["range"]["start"]["line"] + 1, item.get("rule"))
                    for item in result["generalDiagnostics"]
                    if item["severity"] == "error"
                }
                rules = ("reportAssignmentType", "reportArgumentType", "reportArgumentType")
            elif name == "mypy":
                errors = {
                    (int(line), code) for line, code in re.findall(
                        r"negative\.py:(\d+): .*?\[([a-z-]+)\]", negative.stdout
                    )
                }
                rules = ("assignment", "arg-type", "arg-type")
            else:
                errors = {
                    (int(line), code) for line, code in re.findall(
                        r"negative\.py:(\d+):\d+: error\[([a-z-]+)\]", negative.stdout
                    )
                }
                rules = ("invalid-assignment", "invalid-argument-type", "invalid-argument-type")
            expected = set(zip(negative_lines, rules))
            assert expected <= errors, (
                f"{name}: missing expected errors {expected - errors}\n"
                f"stdout: {negative.stdout}\nstderr: {negative.stderr}"
            )
            print(f"{name}: installed-wheel consumer checks passed")
        print("Wheel and sdist include py.typed.")


if __name__ == "__main__":
    main()
