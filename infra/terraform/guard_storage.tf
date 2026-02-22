provider "aws" {
  region  = "us-east-1"
  # En local apuntaría a Localstack, en prod a AWS real
}

# 1. Bucket WORM (Write Once, Read Many)
resource "aws_s3_bucket" "guard_vault" {
  bucket = "astra-guard-vault-prod"
  
  # Habilitar bloqueo de objetos (Irreversible en producción)
  object_lock_enabled = true

  tags = {
    Name        = "Astra Guard Vault"
    Environment = "Production"
    Module      = "GUARD"
  }
}

# 2. Configuración de Versionado (Obligatorio para Object Lock)
resource "aws_s3_bucket_versioning" "guard_versioning" {
  bucket = aws_s3_bucket.guard_vault.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 3. Regla de Retención por Defecto (Compliance = Ni root puede borrar)
resource "aws_s3_bucket_object_lock_configuration" "guard_lock_config" {
  bucket = aws_s3_bucket.guard_vault.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 1825 # 5 años (Estándar legal)
    }
  }
}

# 4. KMS Keys por Tenant (Ejemplo)
data "aws_caller_identity" "current" {}

resource "aws_kms_key" "tenant_keys" {
  for_each            = toset(["tenant_a", "tenant_b"])
  description         = "Master Key for ${each.key}"
  enable_key_rotation = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })
}
