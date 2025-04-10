import asyncio
from datetime import timedelta
import json
import logging
import time
from typing import Any, Coroutine, Generator, cast
from unittest.mock import AsyncMock, patch

from aiohttp.client_exceptions import ClientConnectionError
from homeassistant.auth.models import User
from homeassistant.components.event import ATTR_EVENT_TYPE, EventDeviceClass
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_ID,
    CONF_PLATFORM,
    CONF_STATE_TEMPLATE,
    CONF_TOKEN,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPressure,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.yandex_smart_home import DOMAIN, YandexSmartHome
from custom_components.yandex_smart_home.capability_custom import CustomOnOffCapability, get_custom_capability
from custom_components.yandex_smart_home.capability_onoff import OnOffCapabilityBasic
from custom_components.yandex_smart_home.config_flow import ConfigFlowHandler
from custom_components.yandex_smart_home.const import (
    CONF_CLOUD_INSTANCE,
    CONF_CLOUD_INSTANCE_CONNECTION_TOKEN,
    CONF_CLOUD_INSTANCE_ID,
    CONF_CONNECTION_TYPE,
    CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID,
    CONF_ENTITY_CUSTOM_MODES,
    CONF_ENTITY_CUSTOM_RANGES,
    CONF_ENTITY_CUSTOM_TOGGLES,
    CONF_ENTITY_MODE_MAP,
    CONF_ENTITY_PROPERTIES,
    CONF_ENTITY_PROPERTY_ENTITY,
    CONF_ENTITY_PROPERTY_TYPE,
    CONF_LINKED_PLATFORMS,
    CONF_SKILL,
    CONF_USER_ID,
    ConnectionType,
)
from custom_components.yandex_smart_home.helpers import APIError, SmartHomePlatform
from custom_components.yandex_smart_home.notifier import (
    CloudNotifier,
    Notifier,
    NotifierConfig,
    PendingStates,
    YandexDirectNotifier,
)
from custom_components.yandex_smart_home.property_custom import (
    ButtonPressCustomEventProperty,
    ButtonPressEventPlatformCustomProperty,
    CO2LevelCustomFloatProperty,
    HumidityCustomFloatProperty,
    PressureCustomFloatProperty,
    get_custom_property,
)
from custom_components.yandex_smart_home.property_float import HumiditySensor, TemperatureSensor
from custom_components.yandex_smart_home.schema import (
    CapabilityType,
    EventPropertyInstance,
    FloatPropertyInstance,
    RangeCapabilityInstance,
    ResponseCode,
)
from tests.test_device import ATTR_UNIT_OF_MEASUREMENT

from . import REQ_ID, MockConfigEntryData, generate_entity_filter, test_cloud

BASIC_CONFIG = NotifierConfig(user_id="bread", token="xyz", skill_id="a-b-c")


@pytest.fixture(name="mock_call_later")
def mock_call_later_fixture() -> Generator[AsyncMock, None, None]:
    with patch("custom_components.yandex_smart_home.notifier.async_call_later") as mock_call_later:
        yield mock_call_later


async def _async_set_state(
    hass: HomeAssistant, entity_id: str, new_state: str, attributes: dict[str, Any] | None = None
) -> None:
    hass.states.async_set(entity_id, new_state, attributes)
    await hass.async_block_till_done()


async def _assert_empty_list(coro: Coroutine[Any, Any, Any]) -> None:
    assert await coro == []


async def _assert_not_empty_list(coro: Coroutine[Any, Any, Any]) -> None:
    assert await coro != []


async def test_notifier_setup_no_linked_platforms(
    hass: HomeAssistant, hass_admin_user: User, aioclient_mock: AiohttpClientMocker
) -> None:
    test_cloud.mock_client_session(hass, test_cloud.MockSession(aioclient_mock))

    config_entry_direct_yandex = MockConfigEntry(
        title="Direct Yandex",
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={CONF_CONNECTION_TYPE: ConnectionType.DIRECT, CONF_PLATFORM: SmartHomePlatform.YANDEX},
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_TOKEN: "token",
                CONF_USER_ID: hass_admin_user.id,
            },
            "_reporting_states": True,
        },
    )
    config_entry_direct_vk = MockConfigEntry(
        title="Direct VK",
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={CONF_CONNECTION_TYPE: ConnectionType.DIRECT, CONF_PLATFORM: SmartHomePlatform.VK},
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_USER_ID: hass_admin_user.id,
            },
            "_reporting_states": False,
        },
    )
    config_entry_cloud = MockConfigEntry(
        title="Cloud",
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.CLOUD,
            CONF_CLOUD_INSTANCE: {
                CONF_CLOUD_INSTANCE_ID: "test",
                CONF_CLOUD_INSTANCE_CONNECTION_TOKEN: "foo",
            },
        },
        options={
            "_reporting_states": True,
        },
    )
    config_entry_cloud_plus_yandex = MockConfigEntry(
        title="Cloud Plus Yandex",
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.CLOUD_PLUS,
            CONF_PLATFORM: SmartHomePlatform.YANDEX,
            CONF_CLOUD_INSTANCE: {
                CONF_CLOUD_INSTANCE_ID: "test",
                CONF_CLOUD_INSTANCE_CONNECTION_TOKEN: "foo",
            },
        },
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_TOKEN: "token",
            },
            "_reporting_states": True,
        },
    )
    config_entry_cloud_plus_vk = MockConfigEntry(
        title="Cloud Plus VK",
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.CLOUD_PLUS,
            CONF_PLATFORM: SmartHomePlatform.VK,
            CONF_CLOUD_INSTANCE: {
                CONF_CLOUD_INSTANCE_ID: "test",
                CONF_CLOUD_INSTANCE_CONNECTION_TOKEN: "foo",
            },
        },
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
            },
            "_reporting_states": False,
        },
    )

    for config_entry in [
        config_entry_direct_yandex,
        config_entry_direct_vk,
        config_entry_cloud,
        config_entry_cloud_plus_yandex,
        config_entry_cloud_plus_vk,
    ]:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)

        component: YandexSmartHome = hass.data[DOMAIN]
        assert component.get_entry_data(config_entry).is_reporting_states is config_entry.options["_reporting_states"]
        assert len(component.get_entry_data(config_entry)._notifiers) == 0


