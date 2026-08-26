from app.app_factory import create_app
from app.service_metadata import (
    SERVICE_NAME as _SERVICE_NAME,
)
from app.service_metadata import (
    SERVICE_VERSION as _SERVICE_VERSION,
)

SERVICE_NAME: str = _SERVICE_NAME
SERVICE_VERSION: str = _SERVICE_VERSION

app = create_app()
