output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "bucket_name" {
  value = aws_s3_bucket.data.bucket
}

output "github_publisher_role_arn" {
  description = "Set as the AWS_ROLE_ARN repository variable in GitHub."
  value       = aws_iam_role.publisher.arn
}

output "dashboard_access_key_id" {
  value = aws_iam_access_key.dashboard.id
}

output "dashboard_secret_access_key" {
  description = "Goes into Streamlit Cloud secrets. Read with: terraform output -raw dashboard_secret_access_key"
  value       = aws_iam_access_key.dashboard.secret
  sensitive   = true
}
