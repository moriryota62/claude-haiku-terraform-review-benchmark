import pathlib, sys

root = pathlib.Path(sys.argv[1])
src = (root / "clean.tf").read_text()

def sub(old, new):
    global src
    assert src.count(old) == 1, f"not unique/missing: {old!r} ({src.count(old)})"
    src = src.replace(old, new)

sub('  storage_encrypted           = true\n', '  storage_encrypted           = false # @seed:S3_RDS_UNENCRYPTED\n')
sub('  manage_master_user_password = true\n', '  password                    = "Passw0rd123!" # @seed:S3_HARDCODED_PASSWORD\n')
sub('  multi_az                    = true\n', '  multi_az                    = false # @seed:S3_NO_MULTI_AZ\n')
sub('  publicly_accessible         = false\n', '  publicly_accessible         = true # @seed:S3_RDS_PUBLIC\n')
sub('  backup_retention_period     = 7\n', '  backup_retention_period     = 0 # @seed:S3_NO_BACKUP_FINAL_SNAPSHOT\n')
sub('  skip_final_snapshot         = false\n  final_snapshot_identifier   = "main-final"\n',
    '  skip_final_snapshot         = true # @seed:S3_NO_BACKUP_FINAL_SNAPSHOT\n')
sub('    security_groups = [aws_security_group.app.id]\n  }\n}\n\nresource "aws_lb" "main"',
    '    cidr_blocks     = ["0.0.0.0/0"] # @seed:S3_DB_SG_OPEN\n  }\n}\n\nresource "aws_lb" "main"')
sub('    description     = "MySQL from app"', '    description     = "MySQL"')
sub('http_tokens   = "required"', 'http_tokens   = "optional" # @seed:S3_IMDSV1')
sub('health_check_type         = "ELB"', 'health_check_type         = "EC2" # @seed:S3_ASG_HEALTHCHECK_EC2')
sub('  vpc_zone_identifier       = [for s in aws_subnet.private : s.id]',
    '  vpc_zone_identifier       = [for s in aws_subnet.public : s.id] # @seed:S3_ASG_PUBLIC')
sub('resource "aws_nat_gateway" "main" {', 'resource "aws_nat_gateway" "nat_gateway" { # @seed:S3_NAME_REPEAT')
sub('nat_gateway_id = aws_nat_gateway.main.id', 'nat_gateway_id = aws_nat_gateway.nat_gateway.id')
sub('variable "instance_type" {\n  type        = string\n  description = "EC2 instance type of the application servers"\n  default     = "t3.micro"\n}',
    'variable "instance_type" { # @seed:S3_VAR_NO_DESC\n  type    = string\n  default = "t3.micro"\n}')
sub('resource "aws_route_table_association" "private" {\n  for_each = aws_subnet.private\n\n  subnet_id      = each.value.id',
    'resource "aws_route_table_association" "private" {\n  count = length(aws_subnet.private) # @seed:S3_COUNT_LOOP\n\n  subnet_id      = values(aws_subnet.private)[count.index].id')
sub('resource "aws_iam_instance_profile" "app" {',
    'resource "aws_iam_role_policy" "app_inline" {\n  name = "app-inline"\n  role = aws_iam_role.app.id\n\n  policy = jsonencode({\n    Version = "2012-10-17"\n    Statement = [{\n      Effect   = "Allow"\n      Action   = "*" # @seed:S3_IAM_WILDCARD\n      Resource = "*" # @seed:S3_IAM_WILDCARD\n    }]\n  })\n}\n\nresource "aws_iam_instance_profile" "app" {')
(root / "buggy.tf").write_text(src)
print("ok", src.count("@seed"))
