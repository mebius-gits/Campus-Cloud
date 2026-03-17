from __future__ import annotations

from app.core.config import settings
from app.services.catalog_service import load_catalog


catalog = load_catalog(settings.resolved_templates_dir)

