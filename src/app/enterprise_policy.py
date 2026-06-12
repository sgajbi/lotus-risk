import os


def enterprise_policy_version() -> str:
    return os.getenv("ENTERPRISE_POLICY_VERSION", "1.0.0")


__all__ = ["enterprise_policy_version"]
