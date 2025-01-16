"""Tests for yandex_smart_home integration."""

from typing import Any, Callable
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entityfilter
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.yandex_smart_home import CONF_FILTER_SOURCE, DOMAIN, EntityFilterSource
from custom_components.yandex_smart_home.config_flow import ConfigFlowHandler
from custom_components.yandex_smart_home.entry_data import ConfigEntryData
from custom_components.yandex_smart_home.helpers import STORE_CACHE_ATTRS, CacheStore


class MockConfigEntryData(ConfigEntryData):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry | None = None,
        yaml_config: ConfigType | None = None,
        entity_config: dict[str, Any] | None = None,
        entity_filter: entityfilter.EntityFilter | None = None,
    ):
        if not entry:
            entry = MockConfigEntry(
                domain=DOMAIN,
                version=ConfigFlowHandler.VERSION,
                data={},
                options={CONF_FILTER_SOURCE: EntityFilterSource.YAML},
            )

        super().__init__(hass, entry, yaml_config, entity_config, entity_filter)

        self.cache = MockCacheStore()

    @property
    def is_reporting_states(self) -> bool:
        return True


class MockStore(Store[Any]):
    def __init__(self, data: dict[str, Any]):
        self._data: dict[str, Any] = data
        self.saved_mock: MagicMock = MagicMock()

    async def async_load(self) -> dict[str, Any]:
        return self._data

    def async_delay_save(
        self,
        data_func: Callable[[], dict[str, Any]],
        delay: float = 0,
    ) -> None:
        self.saved_mock()
        return None


class MockCacheStore(CacheStore):
    _store: MockStore

    def __init__(self) -> None:
        self._data = {STORE_CACHE_ATTRS: {}}
        self._store = MockStore({})


def generate_entity_filter(
    include_entity_globs: list[str] | None = None, exclude_entities: list[str] | None = None
) -> entityfilter.EntityFilter:
    return entityfilter.EntityFilter(
        {
            entityfilter.CONF_INCLUDE_DOMAINS: [],
            entityfilter.CONF_INCLUDE_ENTITY_GLOBS: include_entity_globs or [],
            entityfilter.CONF_INCLUDE_ENTITIES: [],
            entityfilter.CONF_EXCLUDE_DOMAINS: [],
            entityfilter.CONF_EXCLUDE_ENTITY_GLOBS: [],
            entityfilter.CONF_EXCLUDE_ENTITIES: exclude_entities or [],
        }
    )


REQ_ID: str = "5ca6622d-97b5-465c-a494-fd9954f7599a"
