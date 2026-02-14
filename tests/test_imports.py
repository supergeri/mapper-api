"""Verify all modules can be imported without errors."""
import pytest

# All tests in this module are pure import checks - mark as unit tests
pytestmark = pytest.mark.unit


def test_core_module_imports():
    """Import core backend modules to catch bad import paths."""
    import backend.app
    import backend.auth
    import backend.database
    import backend.bulk_import
    import backend.mobile_pairing


def test_core_logic_imports():
    """Import core logic modules."""
    import backend.core.canonicalize
    import backend.core.catalog
    import backend.core.exercise_categories
    import backend.core.exercise_suggestions
    import backend.core.garmin_matcher
    import backend.core.global_mappings
    import backend.core.match
    import backend.core.normalize
    import backend.core.user_mappings
    import backend.core.workflow


def test_adapter_imports():
    """Import adapter modules."""
    import backend.adapters.blocks_to_fit
    import backend.adapters.blocks_to_hiit_garmin_yaml
    import backend.adapters.blocks_to_hyrox_yaml
    import backend.adapters.blocks_to_workoutkit
    import backend.adapters.blocks_to_zwo
    import backend.adapters.cir_to_garmin_yaml
    import backend.adapters.garmin_lookup
    import backend.adapters.ingest_to_cir
    import backend.adapters.workoutkit_schemas
    import backend.adapters.zwo_schemas


def test_parser_imports():
    """Import parser modules."""
    import backend.parsers.base
    import backend.parsers.models
    import backend.parsers.csv_parser
    import backend.parsers.excel_parser
    import backend.parsers.json_parser
    import backend.parsers.text_parser
    import backend.parsers.url_parser
    import backend.parsers.image_parser


def test_mapping_imports():
    """Import mapping modules."""
    import backend.mapping.exercise_name_matcher


def test_app_starts():
    """Verify FastAPI app can be instantiated."""
    from backend.app import app
    assert app is not None
    assert hasattr(app, 'routes')
