Дополнительные настройки устройств могут задаваться через раздел `entity_config` в [YAML конфигурации](./getting-started.md#yaml). Использование `entity_config` возможно при **любом** способе передачи объектов в УДЯ. Все параметры являются необязательными.

!!! attention "Обратите внимание"
    Наличие объекта в `entity_config` не означает, что он будет передан в УДЯ автоматически. Не забудьте явно разрешить [передачу объекта в УДЯ](./filter.md).

## Имя и комната { id=name-room }

> Параметры: `name` и `room`

Название и комната устройства, имеются [ограничения](../quirks.md#naming) по длине и возможным символам. Можно так же задавать [через интерфейс](../quirks.md#naming).

!!! tip "[Рекомендации по правильному выбору имени устройства](https://alice.yandex.ru/support/ru/smart-home/how-to-name-device)"

!!! info "Смотрите также: [как интеграция определяет имя устройства и комнату](../quirks.md#naming)"

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        switch.dishwasher:
          name: Посудомойка
          room: Кухня
    ```

## Тип устройства { id=type }

> Параметр: `type` ([**возможные значения**](https://yandex.ru/dev/dialogs/smart-home/doc/concepts/device-types.html))

Переопределяет автоматически вычисленный тип устройства. Влияет только на визуальную составляющую в "Дом с Алисой" (и глаголы управления). Никак не влияет на функции устройства.

Например, домен `switch` по умолчанию передаётся как "выключатель" (`switch`) и реагирует на команду "Алиса, включи ХХХ".
Если задать `openable`, то у такого устройства изменится иконка на дверь и фраза на "Алиса, **открой** XXX".

Поддерживается как полное, так и краткое наименование: вместо `devices.types.dishwasher` можно использовать `dishwasher`, или вместо `devices.types.thermostat.ac` можно использовать `thermostat.ac`.

!!! attention "Обратите внимание (УДЯ)"
    После изменения типа **обязательно** удалите устройство вручную в УДЯ и выполните [Обновление списка устройств](../platforms/yandex.md#discovery).

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        switch.dishwasher:
          name: Посудомойка
          type: dishwasher
        switch.gate:
          name: Ворота
          type: openable
    ```

Рекомендуемые альтернативные типы:

* `switch` для светильников: Предотвращает включение по команде "Алиса, включи свет"
* `thermostat.ac`: Кондиционер
* `cooking.kettle`: Чайник

## Действие включения/выключения { id=turn_on-off }

> Параметр: `turn_on` и `turn_off`

Переопределяет действие, которое будет выполнено при включении или отключении устройства через УДЯ.

Параметр может быть использован, например, для [выбора режима включения](../devices/climate.md) кондиционера.

!!! example "Переопределение действия включения/выключения телевизора"
    ```yaml
    yandex_smart_home:
      entity_config:
        media_player.tv:
          turn_on:
            action: script.tv_on
          turn_off:
            action: switch.turn_off
            entity_id: switch.tv_outlet
    ```

Для запрета включения или отключения устройства установите `turn_on` или `turn_off` равным `false` (без кавычек).
Альтернативный способ повлиять на управление устройством - [коды ошибок](../advanced/error-codes.md).

!!! example "Запрет открытия замка из УДЯ (закрывать по-прежнему можно)"
    ```yaml
      yandex_smart_home:
        entity_config:
          lock.front_door:
            turn_on: false
    ```

Для добавления функции включения тем объектам, которые изначально её не поддерживают, кроме параметров `turn_on` или `turn_off` необходимо дополнительно добавить параметр [`state_template`](#state_template).

## Поддерживаемые функции (media_player) { id=features }

> Параметр: `features` (только для `media_player`)

> Возможные значения: `volume_mute`, `volume_set`, `next_previous_track`, `select_source`, `turn_on_off`, `play_pause`, `play_media` (список, можно все сразу)

Используется для явного указания поддерживаемых устройством функций.
Необходим для устройств, которые меняют набор функций в зависимости от своего состояния (например Chrome Cast или Universal Mediaplayer).

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        media_player.chrome_cast:
          features:
            - volume_mute
            - volume_set
            - next_previous_track
            - select_source
            - turn_on_off
            - play_pause
            - play_media
    ```

## Выбор каналов (media_player) { id=support_set_channel }

> Параметр: `support_set_channel` (только для `media_player`)

> Возможные значения: `false`

Отключает функцию выбора канала для `media_player` через цифровую панель и действие `media_player.play_media`.

Может потребоваться для устройств, которые не поддерживают выбор канала, но поддерживают действие `play_media` и переключение треков.

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        media_player.music_player:
          support_set_channel: false
    ```

## Раздельные кнопки вкл/выкл { id=state_unknown }

> Параметр: `state_unknown`

> Возможные значения: `true`

Включает раздельное отображение кнопок для включение и отключения устройства.

Рекомендуется использовать для устройств, которые не возвращают своё актуальное состояние (например шторы или вентилятор, управляемые по IR каналу).

![](../assets/images/config/state-unknown.png){ width=200 }

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        cover.ir_shades:
          state_unknown: true
    ```

## Состояние из шаблона { id=state_template }

> Параметр: `state_template`

Включает вычисление состояния устройства не из состояния объекта, а из шаблона. Полезно использовать с параметрами `turn_on` и `turn_off` для добавления функции включения тем устройствам, которые её не поддерживают (например камерам).

!!! warning "При использование `state_template` обязательно задать параметры `turn_on` и `turn_off` вручную, в противном случае включение/выключение устройства работать не будет."

!!! example "Пример управления розеткой из карточки камеры"
    ```yaml
    yandex_smart_home:
      entity_config:
        camera.aquarium:
          state_template: '{{ states("switch.camera_aquarium") }}'
          turn_on:
            action: switch.turn_on
            entity_id: switch.camera_aquarium
          turn_off:
            action: switch.turn_off
            entity_id: switch.camera_aquarium
    ```

## Подсветка { id=backlight }

> Параметр: `backlight_entity_id`

Позволяет подключить к устройству осветительный прибор (например подсветка чайника). Все функции осветительного прибора (яркость, цвет, температура) будут так же добавлены к устройству.

В качестве подсветки могут выступать не только осветительные приборы (`light.*`), но и любые другие объекты, поддерживающие действия `turn_on` и `turn_off`.

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        water_heater.kettle:
          backlight_entity_id: light.kettle_backlight
        climate.ac:
          backlight_entity_id: switch.ac_backlight
    ```

## "Медленные" устройства { id=slow-device }

> Параметр: `slow`

> Возможные значения: `true`

При получении команды от УДЯ компонент выполняет действие над устройством, ждёт его завершения, и только после этого возвращает ответ "команда успешно  выполнена". Некоторые устройства (например интеграция Starline) выполняют действия очень долго (дольше 5 секунд), из-за этого при управлении через Алису постоянно возникает ошибка.

После включении флага `slow: true` в УДЯ будет отправлен ответ "команда успешно выполнена" сразу же после её получения без фактического ожидания завершения выполнения действия на стороне Home Assistant.

!!! warning "Включайте этот флаг только для проблемных устройств"

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        switch.starline_engine:
          slow: true
    ```

## Ограничение уровня громкости { id=range }

> Параметр: `range`

Ограничивает диапазон, в котором может регулироваться громкость устройства.

!!! example "Пример"
    ```yaml
    yandex_smart_home:
      entity_config:
        media_player.receiver:
          range:
            max: 95
            min: 20
            precision: 2  # шаг регулировки
    ```
