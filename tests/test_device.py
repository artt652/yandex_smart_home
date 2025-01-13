from typing import Any
from unittest.mock import PropertyMock, patch

from homeassistant.components import light, media_player
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.demo.light import DemoLight
from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.components.media_player import MediaPlayerDeviceClass, MediaPlayerEntityFeature
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_ROOM,
    CONF_STATE_TEMPLATE,
    CONF_TYPE,
    PERCENTAGE,
    SERVICE_TURN_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.template import Template
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.yandex_smart_home.capability_color import (
    ColorSceneStateCapability,
    ColorSettingCapability,
    ColorTemperatureCapability,
    RGBColorCapability,
)
from custom_components.yandex_smart_home.capability_custom import (
    CustomModeCapability,
    CustomOnOffCapability,
    CustomRangeCapability,
    CustomToggleCapability,
)
from custom_components.yandex_smart_home.capability_mode import InputSourceCapability
from custom_components.yandex_smart_home.capability_onoff import (
    OnOffCapabilityBasic,
    OnOffCapabilityButton,
    OnOffCapabilityMediaPlayer,
)
from custom_components.yandex_smart_home.capability_range import BrightnessCapability, VolumeCapability
from custom_components.yandex_smart_home.capability_toggle import MuteCapability, StateToggleCapability
from custom_components.yandex_smart_home.const import (
    CONF_BACKLIGHT_ENTITY_ID,
    CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID,
    CONF_ENTITY_CUSTOM_MODE_SET_MODE,
    CONF_ENTITY_CUSTOM_MODES,
    CONF_ENTITY_CUSTOM_RANGE_SET_VALUE,
    CONF_ENTITY_CUSTOM_RANGES,
    CONF_ENTITY_CUSTOM_TOGGLE_TURN_OFF,
    CONF_ENTITY_CUSTOM_TOGGLE_TURN_ON,
    CONF_ENTITY_CUSTOM_TOGGLES,
    CONF_ENTITY_MODE_MAP,
    CONF_ENTITY_PROPERTIES,
    CONF_ENTITY_PROPERTY_ATTRIBUTE,
    CONF_ENTITY_PROPERTY_ENTITY,
    CONF_ENTITY_PROPERTY_TYPE,
    CONF_ENTRY_ALIASES,
    DOMAIN,
)
from custom_components.yandex_smart_home.device import BacklightCapability, Device
from custom_components.yandex_smart_home.helpers import APIError
from custom_components.yandex_smart_home.property_custom import (
    ButtonPressCustomEventProperty,
    FoodLevelEventPlatformCustomProperty,
    VoltageCustomFloatProperty,
    get_custom_property,
)
from custom_components.yandex_smart_home.property_event import BatteryLevelStateEvent, OpenStateEventProperty
from custom_components.yandex_smart_home.property_float import (
    BatteryLevelPercentageSensor,
    TemperatureSensor,
    VoltageSensor,
)
from custom_components.yandex_smart_home.schema import (
    DeviceType,
    OnOffCapabilityInstance,
    OnOffCapabilityInstanceAction,
    OnOffCapabilityInstanceActionState,
    RangeCapabilityInstance,
    RangeCapabilityInstanceAction,
    RangeCapabilityInstanceActionState,
    ResponseCode,
    ToggleCapabilityInstance,
    ToggleCapabilityInstanceAction,
    ToggleCapabilityInstanceActionState,
)

from . import MockConfigEntryData, generate_entity_filter


