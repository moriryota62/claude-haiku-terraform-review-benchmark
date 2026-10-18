# claude-haiku-terraform-review-benchmark

[Claude Haiku 5.5 の Terraform コーディング検証](https://github.com/moriryota62/claude-haiku-terraform-benchmark)の続きとして、**Terraformのコードレビュー**で Haiku 5.5 は Sonnet 5.5 の代替になりうるかを検証するベンチマーク。

Claude Haiku 4.5 / Claude Sonnet 5.5 / Claude Haiku 5.5 の3モデルに、あらかじめ不具合を仕込んだTerraformコードを同一のプロンプトでレビューさせ、検出率・誤検知などの客観的な指標で品質・生成時間・コストを比較する。LLMの出力は毎回ばらつくため、同じ手順を3回実行している。

## 結果

**[results/summary.md](results/summary.md)** に全集計をまとめている。3回平均の総合スコア(100点満点)は次のとおり。

| | Haiku 4.5 | Sonnet 5.5 | Haiku 5.5 |
| --- | --- | --- | --- |
| タスク1 (S3) | 81.4 | 98.3 | 99.4 |
| タスク2 (VPC+EC2) | 86.2 | 98.6 | 98.6 |
| タスク3 (ALB+ASG+RDS+IAM) | 67.6 | 99.6 | 100.0 |
| **全体** | **78.4** | **98.8** | **99.3** |
| 生成時間(3タスク×buggy/clean の合計、平均) | 約51秒 | 約99秒 | 約94秒 |
| コスト(同上、平均) | $0.060 | $0.193 | $0.013 |

要点:

- Haiku 5.5 と Sonnet 5.5 は、この問題セットでは**どちらもほぼ満点で差が付かなかった**(「同等」ではなく「この難易度では区別できない」)
- Haiku 4.5 は重大な不具合の見落としがあり、不具合を仕込んでいない対照コードへの誤検知が計11件(事実誤認を含む)あった。タスク3のbuggyでは壊れたJSONを1回返し、その回は検出0件扱い(12.5点)になった
- 対照コードへの誤検知は Sonnet 5.5 / Haiku 5.5 ともに3回とも0件
- コストは Haiku 5.5 が Sonnet 5.5 の約1/14〜1/15。生成時間は5%ほど短いだけで、Haiku 4.5 よりは遅い(出力が長い)

## 検証方法

1. 3段階の複雑さを持つAWS Terraformコードを用意する([tasks/](tasks/))
   - タスク1: S3バケット単体(シンプル)
   - タスク2: VPC + EC2 + セキュリティグループ(中程度)
   - タスク3: ALB + ASG + RDS + IAM(複雑)
2. 各タスクに2種類のコードを用意する。どちらも `terraform validate` を通る
   - `buggy.tf`: 既知の不具合(計26件: 6+7+13)を仕込んだコード。仕込み位置は `# @seed:ID` マーカーで管理し、レビュー対象には含めない
   - `clean.tf`: 不具合を仕込んでいない対照コード(誤検知の測定用)
3. Amazon Bedrock経由で3モデルに同一のレビュープロンプトを与える([scripts/run_review.py](scripts/run_review.py))。コーディング規約([rules.md](rules.md))もプロンプトに含め、出力はJSONで返させる。MCP等は使わずプロンプトのみ
4. 出力を正解データ([scripts/truth.py](scripts/truth.py))と照合して採点する([scripts/score.py](scripts/score.py))

| 指標 | 内容 | 配点 |
| --- | --- | --- |
| 検出率 | 仕込んだ不具合のうち検出できた割合(重大度で重み付け: critical 4 / high 3 / medium 2 / low 1) | 50 |
| 行番号 | 指摘の行番号が仕込み箇所の±3行以内か(リソース欠落型は該当リソース範囲内) | 10 |
| 修正案 | 修正案が妥当な内容を含むか | 15 |
| 重大度 | 想定の重大度との差が1段階以内か | 5 |
| 出力形式 | JSONとして解釈できるか | 5 |
| 精度 | clean版で medium 以上の誤検知がどれだけ少ないか(3件以上で0点) | 15 |

clean版への指摘のうち、コードの設計上の弱点としてもっともな観察(単一AZ構成、HTTPのみのALB、ログ未設定など)は、誤検知にも加点にも数えない「中立」として扱う(`known_observations`)。

## 使用モデル (Amazon Bedrock, 推論プロファイル, us-east-1)

| 表記 | モデルID |
| --- | --- |
| Haiku 4.5 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Sonnet 5.5 | `us.anthropic.claude-sonnet-5-5` |
| Haiku 5.5 | `us.anthropic.claude-haiku-5-5` |

コストは Haiku 4.5 = 入力$1.10/出力$5.50、Sonnet 5.5 = 入力$2.20/出力$11.00、Haiku 5.5 = 入力$0.11/出力$0.55(いずれも100万トークンあたり)で計算している。公式の最新料金は未確認。

## 再現方法

```bash
# 1. 依存: terraform, python3, boto3(Bedrockの認証情報が必要)

# 2. レビュー対象の生成(@seed マーカーを除去し、仕込み位置を seed_lines.json に出力)
python3 scripts/build_targets.py $PWD

# 3. レビューの実行(3モデル x 3タスク x buggy/clean x 3回 = 54リクエスト)
python3 scripts/run_review.py $PWD --runs 3 --workers 3

# 4. 採点とレポート生成
python3 scripts/score.py $PWD
```

モデルの生出力は [results/raw/\<model\>/\<task\>/\<buggy|clean\>/run\<n\>.json](results/raw/) に、採点結果は [results/scores.json](results/scores.json) と [results/summary.md](results/summary.md) に出力される。

タスク3の `buggy.tf` は、`clean.tf` に不具合だけを文字列置換で仕込んだもの([scripts/make_buggy_task3.py](scripts/make_buggy_task3.py))。

## 注意点・限界

- 仕込んだ不具合が教科書的で、Sonnet 5.5 と Haiku 5.5 の優劣は判定できていない
- 誤検知の判定は「想定外 かつ 中立リストに無い medium 以上」というルールベース。buggy版での「想定外の指摘」(単一NAT、HTTPのみのALB、パブリックIP未付与など)は本物の追加指摘の可能性が高いが未判定で、スコアには入れていない
- 試行は各3回のみ。対象は1ファイルのTerraformのみ
- 正解データは作者が作成しており、照合はキーワードと位置によるため、表現次第で取りこぼしや過剰一致があり得る

## ディレクトリ構成

```
tasks/      レビュー対象のTerraformコード(buggy.tf / clean.tf。@seed マーカー付き)
targets/    マーカーを除去したレビュー対象と、仕込み位置(seed_lines.json)
rules.md    プロンプトに含めるコーディング規約
scripts/    対象生成・レビュー実行・採点スクリプトと正解データ(truth.py)
results/    モデルの生出力(raw/)、採点結果(scores.json)、集計(summary.md)
```
