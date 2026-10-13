terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
  default_tags {
    tags = { Project = var.project, ManagedBy = "terraform" }
  }
}

data "aws_caller_identity" "current" {}

locals {
  bucket_name  = "${var.project}-${data.aws_caller_identity.current.account_id}"
  github_oidc  = "token.actions.githubusercontent.com"
  provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

# --- Bucket: private, encrypted, versioned ------------------------------------

resource "aws_s3_bucket" "data" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# Versioning = an undo button if a bad publish overwrites good data.
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket     = aws_s3_bucket.data.id
  depends_on = [aws_s3_bucket_versioning.data]
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

# --- GitHub Actions publisher: OIDC, no long-lived keys ------------------------

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://${local.github_oidc}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://${local.github_oidc}"
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc}:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc}:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/${var.github_branch}"]
    }
  }
}

resource "aws_iam_role" "publisher" {
  name                 = "${var.project}-github-publisher"
  assume_role_policy   = data.aws_iam_policy_document.github_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "publisher" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
}

resource "aws_iam_role_policy" "publisher" {
  role   = aws_iam_role.publisher.id
  policy = data.aws_iam_policy_document.publisher.json
}

# --- Streamlit dashboard reader: read-only, serving/ prefix only ---------------
# Streamlit Community Cloud can't do OIDC, so it gets a narrowly scoped key.

resource "aws_iam_user" "dashboard" {
  name = "${var.project}-dashboard-reader"
}

data "aws_iam_policy_document" "dashboard" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/serving/*"]
  }
}

resource "aws_iam_user_policy" "dashboard" {
  user   = aws_iam_user.dashboard.name
  policy = data.aws_iam_policy_document.dashboard.json
}

resource "aws_iam_access_key" "dashboard" {
  user = aws_iam_user.dashboard.name
}
