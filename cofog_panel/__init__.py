"""COFOG-Panel: harmonise IMF GFS COFOG data into reproducible country-year panels."""

__version__ = "1.0.5"

from .aggregate import is_complete, resolve_value, run_aggregation  # noqa: E402
from .checks import verify_cofog_format, verify_country_format  # noqa: E402
from .etl import split_data  # noqa: E402
from .master_seed import DEFAULT_END_YEAR, DEFAULT_START_YEAR, prepare_master, seed_master  # noqa: E402

__all__ = [
    "__version__",
    "is_complete", "resolve_value", "run_aggregation",
    "verify_cofog_format", "verify_country_format",
    "split_data",
    "DEFAULT_START_YEAR", "DEFAULT_END_YEAR", "prepare_master", "seed_master",
]
