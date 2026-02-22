#!/bin/sh
echo "Waiting for Qdrant..."

COLLECTION_NAME="templates_v1"
VECTOR_SIZE=768
DISTANCE="Cosine"

# Verificar si la colección existe
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://$QDRANT_HOST:$QDRANT_PORT/collections/$COLLECTION_NAME)

if [ "$HTTP_CODE" -eq 200 ]; then
  echo "Collection '$COLLECTION_NAME' already exists."
else
  echo "Creating collection '$COLLECTION_NAME'..."
  curl -X PUT "http://$QDRANT_HOST:$QDRANT_PORT/collections/$COLLECTION_NAME" \
       -H "Content-Type: application/json" \
       -d '{
         "vectors": {
           "size": '$VECTOR_SIZE',
           "distance": "'"$DISTANCE"'"
         }
       }'
  echo -e "\nCollection created."
fi

echo "Qdrant provisioning complete."
