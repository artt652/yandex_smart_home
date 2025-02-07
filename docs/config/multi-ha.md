Если у вас запущено несколько независимых Home Assistant (например Дом и Дача), то при их добавлении в УДЯ/Маруся вы можете столкнуться с проблемой. Платформы умного дома не позволяют подключать несколько учётных записей к одному навыку. Другими словами, не получится добавить несколько навыков Yaha Cloud к одному аккаунту УДЯ/Маруси.

Эту проблему можно решить несколькими способами:

### Способ 1

* Основной HA: **Облачное** подключение через Yaha Cloud
* Дополнительные HA: **Прямое** подключение
* Особенности: Потребуется выставить Home Assistant в интернет, сложная настройка прямого подключения

### Способ 2

* Основной HA: **Облачное** подключение через Yaha Cloud (аккаунт УДЯ 1)
* Дополнительные HA: **Облачное** подключение через Yaha Cloud (аккаунт УДЯ 2)
* Особенности: Аккаунт 2 [делится](https://alice.yandex.ru/support/ru/smart-home/multiaccount) умным домом с Аккаунт 1, подходит только для УДЯ

### Способ 3

* Основной HA: **Облачное** подключение через Yaha Cloud
* Дополнительные HA: **Облачное Плюс** подключение через свой приватный навык
* Особенности: Сложная настройка Облачного Плюс подключения, подходит для УДЯ и Маруси

### Способ 4

* Основной HA: **Прямое** подключение (навык 1)
* Дополнительные HA: **Прямое** подключение (навык 2)
* Особенности: Создаётся несколько независимых приватных навыков, потребуется выставить оба Home Assistant в интернет, сложная настройка прямого подключения

### Способ 5

* Основной HA: **Облачное** подключение через Yaha Cloud
* Дополнительные HA: компонент [Remote Home Assistant](https://github.com/custom-components/remote_homeassistant)
* Особенности: Потребуется связать по сети основной и дополнительные HA (через интернет или VPN), в УДЯ/Марусю добавляется только основной HA
