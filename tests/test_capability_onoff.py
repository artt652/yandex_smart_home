from typing import cast

from homeassistant.components import (
    automation,
    button,
    climate,
    cover,
    fan,
    group,
    input_boolean,
    input_button,
    light,
    lock,
    media_player,
    remote,
    scene,
    script,
    switch,
    vacuum,
    valve,
    water_heater,
)
from homeassistant.components.climate import HVACMode
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.components.valve import ValveEntityFeature
from homeassistant.components.water_heater import WaterHeaterEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    CONF_SERVICE,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_VALVE,
    SERVICE_LOCK,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_VALVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_UNLOCK,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, Context, HomeAssistant, State
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.yandex_smart_home.backports import LockState, VacuumActivity
from custom_components.yandex_smart_home.capability_onoff import OnOffCapability
from custom_components.yandex_smart_home.const import CONF_STATE_UNKNOWN, CONF_TURN_OFF, CONF_TURN_ON
from custom_components.yandex_smart_home.helpers import ActionNotAllowed, APIError
from custom_components.yandex_smart_home.schema import (
    CapabilityType,
    OnOffCapabilityInstance,
    OnOffCapabilityInstanceActionState,
    ResponseCode,
)

from . import MockConfigEntryData
from .test_capability import (
    assert_exact_one_capability,
    assert_no_capabilities,
    get_capabilities,
    get_exact_one_capability,
)

ACTION_STATE_ON = OnOffCapabilityInstanceActionState(instance=OnOffCapabilityInstance.ON, value=True)
ACTION_STATE_OFF = OnOffCapabilityInstanceActionState(instance=OnOffCapabilityInstance.ON, value=False)


@pytest.mark.parametrize(
    "state_domain,service_domain",
    [
        (automation.DOMAIN, automation.DOMAIN),
        (input_boolean.DOMAIN, input_boolean.DOMAIN),
        (group.DOMAIN, HA_DOMAIN),
        (fan.DOMAIN, fan.DOMAIN),
        (switch.DOMAIN, switch.DOMAIN),
        (light.DOMAIN, light.DOMAIN),
    ],
)
async def test_capability_onoff_simple(
    hass: HomeAssistant, entry_data: MockConfigEntryData, state_domain: str, service_domain: str
) -> None:
    state_on = State(f"{state_domain}.test", STATE_ON)
    cap_on = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_on, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap_on.retrievable is True
    assert cap_on.get_value() is True
    assert cap_on.parameters is None

    on_calls = async_mock_service(hass, service_domain, SERVICE_TURN_ON)
    await cap_on.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: f"{state_domain}.test"}

    off_calls = async_mock_service(hass, service_domain, SERVICE_TURN_OFF)
    await cap_on.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: f"{state_domain}.test"}

    state_off = State(f"{state_domain}.test", STATE_OFF)
    cap_off = get_exact_one_capability(hass, entry_data, state_off, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON)
    assert cap_off.get_value() is False

    entry_data = MockConfigEntryData(hass, entity_config={f"{state_domain}.test": {CONF_STATE_UNKNOWN: True}})
    state = State(f"{state_domain}.test", STATE_ON)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is False
    assert cap.parameters
    assert cap.parameters.dict() == {"split": True}


@pytest.mark.parametrize(
    "domain,initial_state,service",
    [
        (script.DOMAIN, STATE_OFF, SERVICE_TURN_ON),
        (scene.DOMAIN, STATE_UNKNOWN, SERVICE_TURN_ON),
        (button.DOMAIN, STATE_UNKNOWN, button.SERVICE_PRESS),
        (input_button.DOMAIN, STATE_UNKNOWN, input_button.SERVICE_PRESS),
    ],
)
async def test_capability_onoff_only_on(
    hass: HomeAssistant, entry_data: MockConfigEntryData, domain: str, initial_state: str, service: str
) -> None:
    state = State(f"{domain}.test", initial_state)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap.retrievable is False
    assert cap.parameters is None
    assert cap.get_value() is None

    on_calls = async_mock_service(hass, domain, service)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)

    if domain == script.DOMAIN:
        await hass.async_block_till_done()

    assert len(on_calls) == 2
    assert on_calls[0].data == {ATTR_ENTITY_ID: f"{domain}.test"}
    assert on_calls[1].data == {ATTR_ENTITY_ID: f"{domain}.test"}


