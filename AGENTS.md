# Alerts Energy Outages: робота з репозиторієм

## Архітектура
- `custom_components/alerts_energy_outages/`: custom integration, domain `alerts_energy_outages`.
- `brand/icon.png`, `brand/icon@2x.png`: локальна іконка для HA 2026.3+ та HACS; старі HA її не використовують.
- `manifest.json`, `hacs.json`: версія/HA metadata; `const.py`: operator, endpoint, polling, source timezone.
- `config_flow.py`: динамічні точні черги, duplicate protection, reconfigure зі збереженням entity identity.
- `api.py`: HA-managed aiohttp session, публічний GET, response/queue validation.
- `__init__.py`: first refresh, platform setup/unload, coordinator у `hass.data`, UTC clock listener із cleanup.
- `coordinator.py`: polling 60 с, UpdateFailed, day validity, half-hour periods, state formatting.
- `sensor.py`, `binary_sensor.py`: незалежна availability днів і поточне планове відключення; entity properties без I/O.
- `diagnostics.py`: allowlist health/public metadata; `strings.json`, `translations/en.json`, `translations/uk.json`: UI.
- `includes/packages/energyua_22.yaml`: окремий сучасний YAML-пакет для точної 2.2, потребує HA timezone Europe/Kyiv; автоматизація в `automations/` залежить від його IDs.
- Читай обидва README, `CONTRIBUTING.md`, `CHANGELOG.md` та `configuration.yaml.example` перед змінами встановлення/поведінки.

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
- Зберігай domain, schema VERSION=1, entity keys та існуючі атрибути. Зміни їх контракту потребують compatibility plan.
- Entry unique ID = operator_queue. Entity/device identity = збережений `entity_unique_id`, інакше entry.unique_id/entry_id. Reconfigure змінює queue/entry unique ID, але залишає registry identity; не створюй колізії при повторному використанні старої черги.
- Не підміняй відсутню чергу схожим номером. Отримуй точні варіанти з API й вимагай явного вибору користувача.
- Дні незалежні. Невідомі/невалідні/недатовані/застарілі графіки не означають «без відключень» чи off.
- Source timezone: Europe/Kyiv. Перевіряй midnight, DST, half-hour boundaries та unavailable/recovery. Clock updates мають працювати без зміни payload.
- Коди: 0=світло є, 1=немає всю годину, 2=перші 30 хв, 3=другі 30 хв; лише int, не bool/string. Інтервали [start,end), межі 0..48, кінець доби 24:00.
- State має ліміт 255 символів; усі періоди зберігай в атрибутах. Локалізований текст не є machine contract.
- HA-managed session не закривай самостійно; blocking I/O не додавай. Зберігай first refresh до platform setup, успішний unload і timer cleanup.
- Legacy YAML: зберігай entity IDs/friendly names та залежні автоматизації. Не використовуй видалені `platform: template` чи `from_json(default)`, несумісний із HA 2024.6.
- Не вмикай custom integration і YAML-пакет для тієї самої черги одночасно. Не змінюй робочий HA під час тестів.
- Після змін запускай релевантні gates. Окремо повідомляй static, runtime, hosted CI, live API та frontend результати; пропущені перевірки не називай успішними.
- Push/tag/release лише з дозволу власника й після релевантних gates; двомовні release notes. Старий перехід із yasno_outages залишається ручним, як описано README.
