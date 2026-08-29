"""Single place that imports every model so SQLAlchemy's metadata
(and Alembic, later) knows about all tables. Import this before create_all."""
from app.core.database import Base  # noqa: F401

# import all module models to register them on Base.metadata
from app.modules.users import models as user_models   # noqa: F401
from app.modules.leads import models as lead_models    # noqa: F401
from app.modules.quotations import models as quotation_models  # noqa: F401
