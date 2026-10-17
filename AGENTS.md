# Alerts Energy Outages: робота з репозиторієм

## Архітектура
- `custom_components/alerts_energy_outages/`: custom integration, domain `alerts_energy_outages`.
- `brand/icon.png`, `brand/icon@2x.png`: локальна іконка для HA 2026.3+ (RGBA 256/512 px). Старі HA її не використовують; HACS 2.0.5 може показувати заглушку замість локальної іконки.
- `manifest.json`, `hacs.json`: версія/HA metadata; `const.py`: operator, endpoint, polling, source timezone.
- `config_flow.py`: область → район/громада/населений пункт → оператор → черга; retry/back, duplicate protection, atomic reconfigure зі збереженням entity identity.
- `api.py`: HA-managed aiohttp session; публічні GET /atus, /atus/{katottg}, /source-registry/areas/{area}/{suppliers,shutdowns}; Territory validation. Міський довідник не визначає чергу або оператора за адресою.
- `__init__.py`: first refresh, platform setup/unload, entry adapters у `hass.data`, shared area pool у DATA_AREAS; ref-counted acquire/release та cleanup на setup failure/unload.
- `coordinator.py`: один area poller (типово 15 хв) + half-hour clock; найкоротший scan_interval у хвилинах серед активних entry contexts з увімкненим polling. Options flow: 1..1440 цілих хв; update listener переплановує без reload. Не прив’язуй shared source до першого ConfigEntry; зберігай pref_disable_polling та cleanup listener на unload.
- `forecast.py`: UTC half-hour timeline із Kyiv wall codes, DST, поточний/наступний період, невідомий кінець на краю published horizon.
- `sensor.py`, `binary_sensor.py`: незалежна availability днів і поточне планове відключення; entity properties без I/O.
- `diagnostics.py`: allowlist health/public metadata; `strings.json`, `translations/en.json`, `translations/uk.json`: UI.
- Репозиторій підтримує встановлення custom integration через HACS/UI. Приклади автоматизацій мають використовувати її фактичні entity IDs і машинні атрибути.
- Читай обидва README, `CONTRIBUTING.md` та `CHANGELOG.md` перед змінами встановлення/поведінки.

## Стиль і перевірки
- Python 3.12+: 4 пробіли, подвійні лапки, англійські docstrings, анотації, snake_case, async networking.
- Sensor descriptions: frozen/kw_only dataclass; сутності: CoordinatorEntity. Зберігай стиль відповідного файлу.
- Команди в Linux/WSL після встановлення `requirements-dev.txt`: `python scripts/validate.py`, `ruff check .`, `ruff format --check .`, `mypy`, `pytest -q --cov --cov-report=term-missing`.
- Форматування: `ruff format .`. Pre-commit необов’язковий: `pre-commit run --all-files` після встановлення.
- Окремий Python 3.12 environment з `requirements-ha-minimum.txt` перевіряє HA 2024.6. Не змішуй old/current HA dependencies.
- CI: `.github/workflows/validate.yml`, два HA baselines, Ruff, mypy, metadata, hassfest і HACS.
- Mypy не обходить HA source tree; HA APIs перевіряються runtime-тестами.

## Безпечні зміни та backward compatibility
- Спершу перевір реалізацію й відтвори проблему. Змінюй найвужчий шар; уникай unrelated refactoring.
- Зберігай domain, schema VERSION=1 (MINOR_VERSION=2), entity keys та існуючі атрибути. Зміни їх контракту потребують compatibility plan.
- Entry unique ID для Києва = operator_queue; для інших областей = area_operator_queue. Не додавай locality до ID: графік регіональний. Entity/device identity = збережений `entity_unique_id`, інакше entry.unique_id/entry_id. Reconfigure змінює queue/entry unique ID, але залишає registry identity; не створюй колізії при повторному використанні старої черги.
- Не підміняй відсутню чергу схожим номером. Отримуй точні варіанти з API й вимагай явного вибору користувача.
- `async_migrate_entry`: idempotent expand-only area=kyiv для старих записів; зберігай дані й registry identity. Старі версії підтримують лише київські записи.
- Дні незалежні. Невідомі/невалідні/недатовані/застарілі графіки не означають «без відключень» чи off.
- Source timezone: Europe/Kyiv. Перевіряй midnight, DST, half-hour boundaries та unavailable/recovery. Clock updates мають працювати без зміни payload.
- Коди: 0=світло є, 1=немає всю годину, 2=перші 30 хв, 3=другі 30 хв; лише int, не bool/string. NoShutdowns приймай лише з актуальною датою й 24 нулями; emergency/невідомі коди не перетворюй на off. Інтервали [start,end), межі 0..48, кінець доби 24:00.
- Нові forecast keys additive: next_outage (лише майбутнє), expected_restoration/outage_duration (current-or-next). Unknown start/end/no window -> None, не нуль/північ. Відключення на початку today може починатися вчора: full duration невідома. Тривалість у хвилинах без state_class. Data status/last_successful_update залишаються доступними при API failure; це response time, не source publication.
- State має ліміт 255 символів; усі періоди зберігай в атрибутах. Локалізований текст не є machine contract.
- HA-managed session не закривай самостійно; blocking I/O не додавай. Зберігай first refresh до platform setup, успішний unload і timer cleanup.
- Для сповіщень про завтра перевіряй availability і schedule_status=published, використовуй date та повні periods. Відрізняй зміну графіка від updated/API recovery; захист від повторів має враховувати перезапуск HA.
- Не змінюй робочий HA під час тестів.
- Після змін запускай релевантні gates. Окремо повідомляй static, runtime, hosted CI, live API та frontend результати; пропущені перевірки не називай успішними.
- Push/tag/release лише з дозволу власника й після релевантних gates; двомовні release notes.
