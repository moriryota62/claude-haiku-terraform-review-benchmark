"""正解データ: buggy.tf に仕込んだ不具合(seed)の定義。

text_groups : 各グループ(正規表現のリスト)のうち、いずれかが指摘文に含まれる、をすべてのグループで満たすこと
anchor      : 指摘の resource/title に含まれていれば、行番号が無くても位置が合っているとみなす
fix_any     : 修正案(fix)に含まれていれば「妥当な修正案」とみなす正規表現
"""

SEVERITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}

RULE_NAME = r"命名|リソース名|naming|repeat|繰り返|重複|規約|convention|rule ?2"
RULE_DESC = r"description|説明"

TASKS = {
    "task1_s3": {
        "title": "タスク1: シンプル (S3)",
        "seeds": {
            "S1_PUBLIC_POLICY": dict(
                severity="critical", anchor=r"public_read|principals|aws_s3_bucket_policy",
                text_groups=[[r"public|パブリック|公開|principal|anonymous|誰でも|全世界|\"\*\""]],
                fix_any=r"principal|限定|削除|remove|restrict|cloudfront|oac|特定|delete"),
            "S1_PAB_WEAK": dict(
                severity="high", anchor=r"public_access_block",
                text_groups=[[r"block_public_policy|restrict_public_buckets|public_access_block|パブリックアクセスブロック"]],
                fix_any=r"true"),
            "S1_VERSIONING_SUSPENDED": dict(
                severity="medium", anchor=r"versioning",
                text_groups=[[r"version|バージョニング|suspended"]],
                fix_any=r"enabled|有効"),
            "S1_NAME_REPEAT": dict(
                severity="low", anchor=r"s3_bucket",
                text_groups=[[RULE_NAME]],
                fix_any=r"main|rename|変更|リネーム|用途"),
            "S1_VAR_NO_META": dict(
                severity="low", anchor=r"tags|variable",
                text_groups=[[r"tags|variable|変数"], [r"type|description|説明|型"]],
                fix_any=r"description|type|説明|型"),
            "S1_OUTPUT_NO_DESC": dict(
                severity="low", anchor=r"bucket_arn|output",
                text_groups=[[r"output|出力"], [RULE_DESC]],
                fix_any=r"description|説明"),
        },
        "known_observations": r"lifecycle|ライフサイクル|logging|ログ|kms|cmk|replication|レプリケーション|notification|通知|mfa|object lock|access log|アクセスログ|タグ|tag",
    },
    "task2_vpc_ec2": {
        "title": "タスク2: 中程度 (VPC+EC2)",
        "seeds": {
            "S2_SSH_OPEN": dict(
                severity="high", anchor=r"allowed_ssh_cidr|security_group",
                text_groups=[[r"ssh|22|allowed_ssh_cidr"], [r"0\.0\.0\.0/0|open|anywhere|全|公開|any|インターネット"]],
                fix_any=r"限定|restrict|default.*(削除|なし|remove)|削除|trusted|特定|vpn|bastion|ssm|session manager|/32"),
            "S2_IMDSV1": dict(
                severity="medium", anchor=r"metadata_options|aws_instance",
                text_groups=[[r"imds|metadata|http_tokens|メタデータ"]],
                fix_any=r"required"),
            "S2_EBS_UNENCRYPTED": dict(
                severity="medium", anchor=r"root_block_device|aws_instance|ebs",
                text_groups=[[r"encrypt|暗号"]],
                fix_any=r"true|有効"),
            "S2_HARDCODED_AMI": dict(
                severity="medium", anchor=r"aws_instance|ami",
                text_groups=[[r"(?<![A-Za-z0-9_])ami(?![A-Za-z0-9_])"], [r"hard|ハード|固定|直接|ssm|data|latest|最新|ベタ|リージョン|region"]],
                fix_any=r"ssm|data|aws_ami|latest|最新|変数|variable"),
            "S2_COUNT_LOOP": dict(
                severity="low", anchor=r"aws_subnet|route_table_association|public",
                text_groups=[[r"count"]],
                fix_any=r"for_each"),
            "S2_NAME_REPEAT": dict(
                severity="low", anchor=r"aws_vpc",
                text_groups=[[RULE_NAME]],
                fix_any=r"main|rename|変更|リネーム|用途"),
            "S2_OUTPUT_NO_DESC": dict(
                severity="low", anchor=r"instance_id|output",
                text_groups=[[r"output|出力"], [RULE_DESC]],
                fix_any=r"description|説明"),
        },
        "known_observations": r"egress|アウトバウンド|flow ?log|フローログ|monitoring|監視|ebs.?optimized|key.?pair|キーペア|キー|ssm|session manager|public ip|パブリック ?ip|ipv6|nacl|default security group|デフォルト.*セキュリティグループ|kms|cmk|タグ|tag|cidr.*(narrow|限定)|map_public_ip|elastic ip|eip|単一.?az|シングル.?az|single.?az|1つの.?az|単一のサブネット|単一インスタンス|冗長性|iam ?ロール|iam ?role|instance profile|associate_public_ip|パブリック ?ip|ユーザーデータ|user.?data",
    },
    "task3_alb_asg_rds": {
        "title": "タスク3: 複雑 (ALB+ASG+RDS+IAM)",
        "seeds": {
            "S3_RDS_PUBLIC": dict(
                severity="critical", anchor=r"aws_db_instance",
                text_groups=[[r"publicly_accessible|public|パブリック|公開"]],
                fix_any=r"false"),
            "S3_HARDCODED_PASSWORD": dict(
                severity="critical", anchor=r"aws_db_instance",
                text_groups=[[r"password|パスワード"], [r"hard|ハード|平文|plain|直接|secret|manage_master|固定|コード|tfstate|state"]],
                fix_any=r"manage_master|secrets ?manager|ssm|parameter|variable|sensitive|変数"),
            "S3_DB_SG_OPEN": dict(
                severity="critical", anchor=r"aws_security_group\.db|(?<![A-Za-z0-9_])db(?![A-Za-z0-9_])",
                text_groups=[[r"3306|mysql|(?<![A-Za-z0-9_])db(?![A-Za-z0-9_])|database|データベース"], [r"0\.0\.0\.0/0|open|anywhere|全|any|インターネット|公開"]],
                fix_any=r"security_groups|app|sg|限定|restrict|特定"),
            "S3_RDS_UNENCRYPTED": dict(
                severity="high", anchor=r"aws_db_instance",
                text_groups=[[r"storage_encrypted|encrypt|暗号"]],
                fix_any=r"true|有効"),
            "S3_IAM_WILDCARD": dict(
                severity="high", anchor=r"aws_iam_role_policy|app_inline",
                text_groups=[[r"wildcard|ワイルド|\"\*\"|最小権限|least|過剰|full access|admin|action.*\*|\*.*action|resource.*\*"]],
                fix_any=r"least|最小|具体|特定|scope|限定|絞"),
            "S3_IMDSV1": dict(
                severity="medium", anchor=r"launch_template|metadata_options",
                text_groups=[[r"imds|metadata|http_tokens|メタデータ"]],
                fix_any=r"required"),
            "S3_ASG_PUBLIC": dict(
                severity="medium", anchor=r"vpc_zone_identifier|autoscaling_group",
                text_groups=[[r"public|パブリック"], [r"asg|autoscaling|auto scaling|vpc_zone_identifier|subnet|サブネット"]],
                fix_any=r"private|プライベート"),
            "S3_ASG_HEALTHCHECK_EC2": dict(
                severity="medium", anchor=r"autoscaling_group|health_check_type",
                text_groups=[[r"health_check_type|health.?check|ヘルスチェック"], [r"(?<![A-Za-z0-9_])ec2(?![A-Za-z0-9_])"]],
                fix_any=r"elb"),
            "S3_NO_BACKUP_FINAL_SNAPSHOT": dict(
                severity="medium", anchor=r"aws_db_instance",
                text_groups=[[r"backup|バックアップ|snapshot|スナップショット|retention"]],
                fix_any=r"backup_retention|skip_final_snapshot|final_snapshot|7|日|false"),
            "S3_NO_MULTI_AZ": dict(
                severity="medium", anchor=r"aws_db_instance",
                text_groups=[[r"multi.?az|マルチ ?az|可用性|冗長|availability"]],
                fix_any=r"true|有効|multi"),
            "S3_COUNT_LOOP": dict(
                severity="low", anchor=r"route_table_association",
                text_groups=[[r"count"]],
                fix_any=r"for_each"),
            "S3_NAME_REPEAT": dict(
                severity="low", anchor=r"nat_gateway",
                text_groups=[[RULE_NAME]],
                fix_any=r"main|rename|変更|リネーム|用途"),
            "S3_VAR_NO_DESC": dict(
                severity="low", anchor=r"instance_type",
                text_groups=[[r"variable|変数|instance_type"], [RULE_DESC]],
                fix_any=r"description|説明"),
        },
        "known_observations": r"https|tls|ssl|443|証明書|certificate|waf|access.?log|アクセスログ|egress|アウトバウンド|flow ?log|フローログ|kms|cmk|monitoring|enhanced|performance insights|iam database|auto.?minor|log export|cloudwatch|single nat|単一|nat.*(冗長|az)|タグ|tag|name_prefix|アラーム|alarm|scaling polic|スケーリング ?ポリシー|network acl|nacl|単一.?az|シングル.?az|single.?az|1az|t3\.micro|本番|production|final_snapshot_identifier|snapshot.?identifier|user.?data|ユーザーデータ|ステッキ|stickiness|timeout|タイムアウト|depends_on|依存",
    },
}
