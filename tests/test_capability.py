from typing import Any, cast
from unittest.mock import patch

from homeassistant import core
from homeassistant.components import demo
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.setup import async_setup_component

from custom_components.yandex_smart_home.capability import STATE_CAPABILITIES_REGISTRY, StateCapability
from custom_components.yandex_smart_home.capability_custom import OnOffCapability
from custom_components.yandex_smart_home.const import CONF_SLOW
from custom_components.yandex_smart_home.device import Device
from custom_components.yandex_smart_home.entry_data import ConfigEntryData
from custom_components.yandex_smart_home.schema import (
    CapabilityInstance,
    CapabilityType,
    OnOffCapabilityInstance,
    OnOffCapabilityInstanceActionState,
)
from tests import MockConfigEntryData


def get_capabilities(
    hass: HomeAssistant,
    entry_data: ConfigEntryData,
    state: State,
    capability_type: CapabilityType,
    instance: CapabilityInstance,
) -> list[StateCapability[Any]]:
    caps = []

    for CapabilityT in STATE_CAPABILITIES_REGISTRY:
        capability = CapabilityT(hass, entry_data, state.entity_id, state)

        if capability.type != capability_type or capability.instance != instance:
            continue

        if capability.supported:
            caps.append(capability)

    return caps


def get_exact_one_capability(
    hass: HomeAssistant,
    entry_data: ConfigEntryData,
    state: State,
    capability_type: CapabilityType,
    instance: CapabilityInstance,
) -> StateCapability[Any]:
    caps = get_capabilities(hass, entry_data, state, capability_type, instance)
    assert len(caps) == 1
    return caps[0]


def assert_exact_one_capability(
    hass: HomeAssistant,
    entry_data: ConfigEntryData,
    state: State,
    capability_type: CapabilityType,
    instance: CapabilityInstance,
) -> None:
    assert len(get_capabilities(hass, entry_data, state, capability_type, instance)) == 1


def assert_no_capabilities(
    hass: HomeAssistant,
    entry_data: ConfigEntryData,
    state: State,
    capability_type: CapabilityType,
    instance: CapabilityInstance,
) -> None:
    assert len(get_capabilities(hass, entry_data, state, capability_type, instance)) == 0


