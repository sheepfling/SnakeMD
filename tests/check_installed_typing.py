"""Build distributions and check a consumer against an isolated installed wheel.

Run with Python 3.10+ and the build, poetry-core, and mypy packages installed:
    python tests/check_installed_typing.py
"""

from __future__ import annotations

import os
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
        common = (
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-incremental",
            "--config-file",
            str(config),
            "--python-executable",
            str(python),
        )
        run(*common, "consumer.py", cwd=work, env=env)
        negative = subprocess.run(
            (*common, "negative.py"), cwd=work, env=env, text=True, capture_output=True
        )
        assert negative.returncode != 0, "negative consumer unexpectedly passed"
        assert "Incompatible types in assignment" in negative.stdout, negative.stdout
        assert 'Argument 1 to "Inline" has incompatible type' in negative.stdout, (
            negative.stdout
        )
        assert (
            'Argument 1 to "add_row" of "Table" has incompatible type'
            in negative.stdout
        ), negative.stdout
        print(
            "Wheel and sdist include py.typed; isolated wheel consumer checks passed."
        )


if __name__ == "__main__":
    main()