async def test_capability_onoff_cover(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state_open = State("cover.test", STATE_OPEN, attributes={ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION})
    cap_open = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_open, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap_open.retrievable is True
    assert cap_open.get_value() is True
    assert cap_open.parameters is None

    on_calls = async_mock_service(hass, cover.DOMAIN, SERVICE_OPEN_COVER)
    await cap_open.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "cover.test"}

    off_calls = async_mock_service(hass, cover.DOMAIN, SERVICE_CLOSE_COVER)
    await cap_open.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "cover.test"}

    for state in [STATE_CLOSED, STATE_CLOSING, STATE_OPENING]:
        state_other = State("cover.test", state, attributes={ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION})
        cap = cast(
            OnOffCapability,
            get_exact_one_capability(hass, entry_data, state_other, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
        )
        assert cap.get_value() is False

    state_no_features = State("cover.test", STATE_OPEN)
    cap_no_features = cast(
        OnOffCapability,
        get_exact_one_capability(
            hass, entry_data, state_no_features, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON
        ),
    )
    assert cap_no_features.retrievable is True
    assert cap_no_features.get_value() is True
    assert cap_no_features.parameters is None

    entry_data = MockConfigEntryData(hass, entity_config={"cover.test": {CONF_STATE_UNKNOWN: True}})
    state_binary = State("cover.test", STATE_OPEN)
    cap_binary = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_binary, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap_binary.retrievable is False
    assert cap_binary.parameters
    assert cap_binary.parameters.dict() == {"split": True}


async def test_capability_onoff_valve(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state_open = State("valve.test", STATE_OPEN, attributes={ATTR_SUPPORTED_FEATURES: ValveEntityFeature.SET_POSITION})
    cap_open = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_open, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap_open.retrievable is True
    assert cap_open.get_value() is True
    assert cap_open.parameters is None

    on_calls = async_mock_service(hass, valve.DOMAIN, SERVICE_OPEN_VALVE)
    await cap_open.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: "valve.test"}

    off_calls = async_mock_service(hass, valve.DOMAIN, SERVICE_CLOSE_VALVE)
    await cap_open.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: "valve.test"}

    for state in [STATE_CLOSED, STATE_CLOSING, STATE_OPENING]:
        state_other = State("valve.test", state, attributes={ATTR_SUPPORTED_FEATURES: ValveEntityFeature.SET_POSITION})
        cap = cast(
            OnOffCapability,
            get_exact_one_capability(hass, entry_data, state_other, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
        )
        assert cap.get_value() is False

    state_no_features = State("valve.test", STATE_OPEN)
    cap_no_features = cast(
        OnOffCapability,
        get_exact_one_capability(
            hass, entry_data, state_no_features, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON
        ),
    )
    assert cap_no_features.retrievable is True
    assert cap_no_features.get_value() is True
    assert cap_no_features.parameters is None


async def test_capability_onoff_remote(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State("remote.test", STATE_ON)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.reportable is False
    assert cap.retrievable is False
    assert cap.parameters
    assert cap.parameters.as_dict() == {"split": True}
    assert cap.get_value() is None

    on_calls = async_mock_service(hass, remote.DOMAIN, SERVICE_TURN_ON)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    await hass.async_block_till_done()
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}

    off_calls = async_mock_service(hass, remote.DOMAIN, SERVICE_TURN_OFF)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    await hass.async_block_till_done()
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}


