variable "aws_profile" {
  description = "Local AWS CLI profile Terraform uses."
  type        = string
  default     = "terraform"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "airflow-surf-pipeline"
}

variable "github_subject_prefix" {
  description = <<-EOT
    OIDC `sub` prefix of the repo allowed to publish. GitHub's immutable format embeds the
    owner and repo IDs, so a deleted-and-recreated repo with the same name can't assume the
    role. Find yours with: gh api repos/OWNER/REPO/actions/oidc/customization/sub
  EOT
  type        = string
  default     = "repo:vladimir-kazarin@18403526/airflow-surf-pipeline@1418119502"
}

variable "github_branch" {
  description = "Only workflows running on this branch can assume the publish role."
  type        = string
  default     = "main"
}

variable "create_github_oidc_provider" {
  description = "An AWS account can hold only one GitHub OIDC provider. Set true only if yours has none."
  type        = bool
  default     = false
}
