# Alerts Energy Outages

Графіки відключень з Alerts Energy безпосередньо в Home Assistant.

[![GitHub Release](https://img.shields.io/github/v/release/rodion981/ha-energy-outages?display_name=tag&sort=semver)](https://github.com/rodion981/ha-energy-outages/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/github/license/rodion981/ha-energy-outages)](./LICENSE)

[English](./README.md) | [**Українською**](./README.uk.md)

## Швидке встановлення

1. Відкрийте цей репозиторій у HACS кнопкою нижче та встановіть інтеграцію.
2. Перезапустіть Home Assistant.
3. Натисніть **Add Integration**, щоб запустити налаштування інтеграції.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rodion981&repository=ha-energy-outages&category=integration)

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=alerts_energy_outages)

> [!NOTE]
> Для кнопки HACS потрібен встановлений HACS. Кнопка Add Integration працюватиме після завантаження кастомної інтеграції та перезапуску Home Assistant.

Користувацька інтеграція Home Assistant, яка отримує графіки відключень із [alerts.energy/kyiv](https://alerts.energy/kyiv) для черг ДТЕК Київські електромережі.

## Можливості

- налаштування черги через інтерфейс Home Assistant;
- графік на сьогодні та завтра;
- усі періоди відключень із точністю до 30 хвилин;
- binary sensor «Відключення зараз»;
- сирі погодинні коди й обчислені періоди в атрибутах;
- автоматичне оновлення даних кожні 60 секунд;

Внутрішній domain інтеграції: `alerts_energy_outages`.

## Встановлення через HACS

1. Відкрийте **HACS → Integrations**.
2. Відкрийте меню у правому верхньому куті та виберіть **Custom repositories**.
3. Додайте репозиторій:

   ```text
   https://github.com/rodion981/ha-energy-outages
   ```

   Тип: **Integration**.

4. Знайдіть та встановіть **Alerts Energy Outages**.
5. Перезапустіть Home Assistant.
6. Відкрийте **Settings → Devices & services → Add integration**.
7. Знайдіть **Alerts Energy Outages**, задайте назву та виберіть чергу.

## Сутності

Для кожної доданої черги інтеграція створює три сутності:

| Сутність | Призначення |
|---|---|
| Графік на сьогодні | Усі періоди відключень на поточну добу |
| Графік на завтра | Усі опубліковані періоди на наступну добу |
| Відключення зараз | Увімкнений, якщо поточний час потрапляє в період відключення |

Home Assistant формує entity ID із назви config entry та назви сутності. Актуальні ID можна побачити в **Settings → Devices & services → Alerts Energy Outages → Entities**.

### Атрибути сенсорів графіка

| Атрибут | Опис |
|---|---|
| `queue` | Вибрана черга, наприклад `2.2` |
| `operator` | Ідентифікатор оператора в Alerts Energy |
| `updated` | Час останньої зміни графіка, якщо його надає API |
| `hours` | Масив із 24 погодинних кодів |
| `periods` | Обчислені проміжки з полями `start` і `end` |

Значення кодів:

- `0` — світло є;
- `1` — світла немає всю годину;
- `2` — світла немає перші 30 хвилин;
- `3` — світла немає другі 30 хвилин.

## Перехід із v2.0.x

Версії `v2.0.1–v2.0.2` помилково використовували застарілий domain `yasno_outages`. Через це Home Assistant міг змішувати config entries та показувати помилку міграції.

Для переходу на `v2.1.0` або новішу версію:

1. У **Settings → Devices & services** видаліть config entry **Alerts Energy**.
2. Видаліть стару версію **Alerts Energy Outages** у HACS.
3. Перезапустіть Home Assistant.
4. Встановіть актуальну версію **Alerts Energy Outages**.
5. Знову перезапустіть Home Assistant і додайте інтеграцію заново.

Починаючи з `v2.1.0`, використовується окрема папка `custom_components/alerts_energy_outages`.

## Як це працює

Інтеграція опитує публічний JSON endpoint Alerts Energy:

```text
https://alerts.energy/api/v1/source-registry/areas/kyiv/shutdowns
```

Для вибраної черги береться запис оператора `kyiv_oblenergo`. Погодинні коди перетворюються на півгодинні межі, а сусідні відрізки об’єднуються в суцільні періоди.

Якщо API тимчасово недоступне або повертає некоректну структуру, coordinator позначає оновлення як невдале й Home Assistant зберігає останні успішно отримані дані.

## Legacy YAML-пакет

У репозиторії залишено старий YAML-варіант:

```text
includes/packages/energyua_22.yaml
```

Він потрібен лише для ручного встановлення без custom integration. Для нових інсталяцій рекомендовано використовувати HACS-інтеграцію. Не варто одночасно налаштовувати ту саму чергу через HACS та legacy YAML, оскільки це створить дублікати сутностей.

## Вимоги

- Home Assistant 2024.6 або новіший;
- доступ Home Assistant до `https://alerts.energy`;
- HACS потрібен лише для автоматичного встановлення та оновлення.

## Відомі обмеження

- наразі підтримується Київ і оператор ДТЕК Київські електромережі;
- порожній масив API може означати як відсутність відключень, так і ще не опублікований графік;
- джерело даних є стороннім сервісом і може змінити формат API.

## Підтримка

Про помилки та пропозиції повідомляйте через [GitHub Issues](https://github.com/rodion981/ha-energy-outages/issues).

Made with ❤️ в Україні.

## Ліцензія

[MIT](LICENSE)