@pytest.mark.parametrize(
    "platforms",
    [
        [SmartHomePlatform.YANDEX],
        [SmartHomePlatform.YANDEX, SmartHomePlatform.VK],
    ],
)
async def test_notifier_lifecycle_link_platform_cloud(
    hass: HomeAssistant, hass_admin_user: User, platforms: list[SmartHomePlatform], aioclient_mock: AiohttpClientMocker
) -> None:
    test_cloud.mock_client_session(hass, test_cloud.MockSession(aioclient_mock))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.CLOUD,
            CONF_CLOUD_INSTANCE: {
                CONF_CLOUD_INSTANCE_ID: "test",
                CONF_CLOUD_INSTANCE_CONNECTION_TOKEN: "foo",
            },
            CONF_LINKED_PLATFORMS: platforms,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)

    component: YandexSmartHome = hass.data[DOMAIN]
    assert len(component.get_entry_data(config_entry)._notifiers) == len(platforms)

    for notifier in component.get_entry_data(config_entry)._notifiers:
        assert notifier._unsub_state_changed is not None
        assert notifier._unsub_initial_report is not None
        assert notifier._unsub_heartbeat_report is not None
        assert notifier._unsub_report_states is None
        assert notifier._unsub_discovery is not None
        assert notifier._config.platform is not None

    await hass.config_entries.async_unload(config_entry.entry_id)

    for notifier in component.get_entry_data(config_entry)._notifiers:
        assert notifier._unsub_state_changed is None
        assert notifier._unsub_initial_report is None
        assert notifier._unsub_heartbeat_report is None
        assert notifier._unsub_report_states is None
        assert notifier._unsub_discovery is None


@pytest.mark.parametrize(
    "platform,supported",
    [
        (SmartHomePlatform.YANDEX, True),
        (SmartHomePlatform.VK, False),
    ],
)
async def test_notifier_lifecycle_link_platform_direct(
    hass: HomeAssistant,
    hass_admin_user: User,
    platform: SmartHomePlatform,
    supported: bool,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    test_cloud.mock_client_session(hass, test_cloud.MockSession(aioclient_mock))

    config_entry_direct = MockConfigEntry(
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.DIRECT,
            CONF_PLATFORM: platform,
            CONF_LINKED_PLATFORMS: [platform],
        },
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_TOKEN: "token",
                CONF_USER_ID: hass_admin_user.id,
            }
        },
    )

    config_entry_cloud_plus = MockConfigEntry(
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.CLOUD_PLUS,
            CONF_PLATFORM: platform,
            CONF_CLOUD_INSTANCE: {
                CONF_CLOUD_INSTANCE_ID: "test",
                CONF_CLOUD_INSTANCE_CONNECTION_TOKEN: "foo",
            },
            CONF_LINKED_PLATFORMS: [platform],
        },
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_TOKEN: "token",
            }
        },
    )

    for config_entry in [config_entry_direct, config_entry_cloud_plus]:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)

    component: YandexSmartHome = hass.data[DOMAIN]
    if not supported:
        assert len(component.get_entry_data(config_entry_direct)._notifiers) == 0
        assert len(component.get_entry_data(config_entry_cloud_plus)._notifiers) == 0
    else:
        assert len(component.get_entry_data(config_entry_direct)._notifiers) == 1
        assert len(component.get_entry_data(config_entry_cloud_plus)._notifiers) == 1

    for config_entry in [config_entry_direct, config_entry_cloud_plus]:
        for notifier in component.get_entry_data(config_entry)._notifiers:
            assert notifier._unsub_state_changed is not None
            assert notifier._unsub_initial_report is not None
            assert notifier._unsub_report_states is None
            assert notifier._unsub_discovery is not None

        await hass.config_entries.async_unload(config_entry.entry_id)

        for notifier in component.get_entry_data(config_entry)._notifiers:
            assert notifier._unsub_state_changed is None
            assert notifier._unsub_initial_report is None
            assert notifier._unsub_report_states is None
            assert notifier._unsub_discovery is None


async def test_notifier_missing_skill_data_yandex(
    hass: HomeAssistant, hass_admin_user: User, issue_registry: ir.IssueRegistry
) -> None:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.DIRECT,
            CONF_PLATFORM: SmartHomePlatform.YANDEX,
            CONF_LINKED_PLATFORMS: [SmartHomePlatform.YANDEX],
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, "missing_skill_data") is not None

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_TOKEN: "token",
                CONF_USER_ID: hass_admin_user.id,
            }
        },
    )
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "missing_skill_data") is None

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_notifier_missing_skill_data_vk(
    hass: HomeAssistant, hass_admin_user: User, issue_registry: ir.IssueRegistry
) -> None:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.DIRECT,
            CONF_PLATFORM: SmartHomePlatform.VK,
            CONF_LINKED_PLATFORMS: [SmartHomePlatform.VK],
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, "missing_skill_data") is None


async def test_notifier_postponed_setup(hass: HomeAssistant, hass_admin_user: User) -> None:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=ConfigFlowHandler.VERSION,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.DIRECT,
            CONF_PLATFORM: SmartHomePlatform.YANDEX,
            CONF_LINKED_PLATFORMS: [SmartHomePlatform.YANDEX],
        },
        options={
            CONF_SKILL: {
                CONF_ID: "skill_id",
                CONF_TOKEN: "token",
                CONF_USER_ID: hass_admin_user.id,
            }
        },
    )
    with patch.object(hass, "state", return_value=CoreState.starting):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        component: YandexSmartHome = hass.data[DOMAIN]
        assert len(component.get_entry_data(config_entry)._notifiers) == 0
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        assert len(component.get_entry_data(config_entry)._notifiers) == 1


