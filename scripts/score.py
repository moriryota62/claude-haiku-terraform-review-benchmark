"""results/raw を採点して results/scores.json と results/summary.md を出力する。

配点(タスクごと100点):
  検出率(重大度重み付き) 50 / 行番号の正確さ 10 / 修正案の妥当性 15 / 重大度の妥当性 5
  出力形式(JSONとして解釈可能) 5 / 精度(clean版での誤検知が少ない) 15
"""
import json, pathlib, re, statistics, sys

root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
from truth import TASKS, SEVERITY_WEIGHT

MODELS = ["haiku45", "sonnet55", "haiku55"]
LABEL = {"haiku45": "Haiku 4.5", "sonnet55": "Sonnet 5.5", "haiku55": "Haiku 5.5"}
PRICE = {"haiku45": (1.10, 5.50), "sonnet55": (2.20, 11.00), "haiku55": (0.11, 0.55)}  # USD / 1M tokens (記事と同じ前提)
RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
LINE_TOL = 3


def parse(text):
    m = re.search(r"```json\s*(.*?)```", text, re.S)
    cand = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    try:
        d = json.loads(cand)
        fs = d["findings"]
        assert isinstance(fs, list) and all(isinstance(f, dict) for f in fs)
        return fs, True
    except Exception:
        return [], False


def ftext(f):
    return " ".join(str(f.get(k) or "") for k in ("resource", "title", "description"))


def fline(f):
    try:
        return int(f.get("line"))
    except (TypeError, ValueError):
        return None


def in_blocks(line, blocks):
    return line is not None and any(a <= line <= b for a, b in blocks)


def near(line, lines):
    return line is not None and any(abs(line - l) <= LINE_TOL for l in lines)


def matches(seed, info, f):
    text = ftext(f)
    if not all(any(re.search(p, text, re.I) for p in g) for g in seed["text_groups"]):
        return False
    head = f"{f.get('resource') or ''} {f.get('title') or ''}"
    return in_blocks(fline(f), info["blocks"]) or bool(re.search(seed["anchor"], head, re.I))


def score_pair(task, buggy, clean):
    spec = TASKS[task]
    info = json.loads((root / "targets" / task / "seed_lines.json").read_text())
    bf, b_ok = parse(buggy["text"])
    cf, c_ok = parse(clean["text"])
    seeds = spec["seeds"]
    wsum = sum(SEVERITY_WEIGHT[s["severity"]] for s in seeds.values())
    found, loc_ok, fix_ok, sev_ok, used = {}, 0, 0, 0, set()
    for sid, s in seeds.items():
        cands = [(i, f) for i, f in enumerate(bf) if matches(s, info[sid], f)]
        if not cands:
            continue
        precise = [c for c in cands if near(fline(c[1]), info[sid]["lines"])
                   or (s.get("missing") and in_blocks(fline(c[1]), info[sid]["blocks"]))]
        i, f = (precise or cands)[0]
        found[sid] = True
        used.update(i for i, _ in cands)
        loc_ok += bool(precise)
        fix_ok += bool(re.search(s["fix_any"], str(f.get("fix") or ""), re.I))
        sev = RANK.get(str(f.get("severity")).lower())
        sev_ok += sev is not None and abs(sev - RANK[s["severity"]]) <= 1
    n = len(seeds)
    recall_w = sum(SEVERITY_WEIGHT[seeds[s]["severity"]] for s in found) / wsum
    extras = [f for i, f in enumerate(bf) if i not in used]
    fps = [f for f in cf
           if str(f.get("severity")).lower() in ("critical", "high", "medium")
           and not re.search(spec["known_observations"], ftext(f), re.I)]
    fmt = (b_ok + c_ok) / 2
    parts = {
        "recall": 50 * recall_w,
        "location": 10 * loc_ok / n,
        "fix": 15 * fix_ok / n,
        "severity": 5 * sev_ok / n,
        "format": 5 * fmt,
        "precision": 15 * max(0.0, 1 - len(fps) / 3),
    }
    return {
        "total": round(sum(parts.values()), 1),
        "parts": {k: round(v, 1) for k, v in parts.items()},
        "found": sorted(found), "missed": sorted(set(seeds) - set(found)),
        "n_findings_buggy": len(bf), "n_extras_buggy": len(extras),
        "extras": [{k: f.get(k) for k in ("severity", "resource", "line", "title")} for f in extras],
        "n_findings_clean": len(cf), "false_positives": [{k: f.get(k) for k in ("severity", "resource", "line", "title")} for f in fps],
        "format_ok": {"buggy": b_ok, "clean": c_ok},
        "seconds": round(buggy["seconds"] + clean["seconds"], 1),
        "in_tokens": buggy["usage"]["inputTokens"] + clean["usage"]["inputTokens"],
        "out_tokens": buggy["usage"]["outputTokens"] + clean["usage"]["outputTokens"],
        "truncated": "max_tokens" in (buggy.get("stop"), clean.get("stop")),
    }


def load(m, t, v, n):
    p = root / "results" / "raw" / m / t / v / f"run{n}.json"
    return json.loads(p.read_text()) if p.exists() else None


