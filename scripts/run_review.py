"""3モデル x 3タスク x (buggy|clean) x N回 のレビューを Bedrock Converse API で実行し results/raw に保存する。

使い方: python3 scripts/run_review.py <project_root> [--runs 3] [--models haiku45,sonnet55,haiku55]
"""
import argparse, json, pathlib, time, concurrent.futures as cf
import boto3
from botocore.config import Config

MODELS = {
    "haiku45": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "sonnet55": "us.anthropic.claude-sonnet-5-5",
    "haiku55": "us.anthropic.claude-haiku-5-5",
}
TASKS = ["task1_s3", "task2_vpc_ec2", "task3_alb_asg_rds"]

PROMPT = """あなたはTerraformのコードレビュアーです。以下のTerraformコード(AWS)をレビューし、問題点を指摘してください。

## レビュー観点
- セキュリティ(公開範囲、暗号化、認証情報の扱い、IAM権限など)
- 信頼性・可用性(バックアップ、冗長化、ヘルスチェックなど)
- 設定の正しさ(意図と実装の食い違い、ベストプラクティス違反)
- コーディング規約への準拠

{rules}

## ルール
- 実在する問題だけを指摘すること。問題がなければ findings は空配列でよい。
- 推測や好みによる指摘、コードに存在しない記述についての指摘は避けること。
- 各指摘には、コード中の該当行番号(下記の行番号に対応)とリソース名を付けること。リソース自体が欠落している場合は、関連するリソースの行番号を指定すること。
- severity は critical / high / medium / low のいずれか。
- category は security / reliability / correctness / convention / other のいずれか。
- 出力は次のJSONのみ。前後に説明文を付けないこと。

```json
{{
  "findings": [
    {{
      "severity": "high",
      "category": "security",
      "resource": "aws_xxx.yyy",
      "line": 12,
      "title": "短い見出し",
      "description": "何が問題で、なぜ問題か",
      "fix": "具体的な修正案"
    }}
  ]
}}
```

## レビュー対象コード(main.tf)
```hcl
{code}
```
"""


def numbered(path: pathlib.Path) -> str:
    return "\n".join(f"{i:4d}| {l}" for i, l in enumerate(path.read_text().splitlines(), 1))


def call(client, model_id, prompt):
    for attempt in range(6):
        try:
            t0 = time.time()
            r = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 8192},
            )
            dt = time.time() - t0
            text = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
            return {"text": text, "seconds": round(dt, 2), "usage": r["usage"], "stop": r.get("stopReason")}
        except Exception as e:  # スロットリング等はバックオフして再試行
            if attempt == 5:
                return {"error": str(e)}
            time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    rules = (root / "rules.md").read_text()
    client = boto3.client("bedrock-runtime", region_name="us-east-1",
                          config=Config(read_timeout=600, retries={"max_attempts": 0}))

    jobs = []
    for m in a.models.split(","):
        for t in TASKS:
            for v in ("buggy", "clean"):
                for n in range(1, a.runs + 1):
                    out = root / "results" / "raw" / m / t / v / f"run{n}.json"
                    if out.exists():
                        continue
                    jobs.append((m, t, v, n, out))
    print(f"{len(jobs)} jobs")

    def work(j):
        m, t, v, n, out = j
        prompt = PROMPT.format(rules=rules, code=numbered(root / "targets" / t / f"{v}.tf"))
        res = call(client, MODELS[m], prompt)
        res.update(model=m, model_id=MODELS[m], task=t, variant=v, run=n)
        if "error" in res:
            print("ERR", m, t, v, n, res["error"][:120])
            return
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
        print("done", m, t, v, n, res["seconds"], "s")

    with cf.ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(work, jobs))


if __name__ == "__main__":
    main()