async def test_capability_onoff_media_player(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    default_entry_data = entry_data
    state = State("media_player.simple", STATE_ON)
    assert_no_capabilities(hass, default_entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON)

    state = State("media_player.test", STATE_ON)
    entry_data = MockConfigEntryData(hass, entity_config={state.entity_id: {"features": ["turn_on_off"]}})
    assert_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON)

    state = State("media_player.only_on", STATE_ON, {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_OFF})
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, default_entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is True
    assert cap.parameters is None

    entry_data = MockConfigEntryData(hass, entity_config={"media_player.test": {CONF_STATE_UNKNOWN: True}})
    state_binary = State("media_player.test", STATE_OFF, {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_OFF})
    cap_binary = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_binary, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap_binary.retrievable is False
    assert cap_binary.parameters
    assert cap_binary.parameters.dict() == {"split": True}

    state = State(
        "media_player.test",
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF},
    )
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, default_entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is True
    assert cap.get_value() is True
    assert cap.parameters is None

    on_calls = async_mock_service(hass, media_player.DOMAIN, SERVICE_TURN_ON)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}

    off_calls = async_mock_service(hass, media_player.DOMAIN, SERVICE_TURN_OFF)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}

    state.state = STATE_OFF
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, default_entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.get_value() is False


async def test_capability_onoff_lock(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State("lock.test", LockState.UNLOCKED)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap.retrievable is True
    assert cap.get_value() is True
    assert cap.parameters is None

    on_calls = async_mock_service(hass, lock.DOMAIN, SERVICE_UNLOCK)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}

    off_calls = async_mock_service(hass, lock.DOMAIN, SERVICE_LOCK)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}

    states = [LockState.UNLOCKING, LockState.LOCKING]
    locked_state = LockState.LOCKED

    for s in states:
        state_other = State("lock.test", s)
        cap = cast(
            OnOffCapability,
            get_exact_one_capability(hass, entry_data, state_other, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
        )

        assert cap.get_value() is False

    state.state = locked_state
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    assert cap.get_value() is False

    entry_data = MockConfigEntryData(hass, entity_config={"lock.test": {CONF_STATE_UNKNOWN: True}})
    state = State("lock.test", STATE_ON)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is False
    assert cap.parameters
    assert cap.parameters.dict() == {"split": True}


async def test_capability_onoff_vacuum(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    for s in [STATE_ON, VacuumActivity.CLEANING]:
        state = State(
            "vacuum.test",
            s,
            attributes={ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.START | VacuumEntityFeature.STOP},
        )
        cap = cast(
            OnOffCapability,
            get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
        )
        assert cap.get_value() is True
        assert cap.retrievable is True
        assert cap.parameters is None

    for s in list(VacuumActivity) + [STATE_OFF]:
        if s == VacuumActivity.CLEANING:
            continue
        state = State(
            "vacuum.test",
            s,
            attributes={ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.START | VacuumEntityFeature.STOP},
        )
        cap = cast(
            OnOffCapability,
            get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
        )

        assert cap.get_value() is False

    entry_data = MockConfigEntryData(hass, entity_config={"vacuum.test": {CONF_STATE_UNKNOWN: True}})
    state = State(
        "vacuum.test",
        STATE_ON,
        attributes={ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.START | VacuumEntityFeature.STOP},
    )
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is False
    assert cap.parameters
    assert cap.parameters.dict() == {"split": True}


@pytest.mark.parametrize(
    "features,supported",
    [
        (0, False),
        (VacuumEntityFeature.START, False),
        (VacuumEntityFeature.START | VacuumEntityFeature.RETURN_HOME, True),
        (VacuumEntityFeature.START | VacuumEntityFeature.STOP, True),
        (VacuumEntityFeature.TURN_ON, False),
        (VacuumEntityFeature.TURN_ON | VacuumEntityFeature.TURN_OFF, True),
    ],
)
async def test_capability_onoff_vacuum_supported(
    hass: HomeAssistant, entry_data: MockConfigEntryData, features: int, supported: bool
) -> None:
    state = State("vacuum.test", STATE_ON, {ATTR_SUPPORTED_FEATURES: features})
    assert (
        bool(get_capabilities(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON)) == supported
    )


@pytest.mark.parametrize(
    "features,service",
    [
        (VacuumEntityFeature.START | VacuumEntityFeature.RETURN_HOME, vacuum.SERVICE_START),
        (
            VacuumEntityFeature.START | VacuumEntityFeature.STOP | VacuumEntityFeature.RETURN_HOME,
            vacuum.SERVICE_START,
        ),
        (VacuumEntityFeature.START | VacuumEntityFeature.STOP, vacuum.SERVICE_START),
        (VacuumEntityFeature.TURN_ON | VacuumEntityFeature.TURN_OFF, SERVICE_TURN_ON),
    ],
)
async def test_capability_onoff_vacuum_turn_on(
    hass: HomeAssistant, entry_data: MockConfigEntryData, features: int, service: str
) -> None:
    state = State("vacuum.test", STATE_ON, {ATTR_SUPPORTED_FEATURES: features})
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    on_calls = async_mock_service(hass, vacuum.DOMAIN, service)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}


@pytest.mark.parametrize(
    "features,service",
    [
        (VacuumEntityFeature.START | VacuumEntityFeature.RETURN_HOME, vacuum.SERVICE_RETURN_TO_BASE),
        (
            VacuumEntityFeature.START | VacuumEntityFeature.STOP | VacuumEntityFeature.RETURN_HOME,
            vacuum.SERVICE_RETURN_TO_BASE,
        ),
        (VacuumEntityFeature.START | VacuumEntityFeature.STOP, vacuum.SERVICE_STOP),
        (VacuumEntityFeature.TURN_ON | VacuumEntityFeature.TURN_OFF, SERVICE_TURN_OFF),
    ],
)
async def test_capability_onoff_vacuum_turn_off(
    hass: HomeAssistant, entry_data: MockConfigEntryData, features: int, service: str
) -> None:
    state = State("vacuum.test", STATE_ON, {ATTR_SUPPORTED_FEATURES: features})
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    off_calls = async_mock_service(hass, vacuum.DOMAIN, service)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}