def cost(m, r):
    pi, po = PRICE[m]
    return (r["in_tokens"] * pi + r["out_tokens"] * po) / 1e6


def main():
    S = {m: {t: {} for t in TASKS} for m in MODELS}
    for m in MODELS:
        for t in TASKS:
            for n in (1, 2, 3):
                b, c = load(m, t, "buggy", n), load(m, t, "clean", n)
                if b and c:
                    S[m][t][n] = score_pair(t, b, c)
    (root / "results" / "scores.json").write_text(json.dumps(S, ensure_ascii=False, indent=2))

    L = []
    w = L.append
    runs = (1, 2, 3)
    mean = statistics.mean

    w("## 総合スコア\n")
    w("| タスク | 回 | " + " | ".join(LABEL[m] for m in MODELS) + " |")
    w("| --- | --- | " + " | ".join("---" for _ in MODELS) + " |")
    for t in TASKS:
        for n in runs:
            w(f"| {TASKS[t]['title'] if n == 1 else ''} | {n}回目 | " + " | ".join(
                str(S[m][t][n]["total"]) if n in S[m][t] else "-" for m in MODELS) + " |")
    avg = {m: {n: mean(S[m][t][n]["total"] for t in TASKS if n in S[m][t]) for n in runs if any(n in S[m][t] for t in TASKS)} for m in MODELS}
    for n in runs:
        w(f"| **平均** | **{n}回目** | " + " | ".join(f"**{avg[m][n]:.1f}**" for m in MODELS) + " |")
    w("| | **3回の平均** | " + " | ".join(f"**{mean(avg[m].values()):.1f}**" for m in MODELS) + " |")

    w("\n## 指標別の内訳(3回平均)\n")
    names = {"recall": "検出率 (50)", "location": "行番号 (10)", "fix": "修正案 (15)", "severity": "重大度 (5)", "format": "形式 (5)", "precision": "精度/誤検知なし (15)"}
    for t in TASKS:
        w(f"### {TASKS[t]['title']}\n")
        w("| 指標 | " + " | ".join(LABEL[m] for m in MODELS) + " |")
        w("| --- | " + " | ".join("---" for _ in MODELS) + " |")
        for k, nm in names.items():
            w(f"| {nm} | " + " | ".join(f"{mean(S[m][t][n]['parts'][k] for n in S[m][t]):.1f}" for m in MODELS) + " |")
        w("| **合計** | " + " | ".join(f"**{mean(S[m][t][n]['total'] for n in S[m][t]):.1f}**" for m in MODELS) + " |")
        w("")

    w("## 不具合ごとの検出回数(3回中)\n")
    for t in TASKS:
        w(f"### {TASKS[t]['title']}\n")
        w("| 不具合 | 想定重大度 | " + " | ".join(LABEL[m] for m in MODELS) + " |")
        w("| --- | --- | " + " | ".join("---" for _ in MODELS) + " |")
        for sid, s in TASKS[t]["seeds"].items():
            w(f"| {sid} | {s['severity']} | " + " | ".join(
                f"{sum(sid in S[m][t][n]['found'] for n in S[m][t])}/{len(S[m][t])}" for m in MODELS) + " |")
        w("")

    w("## 誤検知 (clean版で medium 以上の指摘が出た数 / 3回合計)\n")
    w("| タスク | " + " | ".join(LABEL[m] for m in MODELS) + " |")
    w("| --- | " + " | ".join("---" for _ in MODELS) + " |")
    for t in TASKS:
        w(f"| {TASKS[t]['title']} | " + " | ".join(str(sum(len(S[m][t][n]["false_positives"]) for n in S[m][t])) for m in MODELS) + " |")
    w("\n## buggy版での「想定外の指摘」数 (3回合計。要目視確認: 本物の追加指摘か誤検知かは未判定)\n")
    w("| タスク | " + " | ".join(LABEL[m] for m in MODELS) + " |")
    w("| --- | " + " | ".join("---" for _ in MODELS) + " |")
    for t in TASKS:
        w(f"| {TASKS[t]['title']} | " + " | ".join(str(sum(S[m][t][n]["n_extras_buggy"] for n in S[m][t])) for m in MODELS) + " |")

    w("\n## 生成時間とコスト (buggy+clean の2回分 / タスク)\n")
    w("| モデル | 回 | 合計生成時間(秒) | 入力tok | 出力tok | コスト(USD) |")
    w("| --- | --- | --- | --- | --- | --- |")
    for m in MODELS:
        for n in runs:
            rs = [S[m][t][n] for t in TASKS if n in S[m][t]]
            if rs:
                w(f"| {LABEL[m]} | {n}回目 | {sum(r['seconds'] for r in rs):.1f} | {sum(r['in_tokens'] for r in rs)} | "
                  f"{sum(r['out_tokens'] for r in rs)} | {sum(cost(m, r) for r in rs):.4f} |")
    trunc = [(m, t, n) for m in MODELS for t in TASKS for n, r in S[m][t].items() if r["truncated"]]
    w(f"\n出力が max_tokens で打ち切られたラン: {trunc or 'なし'}")

    (root / "results" / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


main()
