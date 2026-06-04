from app.contracts.capabilities import SupportedInputMode

SERVICE_NAME = "lotus-risk"
SERVICE_VERSION = "0.1.0"
ROUNDING_POLICY_VERSION = "v1"
SUPPORTED_INPUT_MODES: tuple[SupportedInputMode, ...] = ("stateless", "stateful", "simulation")
