# v2.6.1: Alerts Energy icon / Іконка Alerts Energy

Release date / Дата релізу: 2026-10-30.

## Українською

- Іконку інтеграції замінено оригінальною іконкою з [сайту Alerts Energy](https://alerts.energy/): жовта блискавка на позначці місця з темним тлом.
- Розмір 512×512 збережений без змін, 256×256 підготовлений з оригіналу; обидва PNG мають прозорі кути. Джерело зазначене в [документації брендингу](https://github.com/rodion981/ha-energy-outages/blob/v2.6.1/docs/BRANDING.md).
- Оновлено згадки про іконку в README українською й англійською.

Логіка API, графіки, опитування та ідентифікатори сутностей незмінні порівняно з v2.6.0. Оновіть через HACS і перезапустіть Home Assistant. Якщо браузер показує стару іконку, оновіть сторінку без кешу. Локальні іконки підтримуються в HA 2026.3+; відображення іконки в каталозі HACS залежить від його власної підтримки брендингу.

## English

- Replace the integration icon with the original [Alerts Energy](https://alerts.energy/) website artwork: a yellow lightning bolt over a location marker on a dark background.
- Preserve the original 512×512 file and resize it to 256×256; both PNGs retain transparent corners. Record the source in [branding documentation](https://github.com/rodion981/ha-energy-outages/blob/v2.6.1/docs/BRANDING.md).
- Update both READMEs to identify the provider's artwork.

API, schedules, polling and entity identities are unchanged from v2.6.0. Update through HACS and restart Home Assistant; refresh the browser without cache if it retains the old icon. Local icons require HA 2026.3+; HACS catalog rendering depends on its own branding support.

## Validation / Перевірки

PNG dimensions, RGBA transparency, byte identity of the 512px source, metadata and exact release archive are checked. CI runs the existing runtime tests, Ruff, formatting, mypy, hassfest and HACS for the final commit/tag.