async def test_device_duplicate_capabilities(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    class MockCapability(OnOffCapabilityBasic):
        @property
        def supported(self) -> bool:
            return True

    class MockCapability2(MuteCapability):
        @property
        def supported(self) -> bool:
            return True

    state = State("switch.test", STATE_ON)
    device = Device(hass, entry_data, state.entity_id, state)

    with patch(
        "custom_components.yandex_smart_home.device.STATE_CAPABILITIES_REGISTRY",
        [MockCapability, MockCapability2, MockCapability, MockCapability2],
    ):
        caps = device.get_capabilities()
        assert len(caps) == 2
        assert isinstance(caps[0], MockCapability)
        assert isinstance(caps[1], MockCapability2)


async def test_device_capabilities(hass: HomeAssistant) -> None:
    light = DemoLight(
        "test_light",
        "Light",
        available=True,
        state=True,
    )
    light.hass = hass
    light.entity_id = "light.test"
    light._attr_name = "Light"  # type: ignore[assignment]
    light.async_write_ha_state()

    state_light = hass.states.get("light.test")
    assert state_light
    state_sensor = State("sensor.test", "33")
    state_switch = State("switch.test", "off")

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            light.entity_id: {
                CONF_ENTITY_MODE_MAP: {"dishwashing": {"eco": [""]}},
                CONF_ENTITY_CUSTOM_RANGES: {
                    "humidity": {
                        CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: state_sensor.entity_id,
                        CONF_ENTITY_CUSTOM_RANGE_SET_VALUE: {},
                    }
                },
                CONF_ENTITY_CUSTOM_TOGGLES: {
                    "pause": {
                        CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: state_sensor.entity_id,
                        CONF_ENTITY_CUSTOM_TOGGLE_TURN_ON: {},
                        CONF_ENTITY_CUSTOM_TOGGLE_TURN_OFF: {},
                    }
                },
                CONF_ENTITY_CUSTOM_MODES: {
                    "dishwashing": {
                        CONF_ENTITY_CUSTOM_CAPABILITY_STATE_ENTITY_ID: state_sensor.entity_id,
                        CONF_ENTITY_CUSTOM_MODE_SET_MODE: {},
                    }
                },
            },
            state_switch.entity_id: {CONF_STATE_TEMPLATE: Template("on", hass)},
        },
    )

    device_light = Device(hass, entry_data, state_light.entity_id, state_light)
    assert [type(c) for c in device_light.get_capabilities()] == [
        CustomModeCapability,
        CustomToggleCapability,
        CustomRangeCapability,
        ColorSettingCapability,
        RGBColorCapability,
        ColorTemperatureCapability,
        OnOffCapabilityBasic,
        BrightnessCapability,
    ]

    device_switch = Device(hass, entry_data, state_switch.entity_id, state_switch)
    assert [type(c) for c in device_switch.get_capabilities()] == [CustomOnOffCapability]


async def test_device_capabilities_with_backlight_entity(hass: HomeAssistant) -> None:
    state_light = State(
        "light.backlight",
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: LightEntityFeature.EFFECT,
            light.ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP, ColorMode.RGB],
            light.ATTR_EFFECT_LIST: ["alarm"],
        },
    )
    state_switch = State("switch.test", "off")
    hass.states.async_set(state_light.entity_id, state_light.state, state_light.attributes)
    hass.states.async_set(state_switch.entity_id, state_switch.state, state_switch.attributes)

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_switch.entity_id: {CONF_BACKLIGHT_ENTITY_ID: "light.foo"},
        },
        entity_filter=generate_entity_filter(include_entity_globs=[state_switch.entity_id]),
    )
    device = Device(hass, entry_data, state_switch.entity_id, state_switch)
    assert [type(c) for c in device.get_capabilities()] == [OnOffCapabilityBasic]

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_switch.entity_id: {CONF_BACKLIGHT_ENTITY_ID: state_light.entity_id},
        },
        entity_filter=generate_entity_filter(include_entity_globs=[state_switch.entity_id]),
    )
    device = Device(hass, entry_data, state_switch.entity_id, state_switch)
    assert [type(c) for c in device.get_capabilities()] == [
        OnOffCapabilityBasic,
        ColorSettingCapability,
        RGBColorCapability,
        ColorTemperatureCapability,
        ColorSceneStateCapability,
        BrightnessCapability,
        BacklightCapability,
    ]
    backlight_capability = [c for c in device.get_capabilities() if isinstance(c, BacklightCapability)][0]
    assert backlight_capability.get_value() is True

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_light.entity_id: {CONF_BACKLIGHT_ENTITY_ID: state_light.entity_id},
        },
        entity_filter=generate_entity_filter(include_entity_globs=["*"]),
    )
    device = Device(hass, entry_data, state_light.entity_id, state_light)
    assert [type(c) for c in device.get_capabilities()] == [
        ColorSettingCapability,
        RGBColorCapability,
        ColorTemperatureCapability,
        ColorSceneStateCapability,
        OnOffCapabilityBasic,
        BrightnessCapability,
    ]


