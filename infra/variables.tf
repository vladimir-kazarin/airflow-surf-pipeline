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

variable "github_repo" {
  description = "owner/name of the repo whose GitHub Actions may publish to the bucket."
  type        = string
  default     = "vladimir-kazarin/airflow-surf-pipeline"
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