@pytest.mark.parametrize("cls", [YandexDirectNotifier, CloudNotifier])
async def test_notifier_format_log_message(
    hass: HomeAssistant, entry_data: MockConfigEntryData, cls: type[Notifier], caplog: pytest.LogCaptureFixture
) -> None:
    n = cls(hass, entry_data, NotifierConfig(user_id="foo", skill_id="bar", token="x"), {}, {})
    ne = cls(hass, entry_data, NotifierConfig(user_id="foo", skill_id="bar", token="x", extended_log=True), {}, {})
    assert n._format_log_message("test") == "test"
    assert ne._format_log_message("test") == "Mock Title: test"

    caplog.clear()
    n._debug_log("test")
    ne._debug_log("test")
    assert caplog.messages == ["test", f"({entry_data.entry.entry_id[:6]}) test"]


async def test_notifier_track_templates(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    hass = hass_platform
    entry_data = MockConfigEntryData(
        hass=hass,
        entity_config={
            "light.kitchen": {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "temperature",
                        CONF_ENTITY_PROPERTY_ENTITY: "binary_sensor.foo",  # it fails
                    },
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "humidity",
                        CONF_ENTITY_PROPERTY_ENTITY: "sensor.float",
                    },
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "pressure",
                        CONF_ENTITY_PROPERTY_ENTITY: "sensor.pressure",
                    },
                ]
            },
            "sensor.outside_temp": {
                CONF_STATE_TEMPLATE: Template("{{ states('sensor.state_template') }}", hass),
                CONF_ENTITY_MODE_MAP: {"dishwashing": {"fowl": ["one"], "two": ["two"]}},
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "button",
                        CONF_ENTITY_PROPERTY_ENTITY: "sensor.button",
                    },
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "co2_level",
                        CONF_ENTITY_PROPERTY_ENTITY: "sensor.float",
                    },
                ],
                CONF_ENTITY_CUSTOM_MODES: {
                    "dishwashing": {CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: "sensor.dishwashing"},
                },
                CONF_ENTITY_CUSTOM_TOGGLES: {
                    "pause": {CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: "binary_sensor.pause"}
                },
                CONF_ENTITY_CUSTOM_RANGES: {"volume": {CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: "sensor.volume"}},
            },
            "switch.not_exposed": {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "humidity",
                        CONF_ENTITY_PROPERTY_ENTITY: "sensor.float",
                    },
                ]
            },
        },
        entity_filter=generate_entity_filter(exclude_entities=["switch.not_exposed"]),
    )

    hass.states.async_set("sensor.button", "click")
    hass.states.async_set("sensor.float", "10")
    hass.states.async_set("sensor.pressure", "1000", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.HPA})
    caplog.clear()
    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )
    await notifier.async_setup()

    assert notifier._template_changes_tracker is not None
    assert notifier._pending.empty is True
    assert caplog.messages[:1] == [
        "Failed to track custom property: Unsupported entity binary_sensor.foo for "
        "temperature property of light.kitchen",
    ]

    # event
    mock_call_later.reset_mock()
    await _async_set_state(hass, "sensor.button", "click", {"foo": "bar"})
    assert notifier._pending.empty is True
    await _async_set_state(hass, "sensor.button", "double_click", {"foo": "bar"})
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["sensor.outside_temp"]
    assert len(pending["sensor.outside_temp"]) == 1
    assert pending["sensor.outside_temp"][0].get_value() == "double_click"
    mock_call_later.assert_called_once()
    assert mock_call_later.call_args[1]["delay"] == 0
    assert notifier._unsub_report_states is not None

    # float
    mock_call_later.reset_mock()
    await _async_set_state(hass, "sensor.float", "50")
    await _async_set_state(hass, "sensor.pressure", "1200", {ATTR_UNIT_OF_MEASUREMENT: UnitOfPressure.HPA})
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["light.kitchen", "sensor.outside_temp"]
    assert isinstance(pending["light.kitchen"][0], HumidityCustomFloatProperty)
    assert pending["light.kitchen"][0].get_value() == 50
    assert pending["light.kitchen"][0].instance == "humidity"
    assert isinstance(pending["light.kitchen"][1], PressureCustomFloatProperty)
    assert pending["light.kitchen"][1].get_value() == 900.07
    assert pending["light.kitchen"][1].instance == "pressure"
    print(pending["sensor.outside_temp"][0])
    assert isinstance(pending["sensor.outside_temp"][0], CO2LevelCustomFloatProperty)
    assert pending["sensor.outside_temp"][0].get_value() == 50
    assert pending["sensor.outside_temp"][0].instance == "co2_level"
    caplog.clear()
    await _async_set_state(hass, "sensor.float", "q")
    assert notifier._pending.empty is True
    assert (
        caplog.messages[-1] == "Unsupported value 'q' for instance co2_level of float property of sensor.outside_temp"
    )
    mock_call_later.assert_not_called()

    # onoff
    mock_call_later.reset_mock()
    notifier._unsub_report_states = None
    await _async_set_state(hass, "sensor.state_template", "off")
    assert notifier._pending.empty is True
    caplog.clear()
    await _async_set_state(hass, "sensor.state_template", "on")
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["sensor.outside_temp"]
    assert isinstance(pending["sensor.outside_temp"][0], CustomOnOffCapability)

    # mode
    mock_call_later.reset_mock()
    notifier._unsub_report_states = None
    await _async_set_state(hass, "sensor.dishwashing", "x")
    assert notifier._pending.empty is True
    caplog.clear()
    await _async_set_state(hass, "sensor.dishwashing", "one")
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["sensor.outside_temp"]
    assert len(pending["sensor.outside_temp"]) == 1
    assert pending["sensor.outside_temp"][0].get_value() == "fowl"
    assert (
        caplog.messages[-1]
        == "State report with value 'fowl' scheduled for <CustomModeCapability device_id=sensor.outside_temp "
        "instance=dishwashing value_template=Template<template=({{ states('sensor.dishwashing') }}) renders=0> value=one>"
    )
    await _async_set_state(hass, "sensor.dishwashing", "unavailable")
    assert notifier._pending.empty is True
    mock_call_later.assert_called_once()
    assert mock_call_later.call_args[1]["delay"] == timedelta(seconds=1)
    assert notifier._unsub_report_states is not None

    # toggle
    await _async_set_state(hass, "binary_sensor.pause", "off")  # type: ignore[unreachable]
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["sensor.outside_temp"]
    assert len(pending["sensor.outside_temp"]) == 1
    assert pending["sensor.outside_temp"][0].get_value() is False
    await _async_set_state(hass, "binary_sensor.pause", "unavailable")
    assert notifier._pending.empty is True
    await _async_set_state(hass, "binary_sensor.pause", "on")
    pending = await notifier._pending.async_get_all()
    assert pending["sensor.outside_temp"][0].get_value() is True

    # range
    await _async_set_state(hass, "sensor.volume", "50")
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["sensor.outside_temp"]
    assert len(pending["sensor.outside_temp"]) == 1
    assert pending["sensor.outside_temp"][0].get_value() == 50
    await _async_set_state(hass, "sensor.volume", "unavailable")
    assert notifier._pending.empty is True

    await notifier.async_unload()
    assert notifier._template_changes_tracker is None