async def test_device_disabled_capabilities(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State(
        "media_player.foo",
        STATE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.SELECT_SOURCE,
            media_player.ATTR_INPUT_SOURCE_LIST: ["foo", "bar"],
        },
    )

    device = Device(hass, entry_data, state.entity_id, state)
    assert [type(c) for c in device.get_capabilities()] == [
        InputSourceCapability,
        OnOffCapabilityMediaPlayer,
        VolumeCapability,
        MuteCapability,
    ]

    entry_data = MockConfigEntryData(
        hass,
        entity_filter=generate_entity_filter(include_entity_globs=["*"]),
        entity_config={
            state.entity_id: {
                CONF_ENTITY_CUSTOM_RANGES: {"volume": False},
                CONF_ENTITY_CUSTOM_TOGGLES: {"mute": False},
                CONF_ENTITY_CUSTOM_MODES: {"input_source": False},
            }
        },
    )

    device = Device(hass, entry_data, state.entity_id, state)
    assert [type(c) for c in device.get_capabilities()] == [
        OnOffCapabilityMediaPlayer,
    ]
    assert len(entry_data._get_trackable_templates()) == 0


async def test_device_duplicate_properties(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    class MockProperty(TemperatureSensor):
        @property
        def supported(self) -> bool:
            return True

    class MockPropertyBS(BatteryLevelPercentageSensor):
        @property
        def supported(self) -> bool:
            return True

    class MockPropertyBE(BatteryLevelStateEvent):
        @property
        def supported(self) -> bool:
            return True

    state = State("sensor.test", "33")
    device = Device(hass, entry_data, state.entity_id, state)

    with patch(
        "custom_components.yandex_smart_home.device.STATE_PROPERTIES_REGISTRY",
        [MockProperty, MockPropertyBS, MockProperty, MockPropertyBS, MockPropertyBE],
    ):
        props = device.get_properties()
        assert len(props) == 3
        assert isinstance(props[0], MockProperty)
        assert isinstance(props[1], MockPropertyBS)
        assert isinstance(props[2], MockPropertyBE)


async def test_device_properties(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    state = State(
        "sensor.temp",
        "5",
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    hass.states.async_set(state.entity_id, state.state)
    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state.entity_id: {
                CONF_ENTITY_PROPERTIES: [
                    {CONF_ENTITY_PROPERTY_TYPE: "voltage"},
                    {CONF_ENTITY_PROPERTY_TYPE: "button"},
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "temperature",
                        CONF_ENTITY_PROPERTY_ENTITY: "binary_sensor.foo",
                    },
                    {
                        CONF_ENTITY_PROPERTY_TYPE: "food_level",
                        CONF_ENTITY_PROPERTY_ENTITY: "event.foo",
                    },
                ]
            }
        },
    )
    device = Device(hass, entry_data, state.entity_id, state)
    assert [type(c) for c in device.get_properties()] == [
        VoltageCustomFloatProperty,
        ButtonPressCustomEventProperty,
        FoodLevelEventPlatformCustomProperty,
        TemperatureSensor,
    ]

    state = State(
        "binary_sensor.door",
        STATE_ON,
        attributes={
            ATTR_DEVICE_CLASS: BinarySensorDeviceClass.DOOR,
        },
    )
    device = Device(hass, entry_data, state.entity_id, state)
    assert [type(c) for c in device.get_properties()] == [OpenStateEventProperty]
    assert caplog.messages[-1] == "Unsupported entity binary_sensor.foo for temperature property of sensor.temp"


