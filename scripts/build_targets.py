"""tasks/*/{clean,buggy}.tf から @seed マーカーを除去したレビュー対象を targets/ に出力し、
seed ごとの行番号・所属ブロック範囲を targets/<task>/seed_lines.json に保存する。
"""
import json, pathlib, re, subprocess, sys

root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
from truth import TASKS

MARK = re.compile(r"\s*#\s*(@seed:\S+(?:\s+@seed:\S+)*)\s*$")
TOP = re.compile(r"^(resource|variable|output|data|terraform|provider|locals)\b")

for task in TASKS:
    out = root / "targets" / task
    out.mkdir(parents=True, exist_ok=True)
    for variant in ("clean", "buggy"):
        lines = (root / "tasks" / task / f"{variant}.tf").read_text().splitlines()
        stripped, seeds = [], {}
        for i, line in enumerate(lines, 1):
            m = MARK.search(line)
            if m:
                for sid in re.findall(r"@seed:(\S+)", m.group(1)):
                    seeds.setdefault(sid, []).append(i)
                line = MARK.sub("", line)
            stripped.append(line)
        (out / f"{variant}.tf").write_text("\n".join(stripped) + "\n")
        subprocess.run(["terraform", "fmt", str(out / f"{variant}.tf")], check=True, capture_output=True)
        final = (out / f"{variant}.tf").read_text().splitlines()
        assert len(final) == len(stripped), "terraform fmt changed line count"
        if variant == "clean":
            assert not seeds, "clean に seed が含まれている"
            continue
        blocks, start = [], None
        for i, line in enumerate(final, 1):
            if TOP.match(line):
                start = i
            if line == "}" and start:
                blocks.append((start, i)); start = None
        info = {}
        for sid, ls in seeds.items():
            spans = sorted({b for l in ls for b in blocks if b[0] <= l <= b[1]})
            info[sid] = {"lines": ls, "blocks": spans}
        expected = set(TASKS[task]["seeds"])
        assert set(info) == expected, f"{task}: seed 不一致 {set(info) ^ expected}"
        (out / "seed_lines.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        print(task, "seeds:", len(info))
