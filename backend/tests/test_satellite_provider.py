from datetime import date

import pytest

from app.core.config import Settings
from app.services.satellite import (
    AreaOfInterest,
    Quality,
    SatelliteProvider,
    UnsupportedVariableError,
    Variable,
    get_provider,
)
from app.services.satellite.registry import UnknownProviderError

# Geometría ficticia: solo identifica el área en las pruebas, no representa ningún embalse real
AOI = AreaOfInterest(
    code="PRUEBA", geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
)


def test_mock_returns_one_observation_per_day_inclusive():
    obs = get_provider("mock").fetch(AOI, Variable.PRECIPITATION, date(2026, 9, 1), date(2026, 9, 30))
    assert len(obs) == 30
    assert [o.day for o in obs][0] == date(2026, 9, 1) and obs[-1].day == date(2026, 9, 30)
    assert all(o.area_code == "PRUEBA" and o.source == "mock" and o.unit == "mm/día" for o in obs)


@pytest.mark.parametrize(
    ("variable", "low", "high"),
    [
        (Variable.PRECIPITATION, 0.0, 200.0),
        (Variable.SOIL_MOISTURE, 0.0, 0.6),
        (Variable.WATER_AREA, 0.0, 1000.0),
        (Variable.NDWI, -1.0, 1.0),
    ],
)
def test_mock_values_in_physical_range(variable, low, high):
    obs = get_provider("mock").fetch(AOI, variable, date(2025, 1, 1), date(2025, 12, 31))
    values = [o.value for o in obs if o.value is not None]
    assert values and all(low <= v <= high for v in values)


def test_mock_wet_season_is_wetter_than_dry_season():
    p = get_provider("mock")
    oct_ = p.fetch(AOI, Variable.PRECIPITATION, date(2025, 10, 1), date(2025, 10, 31))
    feb = p.fetch(AOI, Variable.PRECIPITATION, date(2025, 2, 1), date(2025, 2, 28))
    assert sum(o.value for o in oct_) > 2 * sum(o.value for o in feb)


def test_optical_products_carry_cloud_cover_and_quality_flag():
    obs = get_provider("mock").fetch(AOI, Variable.NDWI, date(2025, 1, 1), date(2025, 12, 31))
    assert all(o.cloud_pct is not None and 0 <= o.cloud_pct <= 100 for o in obs)
    missing = [o for o in obs if o.quality is Quality.MISSING]
    assert all(o.value is None for o in missing)
    assert {o.quality for o in obs} >= {Quality.GOOD}


def test_mock_is_deterministic():
    p = get_provider("mock")
    a = p.fetch(AOI, Variable.SOIL_MOISTURE, date(2024, 3, 1), date(2024, 3, 10))
    b = p.fetch(AOI, Variable.SOIL_MOISTURE, date(2024, 3, 1), date(2024, 3, 10))
    assert a == b


def test_invalid_range_and_unsupported_variable_are_rejected():
    p = get_provider("mock")
    with pytest.raises(ValueError, match="anterior"):
        p.fetch(AOI, Variable.NDWI, date(2025, 2, 1), date(2025, 1, 1))

    class OnlyRain(SatelliteProvider):
        name = "solo_lluvia"
        variables = frozenset({Variable.PRECIPITATION})

        def _fetch(self, aoi, variable, start, end):
            return []

        def check(self):
            return True

    with pytest.raises(UnsupportedVariableError):
        OnlyRain().fetch(AOI, Variable.NDWI, date(2025, 1, 1), date(2025, 1, 2))


def test_registry_planned_and_unknown_providers():
    with pytest.raises(NotImplementedError, match="aún no está implementada"):
        get_provider("era5_land_cds")
    assert get_provider("chirps").name == "chirps"
    with pytest.raises(UnknownProviderError):
        get_provider("no-existe")


def test_settings_default_provider_is_mock():
    s = Settings(db_password="x", _env_file=None)
    assert s.satellite_provider == "mock"
    assert get_provider(s.satellite_provider).check() is True
