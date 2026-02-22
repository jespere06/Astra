from enum import Enum, auto

# Mocking astra_models_pb2 since it's not generated in this env
# In production, this would be an import from generated protos
class IntentType(str, Enum):
    INTENT_FREE_TEXT = "INTENT_FREE_TEXT"
    INTENT_TEMPLATE = "INTENT_TEMPLATE"
    INTENT_HYBRID = "INTENT_HYBRID"
    INTENT_COMMAND = "INTENT_COMMAND"