async def test_device_info(
    hass: HomeAssistant,
    entry_data: MockConfigEntryData,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    state = State("switch.test_1", STATE_ON)
    device_entry = device_registry.async_get_or_create(
        manufacturer="Acme Inc.", identifiers={("test_1", "test_1")}, config_entry_id=config_entry.entry_id
    )
    entity_registry.async_get_or_create("switch", "test", "1", device_id=device_entry.id)
    device = Device(hass, entry_data, state.entity_id, state)
    d = await device.describe()
    assert d
    assert d.id == "switch.test_1"
    assert d.device_info
    assert d.device_info.as_dict() == {"model": "switch.test_1", "manufacturer": "Acme Inc."}

    state = State("switch.test_2", STATE_ON)
    device_entry = device_registry.async_get_or_create(
        manufacturer="Acme Inc.",
        model="Ultra Switch",
        sw_version="57",
        identifiers={("test_2", "test_2")},
        config_entry_id=config_entry.entry_id,
    )
    entity_registry.async_get_or_create(
        "switch",
        "test",
        "2",
        device_id=device_entry.id,
    )
    device = Device(hass, entry_data, state.entity_id, state)
    d = await device.describe()
    assert d
    assert d.id == "switch.test_2"
    assert d.device_info
    assert d.device_info.as_dict() == {
        "manufacturer": "Acme Inc.",
        "model": "Ultra Switch | switch.test_2",
        "sw_version": "57",
    }


async def test_device_name_room(
    hass: HomeAssistant,
    entry_data: MockConfigEntryData,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    area_room = area_registry.async_create("Room")
    bathroom_room = area_registry.async_create("Bathroom", aliases={"foo"})
    area_kitchen = area_registry.async_create("Кухня", aliases={"Кухне"})
    area_closet = area_registry.async_create("Closet", aliases={"Test", "Кладовка", "ббб"})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    state = State("switch.test_1", STATE_ON)
    dev_entry = device_registry.async_get_or_create(
        identifiers={("test_1", "test_1")}, config_entry_id=config_entry.entry_id
    )
    entry = entity_registry.async_get_or_create("switch", "test", "1", device_id=dev_entry.id)
    device = Device(hass, entry_data, state.entity_id, state)
    d = await device.describe()
    assert d
    assert d.id == "switch.test_1"
    assert d.name == "test 1"
    assert d.room is None

    device_registry.async_update_device(dev_entry.id, area_id=area_room.id)
    d = await device.describe()
    assert d
    assert d.room == "Room"

    device_registry.async_update_device(dev_entry.id, area_id=bathroom_room.id)
    d = await device.describe()
    assert d
    assert d.room == "Bathroom"

    entity_registry.async_update_entity(entry.entity_id, area_id=area_kitchen.id)
    d = await device.describe()
    assert d
    assert d.name == "test 1"
    assert d.room == "Кухне"

    entity_registry.async_update_entity(
        entry.entity_id, area_id=area_closet.id, aliases={"foo", "Устройство 2", "апельсин"}
    )
    d = await device.describe()
    assert d
    assert d.name == "Устройство 2"
    assert d.room == "Кладовка"

    entry_data = MockConfigEntryData(hass, entity_config={"switch.test_1": {CONF_NAME: "Имя", CONF_ROOM: "Комната"}})
    device = Device(hass, entry_data, state.entity_id, state)
    d = await device.describe()
    assert d
    assert d.name == "Имя"
    assert d.room == "Комната"


async def test_device_name_room_ignore_aliases(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    area_room = area_registry.async_create("Room")
    area_kitchen = area_registry.async_create("Кухня", aliases={"Ананас", "АлисА: Кухня", "Алиса: Балкон "})
    area_closet = area_registry.async_create("Closet", aliases={"Test", "1", "Кладовка", "ббб"})
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    entry_data = MockConfigEntryData(
        hass,
        entry=MockConfigEntry(domain=DOMAIN, data={}, options={CONF_ENTRY_ALIASES: False}),
    )

    state = State("switch.test_1", STATE_ON)
    dev_entry = device_registry.async_get_or_create(
        identifiers={("test_1", "test_1")}, config_entry_id=config_entry.entry_id
    )
    entry = entity_registry.async_get_or_create("switch", "test", "1", device_id=dev_entry.id)
    device = Device(hass, entry_data, state.entity_id, state)
    d = await device.describe()
    assert d
    assert d.id == "switch.test_1"
    assert d.name == "test 1"
    assert d.room is None

    device_registry.async_update_device(dev_entry.id, area_id=area_room.id)
    d = await device.describe()
    assert d
    assert d.room == "Room"

    entity_registry.async_update_entity(entry.entity_id, area_id=area_kitchen.id)
    d = await device.describe()
    assert d
    assert d.name == "test 1"
    assert d.room == "Балкон"

    entity_registry.async_update_entity(entry.entity_id, area_id=area_closet.id, aliases={"Устройство"})
    d = await device.describe()
    assert d
    assert d.name == "test 1"
    assert d.room == "Closet"

    entity_registry.async_update_entity(
        entry.entity_id, area_id=area_closet.id, aliases={"2", "foo", "Устройство", "апельсин", "Алиса: Устройство"}
    )
    d = await device.describe()
    assert d
    assert d.name == "Устройство"
    assert d.room == "Closet"

    entry_data = MockConfigEntryData(hass, entity_config={"switch.test_1": {CONF_NAME: "Имя", CONF_ROOM: "Комната"}})
    device = Device(hass, entry_data, state.entity_id, state)
    d = await device.describe()
    assert d
    assert d.name == "Имя"
    assert d.room == "Комната"


async def test_device_should_expose(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    device = Device(hass, entry_data, "group.all_locks", State("group.all_locks", STATE_ON))
    assert device.should_expose is False

    device = Device(hass, entry_data, "fake.unsupported", State("fake.unsupported", STATE_ON))
    assert device.should_expose is False

    entry_data = MockConfigEntryData(hass, entity_filter=generate_entity_filter(exclude_entities=["switch.not_expose"]))
    device = Device(hass, entry_data, "switch.test", State("switch.test", STATE_ON))
    assert device.should_expose is True
    device = Device(hass, entry_data, "switch.test", State("switch.test", STATE_UNAVAILABLE))
    assert device.should_expose is False

    device = Device(hass, entry_data, "switch.not_expose", State("switch.not_expose", STATE_ON))
    assert device.should_expose is False


async def test_device_unavaialble(hass: HomeAssistant) -> None:
    state_unavailable = State("sensor.unavailable", STATE_UNAVAILABLE)
    state_on = State("sensor.on", STATE_ON)
    state_switch = State("switch.test", STATE_OFF)
    for s in (state_unavailable, state_on, state_switch):
        hass.states.async_set(s.entity_id, s.state)

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_switch.entity_id: {
                CONF_STATE_TEMPLATE: Template("{{ states('sensor.on') }}", hass),
            }
        },
    )
    device = Device(hass, entry_data, state_switch.entity_id, state_switch)
    assert device.unavailable is False

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            state_switch.entity_id: {
                CONF_STATE_TEMPLATE: Template("{{ states('sensor.unavailable') }}", hass),
            }
        },
    )
    device = Device(hass, entry_data, state_switch.entity_id, state_switch)
    assert device.unavailable is True


