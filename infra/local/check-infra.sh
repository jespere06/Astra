#!/bin/bash

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "--- ASTRA Infrastructure Health Check ---"

# Cargar variables
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
else
  echo -e "${RED}ERROR: No .env file found.${NC}"
  exit 1
fi

check_service() {
  NAME=$1
  URL=$2
  EXPECTED=$3
  
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $URL)
  if [ "$RESPONSE" -eq "$EXPECTED" ]; then
    echo -e "${GREEN}✔ $NAME is UP ($URL)${NC}"
  else
    echo -e "${RED}✘ $NAME is DOWN (Got $RESPONSE, expected $EXPECTED)${NC}"
  fi
}

# 1. Postgres (Check port open)
nc -z localhost $ASTRA_DB_PORT
if [ $? -eq 0 ]; then echo -e "${GREEN}✔ PostgreSQL Port $ASTRA_DB_PORT is open${NC}"; else echo -e "${RED}✘ PostgreSQL Port closed${NC}"; fi

# 2. Redis
nc -z localhost $ASTRA_REDIS_PORT
if [ $? -eq 0 ]; then echo -e "${GREEN}✔ Redis Port $ASTRA_REDIS_PORT is open${NC}"; else echo -e "${RED}✘ Redis Port closed${NC}"; fi

# 3. MinIO Console
check_service "MinIO Console" "http://localhost:$MINIO_CONSOLE_PORT" 200

# 4. Qdrant API
check_service "Qdrant API" "http://localhost:$ASTRA_QDRANT_HTTP_PORT/collections" 200

echo "--- Check Complete ---"