async def test_notifier_track_templates_exception(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    hass = hass_platform
    entry_data = MockConfigEntryData(
        hass=hass,
        entity_config={
            "light.kitchen": {
                CONF_ENTITY_CUSTOM_RANGES: {
                    "volume": {CONF_STATE_TEMPLATE: Template("{{ 100 / states('sensor.v')|int(10) }}", hass)}
                },
            },
        },
        entity_filter=generate_entity_filter(include_entity_globs=["*"]),
    )

    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )
    await notifier.async_setup()

    caplog.clear()
    assert notifier._pending.empty is True
    hass.states.async_set("sensor.v", "5")
    await hass.async_block_till_done()
    pending = await notifier._pending.async_get_all()
    assert len(pending.keys()) == 1

    caplog.clear()
    hass.states.async_set("sensor.v", "0")
    await hass.async_block_till_done()
    assert notifier._pending.empty is True
    assert caplog.messages[-1] == "Error while processing template: {{ 100 / states('sensor.v')|int(10) }}"

    caplog.clear()
    hass.states.async_set("sensor.v", "6")
    await hass.async_block_till_done()
    pending = await notifier._pending.async_get_all()
    assert len(pending.keys()) == 1

    await notifier.async_unload()


async def test_notifier_track_entity_states(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    hass = hass_platform
    entry_data = MockConfigEntryData(
        hass=hass,
        entity_config={
            "light.kitchen": {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "button",
                        CONF_ENTITY_PROPERTY_ENTITY: "event.button",
                    },
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "motion",
                        CONF_ENTITY_PROPERTY_ENTITY: "event.motion",
                    },
                ]
            },
            "input_text.button": {
                CONF_TYPE: "devices.types.other",
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "button",
                        CONF_ENTITY_PROPERTY_ENTITY: "event.button",
                    },
                ],
            },
            "switch.not_exposed": {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "button",
                        CONF_ENTITY_PROPERTY_ENTITY: "event.button",
                    },
                ]
            },
        },
        entity_filter=generate_entity_filter(exclude_entities=["switch.not_exposed", "event.button", "event.motion"]),
    )

    hass.states.async_set("input_text.button", "")
    await hass.async_block_till_done()
    caplog.clear()

    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )
    await notifier.async_setup()
    assert notifier._pending.empty is True

    mock_call_later.reset_mock()
    await _async_set_state(hass, "event.motion", STATE_UNKNOWN, {ATTR_EVENT_TYPE: "motion"})
    assert cast(bool, notifier._pending.empty) is False
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["light.kitchen"]
    assert len(pending["light.kitchen"]) == 1
    assert pending["light.kitchen"][0].get_value() == "detected"

    await _async_set_state(hass, "event.button", STATE_UNKNOWN, {ATTR_EVENT_TYPE: "pressed"})
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["light.kitchen", "input_text.button"]
    assert pending["light.kitchen"][0].get_value() == "click"
    assert pending["input_text.button"][0].get_value() == "click"

    mock_call_later.assert_called_once()
    assert mock_call_later.call_args[1]["delay"] == 0

    mock_call_later.reset_mock()
    await _async_set_state(hass, "event.button", "tick", {ATTR_EVENT_TYPE: "pressed"})
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["light.kitchen", "input_text.button"]


