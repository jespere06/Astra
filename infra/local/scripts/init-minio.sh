#!/bin/sh
echo "Waiting for MinIO..."
# Configurar alias local
mc alias set astra http://$MINIO_HOST:$MINIO_PORT $MINIO_USER $MINIO_PASS

# Convertir la lista separada por comas en iterables
IFS=','
for BUCKET in $BUCKETS; do
  echo "Checking bucket: $BUCKET"
  if mc ls astra/$BUCKET > /dev/null 2>&1; then
    echo "Bucket '$BUCKET' already exists."
  else
    echo "Creating bucket '$BUCKET'..."
    mc mb astra/$BUCKET
    # Hacer el bucket público para descarga (opcional, útil en dev)
    # mc policy set download astra/$BUCKET
  fi
done

echo "MinIO provisioning complete."
