import json
from src.main import app

def generate_openapi():
    with open("docs/api/orchestrator/openapi.json", "w") as f:
        json.dump(app.openapi(), f, indent=2)
    print("✅ OpenAPI Spec generated at docs/api/orchestrator/openapi.json")

if __name__ == "__main__":
    generate_openapi()
