"""COFOG-Panel: harmonise IMF GFS COFOG data into reproducible country-year panels."""

__version__ = "1.2.2"

from .aggregate import is_complete, resolve_value, run_aggregation  # noqa: E402
from .checks import verify_cofog_format, verify_country_format  # noqa: E402
from .etl import split_data  # noqa: E402
from .master_seed import DEFAULT_END_YEAR, DEFAULT_START_YEAR, prepare_master, seed_master  # noqa: E402
from .provenance import read_provenance  # noqa: E402
from .api import PipelineError, build_panel  # noqa: E402

__all__ = [
    "__version__",
    "build_panel", "PipelineError", "read_provenance",
    "is_complete", "resolve_value", "run_aggregation",
    "verify_cofog_format", "verify_country_format",
    "split_data",
    "DEFAULT_START_YEAR", "DEFAULT_END_YEAR", "prepare_master", "seed_master",
]
