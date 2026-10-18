terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block of the VPC"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks of the public subnets"
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability zones of the public subnets"
  default     = ["ap-northeast-1a", "ap-northeast-1c"]
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR block allowed to connect to the instance over SSH"
  default     = "0.0.0.0/0" # @seed:S2_SSH_OPEN
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type"
  default     = "t3.micro"
}

resource "aws_vpc" "vpc" { # @seed:S2_NAME_REPEAT
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "main" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.vpc.id

  tags = { Name = "main" }
}

resource "aws_subnet" "public" {
  count = length(var.public_subnet_cidrs) # @seed:S2_COUNT_LOOP

  vpc_id            = aws_vpc.vpc.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = { Name = "public-${count.index}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "public" }
}

resource "aws_route_table_association" "public" {
  count = length(var.public_subnet_cidrs) # @seed:S2_COUNT_LOOP

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "web" {
  name        = "web"
  description = "Allow SSH"
  vpc_id      = aws_vpc.vpc.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "web" {
  ami                    = "ami-0abcdef1234567890" # @seed:S2_HARDCODED_AMI
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.web.id]

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "optional" # @seed:S2_IMDSV1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = false # @seed:S2_EBS_UNENCRYPTED
  }

  tags = { Name = "web" }
}

output "instance_id" { # @seed:S2_OUTPUT_NO_DESC
  value = aws_instance.web.id
}