async def test_capability_onoff_climate(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    for s in climate.HVAC_MODES:
        if s == HVACMode.OFF:
            continue

        state = State("climate.test", s)
        cap = cast(
            OnOffCapability,
            get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
        )
        assert cap.get_value() is True
        assert cap.retrievable is True
        assert cap.parameters is None

    state = State("climate.test", STATE_OFF)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.get_value() is False

    off_calls = async_mock_service(hass, climate.DOMAIN, SERVICE_TURN_OFF)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}

    entry_data = MockConfigEntryData(hass, entity_config={"climate.test": {CONF_STATE_UNKNOWN: True}})
    state = State("climate.test", STATE_ON)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is False
    assert cap.parameters
    assert cap.parameters.dict() == {"split": True}


@pytest.mark.parametrize(
    "hvac_modes,service,service_hvac_mode",
    [
        ([], SERVICE_TURN_ON, None),
        ([HVACMode.COOL], SERVICE_TURN_ON, None),
        ([HVACMode.AUTO, HVACMode.COOL], climate.SERVICE_SET_HVAC_MODE, HVACMode.AUTO),
        (
            [HVACMode.HEAT_COOL, HVACMode.COOL],
            climate.SERVICE_SET_HVAC_MODE,
            HVACMode.HEAT_COOL,
        ),
        (
            [HVACMode.HEAT_COOL, HVACMode.AUTO, HVACMode.COOL],
            climate.SERVICE_SET_HVAC_MODE,
            HVACMode.HEAT_COOL,
        ),
    ],
)
async def test_capability_onoff_climate_turn_on(
    hass: HomeAssistant,
    entry_data: MockConfigEntryData,
    hvac_modes: list[HVACMode],
    service: str,
    service_hvac_mode: str,
) -> None:
    state = State("climate.test", HVACMode.COOL, {climate.ATTR_HVAC_MODES: hvac_modes})
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    on_calls = async_mock_service(hass, climate.DOMAIN, service)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data[ATTR_ENTITY_ID] == state.entity_id
    if service_hvac_mode:
        assert on_calls[0].data[climate.ATTR_HVAC_MODE] == service_hvac_mode


