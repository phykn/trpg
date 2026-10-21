import argparse
import importlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common

PY = str(common.REPO / ".venv" / "bin" / "python")
SIDES = {
    # The files a side's tests read, the suite, where it runs, and how a failing test is named.
    "server": {"files": ("server/", "scenarios/", "pyproject.toml"),
               "cmd": [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], "cwd": ".",
               "failed": re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)},
    "client": {"files": ("client/",),
               "cmd": ["npx", "jest", "--ci", "--bail", "--runInBand", "--silent"], "cwd": "client",
               "failed": re.compile(r"^\s*● (.+)$", re.MULTILINE)},
}


def tracked(prefixes: tuple[str, ...]) -> list[str]:
    """The working tree as it is, uncommitted tests included, without ignored files."""
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=common.REPO,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    return [f for f in out if f.startswith(prefixes) and (common.REPO / f).is_file()]


def copy_tree(side: str, dest: Path) -> Path:
    for f in tracked(SIDES[side]["files"]):
        (dest / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(common.REPO / f, dest / f)
    if side == "client":
        (dest / "client" / "node_modules").symlink_to(common.REPO / "client" / "node_modules")
    return dest


def suite(side: str, root: Path, timeout: int) -> tuple[str, str]:
    """('pass' | 'fail' | 'timeout', the output)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "CI": "1"}
    try:
        p = subprocess.run(SIDES[side]["cmd"], cwd=root / SIDES[side]["cwd"], env=env,
                           capture_output=True, text=True, timeout=timeout, check=False)
        return ("pass" if p.returncode == 0 else "fail"), p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return "timeout", out


def mutate(side: str, root: Path, m: tuple, timeout: int) -> dict:
    mid, f, old, new, defect = m
    row = {"id": mid, "file": f, "defect": defect}
    path = root / f
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if text.count(old) != 1:
        # The code moved on under the catalog: the mutant must be rewritten, not silently skipped.
        return row | {"status": "stale", "by": f"{text.count(old)} matches"}
    row["file"] = f"{f}:{text[:text.index(old)].count(chr(10)) + 1}"
    path.write_text(text.replace(old, new), encoding="utf-8")
    t0 = time.monotonic()
    try:
        result, out = suite(side, root, timeout)
    finally:
        path.write_text(text, encoding="utf-8")
    found = SIDES[side]["failed"].search(out)
    status = {"pass": "survived", "fail": "killed", "timeout": "killed"}[result]
    by = "timeout (a hang, not an assertion)" if result == "timeout" else found[1] if found else None
    return row | {"status": status, "by": by, "secs": round(time.monotonic() - t0, 1)}


def report(side: str, rows: list[dict], equivalent: dict) -> tuple[str, int]:
    gaps = [r for r in rows if r["status"] == "survived" and r["id"] not in equivalent]
    stale = [r for r in rows if r["status"] == "stale"]
    killed = sum(r["status"] == "killed" for r in rows)
    summary = f"{killed} of {killed + len(gaps)} killed, {len(stale)} stale (equivalent survivors not counted)."
    lines = [f"# Mutation check: {side}", "", summary, "",
             "| id | where | defect | result | caught by |", "|---|---|---|---|---|"]
    for r in rows:
        note = f"equivalent: {equivalent[r['id']]}" if r["id"] in equivalent and r["status"] == "survived" else ""
        lines.append(f"| {r['id']} | {r['file']} | {r['defect']} | {r['status']} | {r.get('by') or note or '-'} |")
    return "\n".join(lines) + "\n", len(gaps) + len(stale)


def main():
    ap = argparse.ArgumentParser(description="Plant one defect at a time in a copy of the tree and check a test fails.")
    ap.add_argument("side", choices=sorted(SIDES))
    ap.add_argument("ids", nargs="*", help="only these mutants")
    ap.add_argument("--out", help="run name under qa_test/runs (default mutate-<side>)")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=180, help="seconds per mutant before it counts as a hang")
    a = ap.parse_args()
    catalog = importlib.import_module(a.side)
    todo = [m for m in catalog.MUTANTS if not a.ids or m[0] in a.ids]
    if a.ids and len(todo) != len(set(a.ids)):
        raise SystemExit(f"unknown ids: {sorted(set(a.ids) - {m[0] for m in todo})}")
    out_dir = common.RUNS / (a.out or f"mutate-{a.side}")
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"mutate-{a.side}-") as tmp:
        roots = [copy_tree(a.side, Path(tmp) / f"w{i}") for i in range(max(1, min(a.jobs, len(todo))))]
        result, out = suite(a.side, roots[0], a.timeout)
        if result != "pass":
            raise SystemExit(f"the unmutated suite does not pass:\n{out[-3000:]}")
        work, rows, lock = queue.Queue(), [], threading.Lock()
        for m in todo:
            work.put(m)

        def worker(root: Path):
            while True:
                try:
                    m = work.get_nowait()
                except queue.Empty:
                    return
                row = mutate(a.side, root, m, a.timeout)
                with lock:
                    rows.append(row)
                    print(f"{row['id']:4} {row['status']:8} {row.get('by') or ''}", flush=True)

        threads = [threading.Thread(target=worker, args=(r,)) for r in roots]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    order = {m[0]: i for i, m in enumerate(todo)}
    rows.sort(key=lambda r: order[r["id"]])
    with (out_dir / f"{a.side}.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    text, bad = report(a.side, rows, catalog.EQUIVALENT)
    (out_dir / f"{a.side}.md").write_text(text, encoding="utf-8")
    print("\n" + text.split("\n\n")[1] + f"\n→ {out_dir / (a.side + '.md')}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