async def test_notifier_state_changed(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    hass = hass_platform
    entry_data = MockConfigEntryData(
        hass=hass,
        entity_filter=generate_entity_filter(exclude_entities=["switch.not_exposed"]),
    )

    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )
    await notifier.async_setup()

    await _async_set_state(hass, "switch.not_exposed", "on")
    await _async_set_state(hass, "switch.not_exposed", "off")
    assert notifier._pending.empty is True
    assert notifier._unsub_report_states is None

    caplog.clear()
    mock_call_later.reset_mock()
    await _async_set_state(hass, "sensor.button", "click", {ATTR_DEVICE_CLASS: "button"})
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["sensor.button"]
    assert len(pending["sensor.button"]) == 1
    assert pending["sensor.button"][0].get_value() == "click"
    assert caplog.messages[-1] == (
        "State report with value 'click' scheduled for <ButtonPressStateEventProperty "
        "device_id=sensor.button type=devices.properties.event instance=button>"
    )
    mock_call_later.assert_called_once()
    assert notifier._unsub_report_states is not None

    await _async_set_state(hass, "binary_sensor.front_door", "off", {ATTR_DEVICE_CLASS: "door"})  # type: ignore[unreachable]
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["binary_sensor.front_door"]
    assert len(pending["binary_sensor.front_door"]) == 1
    assert pending["binary_sensor.front_door"][0].get_value() == "closed"

    light_state = hass.states.get("light.kitchen")
    assert light_state
    await _async_set_state(hass, light_state.entity_id, "off", light_state.attributes)
    pending = await notifier._pending.async_get_all()
    assert list(pending.keys()) == ["light.kitchen"]
    assert len(pending["light.kitchen"]) == 1
    assert pending["light.kitchen"][0].get_value() is False
    assert caplog.messages[-1] == (
        "State report with value 'False' scheduled for <OnOffCapabilityBasic "
        "device_id=light.kitchen type=devices.capabilities.on_off instance=on>"
    )

    hass.states.async_remove("light.kitchen")
    assert notifier._pending.empty is True

    await notifier.async_unload()


@pytest.mark.parametrize("use_custom", [True, False])
async def test_notifier_track_templates_over_states(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, use_custom: bool
) -> None:
    hass = hass_platform
    test_light = cast(State, hass.states.get("light.kitchen"))
    test_sensor = cast(State, hass.states.get("sensor.outside_temp"))

    entity_config = {}
    if use_custom:
        entity_config = {
            test_light.entity_id: {
                CONF_ENTITY_CUSTOM_RANGES: {"brightness": {CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: "sensor.foo"}}
            },
            test_sensor.entity_id: {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "temperature",
                        CONF_ENTITY_PROPERTY_ENTITY: "sensor.foo",
                    }
                ]
            },
        }

    entry_data = MockConfigEntryData(
        hass=hass,
        entity_config=entity_config,
        entity_filter=generate_entity_filter(include_entity_globs=["*"]),
    )

    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )
    await notifier.async_setup()
    assert notifier._pending.empty is True

    await _async_set_state(
        hass,
        test_light.entity_id,
        test_light.state,
        test_light.attributes | {ATTR_BRIGHTNESS: "99"},
    )
    if use_custom:
        assert notifier._pending.empty is True
    else:
        assert len(await notifier._pending.async_get_all()) > 0

    await _async_set_state(
        hass,
        test_sensor.entity_id,
        "99",
        test_sensor.attributes,
    )
    if use_custom:
        assert notifier._pending.empty is True
    else:
        assert len(await notifier._pending.async_get_all()) > 0

    await notifier.async_unload()


async def test_notifier_initial_report(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    entry_data = MockConfigEntryData(
        hass=hass_platform,
        entity_config={
            "light.kitchen": {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "temperature",
                        CONF_ENTITY_PROPERTY_ENTITY: "binary_sensor.foo",  # cursed property
                    }
                ]
            }
        },
        entity_filter=generate_entity_filter(exclude_entities=["switch.test"]),
    )
    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )

    hass_platform.states.async_set("switch.test", "on")
    hass_platform.states.async_set(
        "sensor.button", "on", {ATTR_DEVICE_CLASS: EventDeviceClass.BUTTON, "last_action": "click"}
    )

    await notifier._async_initial_report()
    mock_call_later.assert_called_once()

    devices = await notifier._pending.async_get_all()
    assert list(devices.keys()) == ["sensor.outside_temp", "light.kitchen"]

    def _get_states(entity_id: str) -> list[dict[str, Any]]:
        states: list[dict[str, Any]] = []
        for s in devices[entity_id]:
            instance_state = s.get_instance_state()
            if instance_state:
                states.append(instance_state.as_dict())

        return states

    assert _get_states("sensor.outside_temp") == [
        {"state": {"instance": "temperature", "value": 15.6}, "type": "devices.properties.float"},
    ]

    assert _get_states("light.kitchen") == [
        {"state": {"instance": "temperature_k", "value": 4200}, "type": "devices.capabilities.color_setting"},
        {"state": {"instance": "on", "value": True}, "type": "devices.capabilities.on_off"},
        {"state": {"instance": "brightness", "value": 70}, "type": "devices.capabilities.range"},
    ]

    assert notifier._pending.empty is True
    assert caplog.messages[-1:] == ["Unsupported entity binary_sensor.foo for temperature property of light.kitchen"]


async def test_notifier_heartbeat_report(
    hass_platform: HomeAssistant, mock_call_later: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    entry_data = MockConfigEntryData(
        hass=hass_platform,
        entity_config={
            "light.kitchen": {
                CONF_ENTITY_PROPERTIES: [
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "temperature",
                    }
                ]
            }
        },
        entity_filter=generate_entity_filter(exclude_entities=["switch.test"]),
    )
    notifier = YandexDirectNotifier(
        hass_platform,
        entry_data,
        BASIC_CONFIG,
        entry_data._get_trackable_templates(),
        entry_data._get_trackable_entity_states(),
    )

    hass_platform.states.async_set("switch.test", "on")
    hass_platform.states.async_set(
        "sensor.button", "on", {ATTR_DEVICE_CLASS: EventDeviceClass.BUTTON, "last_action": "click"}
    )

    await notifier.async_setup()

    call_args = mock_call_later.mock_calls[1].kwargs
    assert isinstance(call_args["delay"], timedelta)
    assert 3660 <= call_args["delay"].seconds <= 3600 + 15 * 60

    mock_call_later.reset_mock()
    await notifier._async_hearbeat_report()

    devices = await notifier._pending.async_get_all()
    assert list(devices.keys()) == ["sensor.outside_temp", "light.kitchen"]

    def _get_states(entity_id: str) -> list[dict[str, Any]]:
        states: list[dict[str, Any]] = []
        for s in devices[entity_id]:
            instance_state = s.get_instance_state()
            if instance_state:
                states.append(instance_state.as_dict())

        return states

    assert _get_states("sensor.outside_temp") == [
        {"state": {"instance": "temperature", "value": 15.6}, "type": "devices.properties.float"},
    ]

    assert notifier._pending.empty is True

    call_args = mock_call_later.mock_calls[0].kwargs
    assert isinstance(call_args["delay"], timedelta)
    assert call_args["delay"].seconds == 3600