async def test_capability_onoff_custom_service(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state_media = State("media_player.test", STATE_ON)
    assert_no_capabilities(hass, entry_data, state_media, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON)

    state_switch = State("switch.test", STATE_ON)
    cap_switch = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_switch, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )

    on_calls = async_mock_service(hass, switch.DOMAIN, switch.SERVICE_TURN_ON)
    await cap_switch.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data == {ATTR_ENTITY_ID: state_switch.entity_id}

    off_calls = async_mock_service(hass, switch.DOMAIN, switch.SERVICE_TURN_OFF)
    await cap_switch.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state_switch.entity_id}

    service_domain = "test"
    turn_on_service = "turn_on"
    turn_off_service = "turn_off"
    turn_on_off_entity_id = "switch.test"

    state_switch = State("switch.test", STATE_ON)
    state_media = State("media_player.test", STATE_ON)
    state_vacuum = State("vacuum.test", STATE_ON)
    state_lock = State("lock.test", STATE_OFF)
    state_water_heater = State(
        "water_heater.test", STATE_ON, {ATTR_SUPPORTED_FEATURES: WaterHeaterEntityFeature.ON_OFF}
    )
    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_media.entity_id: {
                CONF_TURN_ON: {
                    CONF_SERVICE: f"{service_domain}.{turn_on_service}",
                    CONF_ENTITY_ID: turn_on_off_entity_id,
                },
                CONF_TURN_OFF: {
                    CONF_SERVICE: f"{service_domain}.{turn_off_service}",
                    CONF_ENTITY_ID: turn_on_off_entity_id,
                },
            },
            state_switch.entity_id: {
                CONF_TURN_ON: {
                    CONF_SERVICE: f"{service_domain}.{turn_on_service}",
                    CONF_ENTITY_ID: turn_on_off_entity_id,
                },
                CONF_TURN_OFF: {
                    CONF_SERVICE: f"{service_domain}.{turn_off_service}",
                    CONF_ENTITY_ID: turn_on_off_entity_id,
                },
            },
            state_vacuum.entity_id: {
                CONF_TURN_ON: {
                    CONF_SERVICE: f"{service_domain}.{turn_on_service}",
                    CONF_ENTITY_ID: turn_on_off_entity_id,
                }
            },
            state_lock.entity_id: {CONF_TURN_ON: False},
            state_water_heater.entity_id: {CONF_TURN_OFF: False},
        },
    )
    cap_media = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_media, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    cap_switch = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_switch, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    cap_lock = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state_lock, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    cap_water_heater = cast(
        OnOffCapability,
        get_exact_one_capability(
            hass, entry_data, state_water_heater, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON
        ),
    )
    assert_exact_one_capability(hass, entry_data, state_vacuum, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON)

    on_calls = async_mock_service(hass, service_domain, turn_on_service)
    await cap_media.set_instance_state(Context(), ACTION_STATE_ON)
    await cap_switch.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 2
    assert on_calls[0].data == {ATTR_ENTITY_ID: [turn_on_off_entity_id]}
    assert on_calls[1].data == {ATTR_ENTITY_ID: [turn_on_off_entity_id]}

    off_calls = async_mock_service(hass, service_domain, turn_off_service)
    await cap_media.set_instance_state(Context(), ACTION_STATE_OFF)
    await cap_switch.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 2
    assert off_calls[0].data == {ATTR_ENTITY_ID: [turn_on_off_entity_id]}
    assert off_calls[1].data == {ATTR_ENTITY_ID: [turn_on_off_entity_id]}

    lock_off_calls = async_mock_service(hass, "lock", "lock")
    with pytest.raises(ActionNotAllowed):
        await cap_lock.set_instance_state(Context(), ACTION_STATE_ON)
    await cap_lock.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(lock_off_calls) == 1

    water_heater_on_calls = async_mock_service(hass, "water_heater", "turn_on")
    with pytest.raises(ActionNotAllowed):
        await cap_water_heater.set_instance_state(Context(), ACTION_STATE_OFF)
    await cap_water_heater.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(water_heater_on_calls) == 1