async def test_capability_demo_platform(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [
            Platform.BUTTON,
            Platform.CLIMATE,
            Platform.COVER,
            Platform.FAN,
            Platform.HUMIDIFIER,
            Platform.LIGHT,
            Platform.LOCK,
            Platform.MEDIA_PLAYER,
            Platform.REMOTE,
            Platform.SWITCH,
        ],
    ):
        await async_setup_component(hass, core.DOMAIN, {})
        await async_setup_component(hass, demo.DOMAIN, {})
        await hass.async_block_till_done()

    # for x in sorted(hass.states.async_all(), key=lambda e: e.entity_id):
    #     d = Device(hass, entry_data, x.entity_id, x)
    #     l = list((c.type.value, c.instance.value) for c in d.get_capabilities())
    #     print(f"state = hass.states.get('{x.entity_id}')")
    #     print(f"assert state")
    #     print(f"device = Device(hass, entry_data, state.entity_id, state)")
    #     if d.type is None:
    #         print(f"assert device.type is None")
    #     else:
    #         print(f"assert device.type == '{d.type.value}'")
    #     print(f"capabilities = list((c.type, c.instance) for c in device.get_capabilities())")
    #     print(f"assert capabilities == {l}")
    #     print()

    state = hass.states.get("button.push")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.other"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("climate.ecobee")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.thermostat"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "thermostat"),
        ("devices.capabilities.mode", "swing"),
        ("devices.capabilities.mode", "program"),
        ("devices.capabilities.mode", "fan_speed"),
        ("devices.capabilities.on_off", "on"),
    ]

    state = hass.states.get("climate.heatpump")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.thermostat"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "thermostat"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "temperature"),
    ]

    state = hass.states.get("climate.hvac")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.thermostat"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "thermostat"),
        ("devices.capabilities.mode", "swing"),
        ("devices.capabilities.mode", "fan_speed"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "temperature"),
    ]

    state = hass.states.get("cover.garage_door")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("cover.hall_window")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "open"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("cover.kitchen_window")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on"), ("devices.capabilities.toggle", "pause")]

    state = hass.states.get("cover.living_room_window")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "open"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("cover.pergola_roof")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("fan.ceiling_fan")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.ventilation.fan"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.mode", "fan_speed"), ("devices.capabilities.on_off", "on")]

    state = hass.states.get("fan.living_room_fan")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.ventilation.fan"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "fan_speed"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.toggle", "oscillation"),
    ]

    state = hass.states.get("fan.percentage_full_fan")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.ventilation.fan"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "fan_speed"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.toggle", "oscillation"),
    ]

    state = hass.states.get("fan.percentage_limited_fan")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.ventilation.fan"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.mode", "fan_speed"), ("devices.capabilities.on_off", "on")]

    state = hass.states.get("fan.preset_only_limited_fan")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.ventilation.fan"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.mode", "fan_speed"), ("devices.capabilities.on_off", "on")]

    state = hass.states.get("humidifier.dehumidifier")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.humidifier"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on"), ("devices.capabilities.range", "humidity")]

    state = hass.states.get("humidifier.humidifier")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.humidifier"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on"), ("devices.capabilities.range", "humidity")]

    state = hass.states.get("humidifier.hygrostat")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.humidifier"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "program"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "humidity"),
    ]

    state = hass.states.get("light.bed_light")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.light"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.color_setting", "base"),
        ("devices.capabilities.color_setting", "rgb"),
        ("devices.capabilities.color_setting", "temperature_k"),
        ("devices.capabilities.color_setting", "scene"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "brightness"),
    ]

    state = hass.states.get("light.ceiling_lights")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.light"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.color_setting", "base"),
        ("devices.capabilities.color_setting", "rgb"),
        ("devices.capabilities.color_setting", "temperature_k"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "brightness"),
    ]

    state = hass.states.get("light.entrance_color_white_lights")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.light"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.color_setting", "base"),
        ("devices.capabilities.color_setting", "rgb"),
        ("devices.capabilities.color_setting", "temperature_k"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "brightness"),
    ]

    state = hass.states.get("light.kitchen_lights")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.light"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.color_setting", "base"),
        ("devices.capabilities.color_setting", "rgb"),
        ("devices.capabilities.color_setting", "temperature_k"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "brightness"),
    ]

    state = hass.states.get("light.living_room_rgbww_lights")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.light"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.color_setting", "base"),
        ("devices.capabilities.color_setting", "rgb"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "brightness"),
        ("devices.capabilities.range", "volume"),
        ("devices.capabilities.range", "open"),
    ]

    state = hass.states.get("light.office_rgbw_lights")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.light"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.color_setting", "base"),
        ("devices.capabilities.color_setting", "rgb"),
        ("devices.capabilities.color_setting", "temperature_k"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "brightness"),
        ("devices.capabilities.range", "volume"),
    ]

    state = hass.states.get("lock.front_door")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("lock.kitchen_door")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("lock.openable_lock")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("lock.poorly_installed_door")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.openable"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("media_player.bedroom")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "volume"),
        ("devices.capabilities.range", "channel"),
        ("devices.capabilities.toggle", "mute"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("media_player.browse")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == []

    state = hass.states.get("media_player.group")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "volume"),
        ("devices.capabilities.range", "channel"),
        ("devices.capabilities.toggle", "mute"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("media_player.kitchen")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "volume"),
        ("devices.capabilities.range", "channel"),
        ("devices.capabilities.toggle", "mute"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("media_player.living_room")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "volume"),
        ("devices.capabilities.range", "channel"),
        ("devices.capabilities.toggle", "mute"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("media_player.lounge_room")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device.tv"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.mode", "input_source"),
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "channel"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("media_player.walkman")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.media_device"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [
        ("devices.capabilities.on_off", "on"),
        ("devices.capabilities.range", "volume"),
        ("devices.capabilities.range", "channel"),
        ("devices.capabilities.toggle", "mute"),
        ("devices.capabilities.toggle", "pause"),
    ]

    state = hass.states.get("remote.remote_one")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.switch"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("remote.remote_two")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.switch"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("switch.ac")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.socket"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("switch.decorative_lights")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.switch"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == [("devices.capabilities.on_off", "on")]

    state = hass.states.get("zone.home")
    assert state
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == "devices.types.other"
    capabilities = list((c.type, c.instance) for c in device.get_capabilities())
    assert capabilities == []


async def test_capability_service_call(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state_normal = State("switch.normal", STATE_ON)
    state_slow_true = State("switch.slow_true", STATE_ON)
    state_slow_false = State("switch.slow_false", STATE_ON)

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_slow_false.entity_id: {
                CONF_SLOW: False,
            },
            state_slow_true.entity_id: {
                CONF_SLOW: True,
            },
        },
    )

    cap_normal = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_normal, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    cap_slow_false = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_slow_false, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    cap_slow_true = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_slow_true, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    with patch("homeassistant.core.ServiceRegistry.async_call") as mock:
        for cap in (cap_normal, cap_slow_false, cap_slow_true):
            await cap.set_instance_state(
                Context(), OnOffCapabilityInstanceActionState(instance=OnOffCapabilityInstance.ON, value=True)
            )
    assert mock.call_args_list[0].kwargs["blocking"] is True
    assert mock.call_args_list[1].kwargs["blocking"] is True
    assert mock.call_args_list[2].kwargs["blocking"] is False