async def test_notifier_send_callback_exception(
    hass: HomeAssistant, entry_data: MockConfigEntryData, caplog: pytest.LogCaptureFixture
) -> None:
    notifier = YandexDirectNotifier(hass, entry_data, BASIC_CONFIG, {}, {})

    with patch.object(notifier._session, "post", side_effect=ClientConnectionError()):
        caplog.clear()
        await notifier.async_send_discovery()
        assert caplog.records[-1].message == "State notification request failed: ClientConnectionError()"
        assert caplog.records[-1].levelno == logging.WARN
        caplog.clear()

    with patch.object(notifier._session, "post", side_effect=asyncio.TimeoutError()):
        await notifier.async_send_discovery()
        assert caplog.records[-1].message == "State notification request failed: TimeoutError()"
        assert caplog.records[-1].levelno == logging.DEBUG


async def test_notifier_send_direct(
    hass: HomeAssistant,
    entry_data: MockConfigEntryData,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    notifier = YandexDirectNotifier(hass, entry_data, BASIC_CONFIG, {}, {})
    token = BASIC_CONFIG.token
    skill_id = BASIC_CONFIG.skill_id
    user_id = BASIC_CONFIG.user_id
    now = time.time()

    aioclient_mock.post(
        f"https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/discovery",
        status=202,
        json={"request_id": REQ_ID, "status": "ok"},
    )

    with patch("time.time", return_value=now):
        await notifier.async_send_discovery()

    assert aioclient_mock.call_count == 1
    assert json.loads(aioclient_mock.mock_calls[0][2]._value) == {"ts": now, "payload": {"user_id": user_id}}
    assert aioclient_mock.mock_calls[0][3] == {"Authorization": f"OAuth {token}"}
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/state",
        status=202,
        json={"request_id": REQ_ID, "status": "ok"},
    )
    await notifier._pending.async_add(
        [ButtonPressCustomEventProperty(hass, entry_data, {}, "btn", Template("click", hass))],
        [],
    )

    with patch("time.time", return_value=now):
        await notifier._async_report_states()

    await hass.async_block_till_done()
    assert len(caplog.messages) == 1
    assert aioclient_mock.call_count == 1
    assert json.loads(aioclient_mock.mock_calls[0][2]._value) == {
        "ts": now,
        "payload": {
            "devices": [
                {
                    "id": "btn",
                    "properties": [
                        {"type": "devices.properties.event", "state": {"instance": "button", "value": "click"}}
                    ],
                }
            ],
            "user_id": user_id,
        },
    }
    assert aioclient_mock.mock_calls[0][3] == {"Authorization": f"OAuth {token}"}
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/discovery",
        status=400,
        json={"request_id": REQ_ID, "status": "error", "error_message": "some error"},
    )
    await notifier.async_send_discovery()

    assert aioclient_mock.call_count == 1
    assert caplog.messages[-1] == "State notification request failed: some error"
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/discovery",
        status=400,
        json={"request_id": REQ_ID, "status": "error", "error_code": "some code"},
    )
    await notifier.async_send_discovery()

    assert aioclient_mock.call_count == 1
    assert caplog.messages[-1] == "State notification request failed: some code"
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/discovery",
        status=500,
        content=b"ERROR",
    )
    await notifier.async_send_discovery()
    assert aioclient_mock.call_count == 1
    assert caplog.messages[-1] == "State notification request failed: ERROR"
    aioclient_mock.clear_requests()
    caplog.clear()

    with patch.object(notifier._session, "post", side_effect=Exception("boo")):
        await notifier.async_send_discovery()
        assert aioclient_mock.call_count == 0
    assert "Unexpected exception" in caplog.messages[-1]