async def test_capability_onoff_water_heater(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State("water_heater.test", STATE_ON)

    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is True
    assert cap.parameters is None
    assert cap.get_value() is True

    state = State("water_heater.test", STATE_OFF, {ATTR_SUPPORTED_FEATURES: WaterHeaterEntityFeature.ON_OFF})
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.get_value() is False

    on_calls = async_mock_service(hass, water_heater.DOMAIN, SERVICE_TURN_ON)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(on_calls) == 1
    assert on_calls[0].data[ATTR_ENTITY_ID] == state.entity_id

    off_calls = async_mock_service(hass, water_heater.DOMAIN, SERVICE_TURN_OFF)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(off_calls) == 1
    assert off_calls[0].data[ATTR_ENTITY_ID] == state.entity_id

    entry_data = MockConfigEntryData(hass, entity_config={"water_heater.test": {CONF_STATE_UNKNOWN: True}})
    state = State("water_heater.test", STATE_ON)
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is False
    assert cap.parameters
    assert cap.parameters.dict() == {"split": True}


@pytest.mark.parametrize("op_on", ["on", "On", "ON", "electric", "Boil"])
@pytest.mark.parametrize("op_off", ["off", "Off", "OFF"])
async def test_capability_onoff_water_heater_set_op_mode(
    hass: HomeAssistant, entry_data: MockConfigEntryData, op_on: str, op_off: str
) -> None:
    state = State(
        "water_heater.test",
        op_on,
        {
            ATTR_SUPPORTED_FEATURES: WaterHeaterEntityFeature.OPERATION_MODE,
            water_heater.ATTR_OPERATION_LIST: [op_on, op_off],
            water_heater.ATTR_OPERATION_MODE: op_on,
        },
    )

    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.retrievable is True
    assert cap.parameters is None
    assert cap.get_value() is True

    state = State(
        "water_heater.test",
        op_off,
        {
            ATTR_SUPPORTED_FEATURES: WaterHeaterEntityFeature.OPERATION_MODE,
            water_heater.ATTR_OPERATION_LIST: [op_on, op_off],
            water_heater.ATTR_OPERATION_MODE: op_off,
        },
    )
    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.get_value() is False

    set_mode_calls = async_mock_service(hass, water_heater.DOMAIN, water_heater.SERVICE_SET_OPERATION_MODE)
    await cap.set_instance_state(Context(), ACTION_STATE_ON)
    assert len(set_mode_calls) == 1
    assert set_mode_calls[0].data[ATTR_ENTITY_ID] == state.entity_id
    assert set_mode_calls[0].data[water_heater.ATTR_OPERATION_MODE] == op_on

    set_mode_calls = async_mock_service(hass, water_heater.DOMAIN, water_heater.SERVICE_SET_OPERATION_MODE)
    await cap.set_instance_state(Context(), ACTION_STATE_OFF)
    assert len(set_mode_calls) == 1
    assert set_mode_calls[0].data[ATTR_ENTITY_ID] == state.entity_id
    assert set_mode_calls[0].data[water_heater.ATTR_OPERATION_MODE] == op_off


async def test_capability_onoff_water_heater_set_unsupported_op_mode(
    hass: HomeAssistant, entry_data: MockConfigEntryData
) -> None:
    state = State(
        "water_heater.test",
        "foo",
        {
            ATTR_SUPPORTED_FEATURES: WaterHeaterEntityFeature.OPERATION_MODE,
            water_heater.ATTR_OPERATION_LIST: ["foo", "bar"],
            water_heater.ATTR_OPERATION_MODE: "foo",
        },
    )

    cap = cast(
        OnOffCapability,
        get_exact_one_capability(hass, entry_data, state, CapabilityType.ON_OFF, OnOffCapabilityInstance.ON),
    )
    assert cap.get_value() is True

    for v in [True, False]:
        with pytest.raises(APIError) as e:
            await cap.set_instance_state(
                Context(), OnOffCapabilityInstanceActionState(instance=OnOffCapabilityInstance.ON, value=v)
            )

        assert e.value.code == ResponseCode.NOT_SUPPORTED_IN_CURRENT_MODE
        assert "Unable to determine operation mode " in e.value.message
