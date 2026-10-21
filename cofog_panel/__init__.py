# Export main functions so CLI and user scripts can call them directly
from .checks import verify_cofog_format, verify_country_format
from .master_seed import seed_master
from .etl import split_data
from .aggregate import run_aggregation, resolve_value

# Export important constants (add new ones if needed)
from .master_seed import DEFAULT_START_YEAR, DEFAULT_END_YEAR

__version__ = "1.0.2"