@pytest.mark.parametrize(
    "platform,config",
    [
        (SmartHomePlatform.YANDEX, NotifierConfig(user_id="bread", token="xyz", platform=SmartHomePlatform.YANDEX)),
        (SmartHomePlatform.VK, NotifierConfig(user_id="bread", token="xyz", platform=SmartHomePlatform.VK)),
    ],
)
async def test_notifier_send_cloud(
    hass: HomeAssistant,
    platform: SmartHomePlatform,
    config: NotifierConfig,
    entry_data: MockConfigEntryData,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await async_setup_component(hass, DOMAIN, {})

    notifier = CloudNotifier(hass, entry_data, config, {}, {})
    token = config.token
    user_id = config.user_id
    now = time.time()

    aioclient_mock.post(
        f"https://yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/discovery",
        status=202,
        json={"request_id": REQ_ID, "status": "ok"},
    )

    with patch("time.time", return_value=now):
        await notifier.async_send_discovery()

    assert aioclient_mock.call_count == 1
    assert json.loads(aioclient_mock.mock_calls[0][2]._value) == {"ts": now, "payload": {"user_id": user_id}}
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {token}"
    assert "yandex_smart_home/" in aioclient_mock.mock_calls[0][3]["User-Agent"]
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/state",
        status=202,
        json={"request_id": REQ_ID, "status": "ok"},
    )
    await notifier._pending.async_add(
        [ButtonPressCustomEventProperty(hass, entry_data, {}, "btn", Template("click", hass))],
        [],
    )

    with patch("time.time", return_value=now):
        await notifier._async_report_states()

    await hass.async_block_till_done()
    assert len(caplog.messages) == 1
    assert aioclient_mock.call_count == 1
    assert json.loads(aioclient_mock.mock_calls[0][2]._value) == {
        "ts": now,
        "payload": {
            "devices": [
                {
                    "id": "btn",
                    "properties": [
                        {"type": "devices.properties.event", "state": {"instance": "button", "value": "click"}}
                    ],
                }
            ],
            "user_id": user_id,
        },
    }
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {token}"
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/discovery",
        status=400,
        json={"request_id": REQ_ID, "status": "error", "error_message": "some error"},
    )
    await notifier.async_send_discovery()

    assert aioclient_mock.call_count == 1
    assert caplog.messages[-1] == "State notification request failed: some error"
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/discovery",
        status=400,
        json={"request_id": REQ_ID, "status": "error", "error_code": "some code"},
    )
    await notifier.async_send_discovery()

    assert aioclient_mock.call_count == 1
    assert caplog.messages[-1] == "State notification request failed: some code"
    aioclient_mock.clear_requests()
    caplog.clear()

    aioclient_mock.post(
        f"https://yaha-cloud.ru/api/home_assistant/v2/callback/{platform}/discovery",
        status=500,
        content=b"ERROR",
    )
    await notifier.async_send_discovery()
    assert aioclient_mock.call_count == 1
    assert caplog.messages[-1] == "State notification request failed: ERROR"
    aioclient_mock.clear_requests()
    caplog.clear()

    with patch.object(notifier._session, "post", side_effect=Exception("boo")):
        await notifier.async_send_discovery()
        assert aioclient_mock.call_count == 0
    assert "Unexpected exception" in caplog.messages[-1]


