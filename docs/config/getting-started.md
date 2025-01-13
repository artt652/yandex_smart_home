Интеграция настраивается двумя способами: YAML конфигурация и интерфейс Home Assistant.

!!! tip "Важно"
    Оба способа настройки могут быть задействованы **одновременно**.

    Например, устройства для передачи выбираются через интерфейс или ярлыки, а их расширенная настройка выполняется через [`entity_config`](entity.md) в YAML конфигурации.

## Через интерфейс Home Assistant { id=gui }

* На странице `Настройки` --> `Устройства и службы` --> [`Интеграции`](https://my.home-assistant.io/redirect/integrations/) найдите
и выберите интеграцию Yandex Smart Home
* Нажмите `Настроить` на нужной записи интеграции

![](../assets/images/config/gui-1.png){ width=750 }
![](../assets/images/config/gui-2.png){ width=750 }

## Через YAML конфигурацию { id=yaml }

Часть параметров может быть настроена только через YAML конфигурацию в файле [`configuration.yaml`](https://www.home-assistant.io/docs/configuration/).
Его можно отредактировать, например, через аддон [File Editor](https://my.home-assistant.io/redirect/supervisor_addon/?addon=core_configurator).

!!! example "Пример configuration.yaml"
    ```yaml
    default_config:
    yandex_smart_home:
      entity_config:
        light.room_main:
          name: Люстра
          room: Комната
    ```

!!! example "[Пример](https://github.com/dext0r/yandex_smart_home/blob/dev/tests/fixtures/valid-config.yaml) большого configuration.yaml"

После изменений в `configuration.yaml` перезагрузите YAML конфигурацию Yandex Smart Home через `Панель разработчика` --> `YAML` --> `Перезагрузка конфигурации YAML`:

![](../assets/images/config/reload-yaml.png){ width=750 }