async def test_device_should_expose_empty_filters(hass: HomeAssistant) -> None:
    entry_data = MockConfigEntryData(hass, entity_filter=generate_entity_filter())

    device = Device(hass, entry_data, "switch.test", State("switch.test", STATE_ON))
    assert device.should_expose is False


async def test_device_type(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State("input_number.test", "40")
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type is None

    entry_data = MockConfigEntryData(hass, entity_config={state.entity_id: {CONF_TYPE: "devices.types.other"}})
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == DeviceType.OTHER

    state = State("switch.test_1", STATE_ON)
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == DeviceType.SWITCH

    entry_data = MockConfigEntryData(
        hass,
        entity_config={
            "switch.test_1": {
                CONF_TYPE: "devices.types.openable.curtain",
            }
        },
    )
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == DeviceType.OPENABLE_CURTAIN


@pytest.mark.parametrize(
    "device_class,device_type",
    [
        (None, DeviceType.OPENABLE),
        (CoverDeviceClass.SHADE, DeviceType.OPENABLE),
        (CoverDeviceClass.CURTAIN, DeviceType.OPENABLE_CURTAIN),
    ],
)
async def test_device_type_cover(
    hass: HomeAssistant, entry_data: MockConfigEntryData, device_class: str | None, device_type: DeviceType
) -> None:
    attributes = {}
    if device_class:
        attributes[ATTR_DEVICE_CLASS] = device_class

    state = State("cover.foo", STATE_ON, attributes=attributes)
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == device_type


@pytest.mark.parametrize(
    "device_class,device_type",
    [
        (None, DeviceType.MEDIA_DEVICE),
        (MediaPlayerDeviceClass.TV, DeviceType.MEDIA_DEVICE_TV),
        (MediaPlayerDeviceClass.RECEIVER, DeviceType.MEDIA_DEVICE_RECIEVER),
        (MediaPlayerDeviceClass.SPEAKER, DeviceType.MEDIA_DEVICE),
    ],
)
async def test_device_type_media_player(
    hass: HomeAssistant, entry_data: MockConfigEntryData, device_class: str | None, device_type: DeviceType
) -> None:
    attributes = {}
    if device_class:
        attributes[ATTR_DEVICE_CLASS] = device_class

    state = State("media_player.tv", STATE_ON, attributes=attributes)
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == device_type


async def test_device_type_switch(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State("switch.test", STATE_ON)
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == DeviceType.SWITCH

    state = State("switch.test", STATE_ON, attributes={ATTR_DEVICE_CLASS: SwitchDeviceClass.OUTLET})
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.type == DeviceType.SOCKET


async def test_device_query(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    class PauseCapability(StateToggleCapability):
        instance = ToggleCapabilityInstance.PAUSE

        @property
        def supported(self) -> bool:
            return True

        def get_value(self) -> bool | None:
            if self.state.state == STATE_UNAVAILABLE:
                return None

            return self.state.state == STATE_ON

        async def set_instance_state(self, context: Context, state: ToggleCapabilityInstanceActionState) -> None:
            pass

    state = State("switch.unavailable", STATE_UNAVAILABLE)
    device = Device(hass, entry_data, state.entity_id, state)
    assert device.query().as_dict() == {"id": state.entity_id, "error_code": ResponseCode.DEVICE_UNREACHABLE}

    state = State("switch.test", STATE_ON)
    state_pause = State("input_boolean.pause", STATE_OFF)
    cap_onoff = OnOffCapabilityBasic(hass, entry_data, state.entity_id, state)
    cap_button = OnOffCapabilityButton(hass, entry_data, state.entity_id, state)
    cap_pause = PauseCapability(hass, entry_data, state_pause.entity_id, state_pause)

    state_temp = State(
        "sensor.temp",
        "5",
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    state_humidity = State(
        "sensor.humidity",
        "95",
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        },
    )
    hass.states.async_set(state_humidity.entity_id, state_humidity.state, state_humidity.attributes)

    state_voltage = State(
        "sensor.voltage",
        "220",
        attributes={
            ATTR_UNIT_OF_MEASUREMENT: "V",
            ATTR_DEVICE_CLASS: SensorDeviceClass.VOLTAGE,
        },
    )

    prop_temp = TemperatureSensor(hass, entry_data, state_temp.entity_id, state_temp)
    prop_humidity_custom = get_custom_property(
        hass,
        entry_data,
        {
            CONF_ENTITY_PROPERTY_ENTITY: state_humidity.entity_id,
            CONF_ENTITY_PROPERTY_TYPE: "humidity",
        },
        state.entity_id,
    )
    prop_voltage = VoltageSensor(hass, entry_data, state_voltage.entity_id, state_voltage)

    state_button = State("binary_sensor.button", "", attributes={"action": "click"})
    hass.states.async_set(state_button.entity_id, state_button.state, state_button.attributes)
    prop_button = get_custom_property(
        hass,
        entry_data,
        {
            CONF_ENTITY_PROPERTY_ENTITY: state_button.entity_id,
            CONF_ENTITY_PROPERTY_ATTRIBUTE: "action",
            CONF_ENTITY_PROPERTY_TYPE: "button",
        },
        state.entity_id,
    )

    device = Device(hass, entry_data, state.entity_id, state)

    with (
        patch.object(Device, "get_capabilities", return_value=[cap_onoff, cap_pause]),
        patch.object(
            Device, "get_properties", return_value=[prop_temp, prop_voltage, prop_humidity_custom, prop_button]
        ),
    ):
        assert device.query().as_dict() == {
            "id": "switch.test",
            "capabilities": [
                {"type": "devices.capabilities.on_off", "state": {"instance": "on", "value": True}},
                {"type": "devices.capabilities.toggle", "state": {"instance": "pause", "value": False}},
            ],
            "properties": [
                {"type": "devices.properties.float", "state": {"instance": "temperature", "value": 5.0}},
                {"type": "devices.properties.float", "state": {"instance": "voltage", "value": 220.0}},
                {"type": "devices.properties.float", "state": {"instance": "humidity", "value": 95.0}},
            ],
        }

        with (
            patch.object(PauseCapability, "retrievable", PropertyMock(return_value=None)),
            patch.object(TemperatureSensor, "retrievable", PropertyMock(return_value=False)),
        ):
            assert device.query().as_dict() == {
                "id": "switch.test",
                "capabilities": [{"type": "devices.capabilities.on_off", "state": {"instance": "on", "value": True}}],
                "properties": [
                    {"type": "devices.properties.float", "state": {"instance": "voltage", "value": 220.0}},
                    {"type": "devices.properties.float", "state": {"instance": "humidity", "value": 95.0}},
                ],
            }

        cap_pause.state.state = STATE_UNAVAILABLE
        prop_voltage.state.state = STATE_UNAVAILABLE
        hass.states.async_set(state_humidity.entity_id, STATE_UNAVAILABLE)
        assert device.query().as_dict() == {
            "id": "switch.test",
            "capabilities": [{"type": "devices.capabilities.on_off", "state": {"instance": "on", "value": True}}],
            "properties": [{"type": "devices.properties.float", "state": {"instance": "temperature", "value": 5.0}}],
        }

    cap_pause.state.state = STATE_ON
    with (
        patch.object(Device, "get_capabilities", return_value=[cap_pause]),
        patch.object(Device, "get_properties", return_value=[prop_temp]),
    ):
        assert device.query().as_dict() == {
            "id": "switch.test",
            "capabilities": [{"type": "devices.capabilities.toggle", "state": {"instance": "pause", "value": True}}],
            "properties": [{"type": "devices.properties.float", "state": {"instance": "temperature", "value": 5.0}}],
        }

        prop_temp.state.state = STATE_UNAVAILABLE
        assert device.query().as_dict() == {
            "id": "switch.test",
            "capabilities": [{"type": "devices.capabilities.toggle", "state": {"instance": "pause", "value": True}}],
        }

        cap_pause.state.state = STATE_UNAVAILABLE
        assert device.query().as_dict() == {"id": "switch.test", "error_code": "DEVICE_UNREACHABLE"}

    with (
        patch.object(Device, "get_capabilities", return_value=[cap_button]),
        patch.object(Device, "get_properties", return_value=[prop_button]),
    ):
        assert device.query().as_dict() == {"id": "switch.test"}


async def test_device_execute(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    state = State("switch.test", STATE_ON)
    device = Device(hass, entry_data, state.entity_id, state)
    with pytest.raises(APIError) as e:
        await device.execute(
            Context(),
            ToggleCapabilityInstanceAction(
                state=ToggleCapabilityInstanceActionState(instance=ToggleCapabilityInstance.PAUSE, value=True),
            ),
        )

    assert e.value.code == ResponseCode.NOT_SUPPORTED_IN_CURRENT_MODE
    assert e.value.message == "Device switch.test doesn't support instance pause of toggle capability"

    off_calls = async_mock_service(hass, state.domain, SERVICE_TURN_OFF)
    await device.execute(
        Context(),
        OnOffCapabilityInstanceAction(
            state=OnOffCapabilityInstanceActionState(instance=OnOffCapabilityInstance.ON, value=False),
        ),
    )
    assert len(off_calls) == 1
    assert off_calls[0].data == {ATTR_ENTITY_ID: state.entity_id}


async def test_device_execute_exception(hass: HomeAssistant, entry_data: MockConfigEntryData) -> None:
    class MockOnOffCapability(OnOffCapabilityBasic):
        async def set_instance_state(self, *_: Any, **__: Any) -> None:
            raise Exception("fail set_state")

    class MockBrightnessCapability(BrightnessCapability):
        @property
        def supported(self) -> bool:
            return True

        async def set_instance_state(self, *_: Any, **__: Any) -> None:
            raise APIError(ResponseCode.INVALID_ACTION, "foo")

    state = State("switch.test", STATE_ON)
    device = Device(hass, entry_data, state.entity_id, state)
    with patch("custom_components.yandex_smart_home.device.STATE_CAPABILITIES_REGISTRY", [MockOnOffCapability]):
        with pytest.raises(APIError) as e:
            await device.execute(
                Context(),
                OnOffCapabilityInstanceAction(
                    state=OnOffCapabilityInstanceActionState(instance=OnOffCapabilityInstance.ON, value=True),
                ),
            )

    assert e.value.code == ResponseCode.INTERNAL_ERROR
    assert e.value.message == (
        "Failed to execute action for on_off capability of switch.test: Exception('fail set_state')"
    )

    device = Device(hass, entry_data, state.entity_id, state)
    with patch("custom_components.yandex_smart_home.device.STATE_CAPABILITIES_REGISTRY", [MockBrightnessCapability]):
        with pytest.raises(APIError) as e:
            await device.execute(
                Context(),
                RangeCapabilityInstanceAction(
                    state=RangeCapabilityInstanceActionState(instance=RangeCapabilityInstance.BRIGHTNESS, value=50),
                ),
            )

    assert e.value.code == ResponseCode.INVALID_ACTION
    assert e.value.message == "foo"