async def test_notifier_report_states(
    hass: HomeAssistant,
    entry_data: MockConfigEntryData,
    mock_call_later: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class MockCapabilityFail(OnOffCapabilityBasic):
        def get_value(self) -> bool | None:
            raise APIError(ResponseCode.INTERNAL_ERROR, "api error cap")

    class MockPropertyFail(TemperatureSensor):
        @property
        def supported(self) -> bool:
            return True

        def get_value(self) -> bool | None:
            raise APIError(ResponseCode.INTERNAL_ERROR, "api error prop")

    notifier = YandexDirectNotifier(hass, entry_data, BASIC_CONFIG, {}, {})
    skill_id = BASIC_CONFIG.skill_id
    user_id = BASIC_CONFIG.user_id
    now = time.time()

    aioclient_mock.post(
        f"https://dialogs.yandex.net/api/v1/skills/{skill_id}/callback/state",
        status=202,
        json={"request_id": REQ_ID, "status": "ok"},
    )

    await notifier._async_report_states()
    assert aioclient_mock.call_count == 0
    assert notifier._unsub_report_states is None

    await notifier._pending.async_add(
        [OnOffCapabilityBasic(hass, entry_data, "switch.on", State("switch.on", "on"))], []
    )
    await notifier._pending.async_add(
        [MockCapabilityFail(hass, entry_data, "switch.fail", State("switch.fail", "on"))], []
    )
    await notifier._pending.async_add(
        [TemperatureSensor(hass, entry_data, "sensor.temperature", State("sensor.temperature", "5"))], []
    )
    await notifier._pending.async_add(
        [HumiditySensor(hass, entry_data, "sensor.temperature", State("sensor.temperature", "5"))], []
    )
    await notifier._pending.async_add(
        [MockPropertyFail(hass, entry_data, "sensor.fail", State("sensor.fail", "5"))], []
    )

    assert notifier._pending.empty is False
    with patch("time.time", return_value=now):
        await notifier._async_report_states()
    await hass.async_block_till_done()
    assert caplog.messages[:2] == ["api error cap", "api error prop"]
    assert aioclient_mock.call_count == 1
    assert notifier._unsub_report_states is None
    request_body = json.loads(aioclient_mock.mock_calls[0][2]._value)
    assert request_body == {
        "payload": {
            "devices": [
                {
                    "capabilities": [
                        {"state": {"instance": "on", "value": True}, "type": "devices.capabilities.on_off"}
                    ],
                    "id": "switch.on",
                },
                {
                    "id": "sensor.temperature",
                    "properties": [
                        {"state": {"instance": "temperature", "value": 5.0}, "type": "devices.properties.float"},
                        {"state": {"instance": "humidity", "value": 5.0}, "type": "devices.properties.float"},
                    ],
                },
            ],
            "user_id": user_id,
        },
        "ts": now,
    }

    with patch.object(notifier._pending, "async_get_all", return_value=notifier._pending._device_states):
        await notifier._pending.async_add(
            [OnOffCapabilityBasic(hass, entry_data, "switch.on", State("switch.on", "on"))], []
        )
        await notifier._async_report_states()
        await hass.async_block_till_done()
        assert notifier._pending.empty is False
        assert notifier._unsub_report_states is not None


async def test_notifier_pending_states(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    ps = PendingStates()
    await ps.async_add([OnOffCapabilityBasic(hass, entry_data, "switch.test", State("switch.test", "on"))], [])
    assert ps._device_states["switch.test"][0].get_value() is True
    await ps.async_add([OnOffCapabilityBasic(hass, entry_data, "switch.test", State("switch.test", "off"))], [])
    assert ps._device_states["switch.test"][0].get_value() is False


async def test_notifier_capability_check_value_change(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    ps = PendingStates()
    cap = get_custom_capability(
        hass,
        entry_data,
        {
            CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: "sensor.empty",
        },
        CapabilityType.RANGE,
        RangeCapabilityInstance.OPEN,
        "foo",
    )
    await _assert_not_empty_list(ps.async_add([cap.new_with_value("5")], []))
    await _assert_empty_list(ps.async_add([cap.new_with_value("5")], [cap.new_with_value("5")]))
    await _assert_not_empty_list(ps.async_add([cap.new_with_value("5")], [cap.new_with_value("6")]))
    await _assert_not_empty_list(ps.async_add([cap.new_with_value("5")], [cap.new_with_value(STATE_UNAVAILABLE)]))
    await _assert_empty_list(ps.async_add([cap.new_with_value(STATE_UNAVAILABLE)], [cap.new_with_value("5")]))


@pytest.mark.parametrize("instance", FloatPropertyInstance.__members__.values())
async def test_notifier_float_property_check_value_change(
    hass: HomeAssistant, entry_data: MockConfigEntryData, instance: FloatPropertyInstance
) -> None:
    ps = PendingStates()
    prop = get_custom_property(hass, entry_data, {CONF_ENTITY_PROPERTY_TYPE: instance}, "sensor.foo")
    assert prop
    await _assert_not_empty_list(ps.async_add([prop.new_with_value("5")], []))
    await _assert_empty_list(ps.async_add([prop.new_with_value("5")], [prop.new_with_value("5")]))
    await _assert_not_empty_list(ps.async_add([prop.new_with_value("5")], [prop.new_with_value("6")]))
    await _assert_not_empty_list(ps.async_add([prop.new_with_value("5")], [prop.new_with_value(STATE_UNAVAILABLE)]))
    await _assert_empty_list(ps.async_add([prop.new_with_value(STATE_UNAVAILABLE)], [prop.new_with_value("5")]))


@pytest.mark.parametrize("instance", EventPropertyInstance.__members__.values())
async def test_notifier_binary_event_property_check_value_change(
    hass: HomeAssistant, entry_data: MockConfigEntryData, instance: EventPropertyInstance
) -> None:
    if instance in [EventPropertyInstance.BUTTON, EventPropertyInstance.VIBRATION]:
        return

    a_value, b_value = "on", "off"
    if instance == EventPropertyInstance.FOOD_LEVEL:
        a_value, b_value = "normal", "low"

    ps = PendingStates()
    prop = get_custom_property(hass, entry_data, {CONF_ENTITY_PROPERTY_TYPE: instance}, "binary_sensor.foo")
    assert prop
    await _assert_empty_list(ps.async_add([prop.new_with_value(a_value)], []))
    await _assert_empty_list(ps.async_add([prop.new_with_value(a_value)], [prop.new_with_value(a_value)]))
    await _assert_not_empty_list(ps.async_add([prop.new_with_value(a_value)], [prop.new_with_value(b_value)]))
    await _assert_empty_list(ps.async_add([prop.new_with_value(a_value)], [prop.new_with_value(STATE_UNAVAILABLE)]))
    await _assert_empty_list(ps.async_add([prop.new_with_value(STATE_UNAVAILABLE)], [prop.new_with_value(a_value)]))


@pytest.mark.parametrize(
    "instance,v", [(EventPropertyInstance.BUTTON, "click"), (EventPropertyInstance.VIBRATION, "on")]
)
async def test_notifier_reactive_event_property_check_value_change(
    hass: HomeAssistant, entry_data: MockConfigEntryData, instance: str, v: str
) -> None:
    ps = PendingStates()
    prop = get_custom_property(hass, entry_data, {CONF_ENTITY_PROPERTY_TYPE: instance}, "binary_sensor.foo")
    assert prop
    await _assert_not_empty_list(ps.async_add([prop.new_with_value(v)], []))
    await _assert_empty_list(ps.async_add([prop.new_with_value(v)], [prop.new_with_value(v)]))
    await _assert_empty_list(ps.async_add([prop.new_with_value("foo")], []))
    await _assert_not_empty_list(ps.async_add([prop.new_with_value(v)], [prop.new_with_value("off")]))
    await _assert_not_empty_list(ps.async_add([prop.new_with_value(v)], [prop.new_with_value(STATE_UNAVAILABLE)]))
    await _assert_empty_list(ps.async_add([prop.new_with_value(STATE_UNAVAILABLE)], [prop.new_with_value(v)]))


async def test_notifier_event_platform_property_check_value_change(
    hass: HomeAssistant, entry_data: MockConfigEntryData
) -> None:
    ps = PendingStates()
    cls = ButtonPressEventPlatformCustomProperty

    await _assert_not_empty_list(
        ps.async_add(
            [cls(hass, entry_data, "foo", State("event.foo", STATE_UNKNOWN, {ATTR_EVENT_TYPE: "click"}))],
            [],
        )
    )
    await _assert_not_empty_list(
        ps.async_add(
            [cls(hass, entry_data, "foo", State("event.foo", "foo", {ATTR_EVENT_TYPE: "click"}))],
            [cls(hass, entry_data, "foo", State("event.foo", "bar", {ATTR_EVENT_TYPE: "click"}))],
        )
    )

    await _assert_empty_list(
        ps.async_add(
            [cls(hass, entry_data, "foo", State("event.foo", STATE_UNKNOWN, {ATTR_EVENT_TYPE: "foo"}))],
            [],
        )
    )
    await _assert_empty_list(
        ps.async_add(
            [cls(hass, entry_data, "foo", State("event.foo", "bar", {ATTR_EVENT_TYPE: "click"}))],
            [cls(hass, entry_data, "foo", State("event.foo", "bar", {ATTR_EVENT_TYPE: "click"}))],
        )
    )
    await _assert_empty_list(
        ps.async_add(
            [cls(hass, entry_data, "foo", State("event.foo", "bar", {ATTR_EVENT_TYPE: "click"}))],
            [cls(hass, entry_data, "foo", State("event.foo", "bar", {ATTR_EVENT_TYPE: "double_click"}))],
        )
    )
