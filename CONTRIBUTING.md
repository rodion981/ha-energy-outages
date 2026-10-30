# Development / Розробка

Use Linux/WSL for Home Assistant runtime tests. Automated validation targets HA 2026.10/Python 3.14 using the fixture pinned in `requirements-dev.txt`. HACS still declares HA 2024.6 as the minimum, but that older baseline is no longer tested.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pip install --no-deps homeassistant==2026.10.0
python scripts/validate.py
ruff check .
ruff format --check .
mypy
pytest -q --cov --cov-report=term-missing
```

HA imports are tested at runtime; mypy checks integration code without traversing the entire HA source tree. Python 3.12 syntax compatibility remains the lint/type-check target while the declared minimum is unchanged.

Optional pre-commit: install `pre-commit`, then run `pre-commit install` and `pre-commit run --all-files`. To format deliberately, run `ruff format .`; keep unrelated files out of a narrow fix.

CI runs the current HA baseline, lint, formatting, type checks, metadata validation, hassfest and HACS validation. Before a release, also test a clean installation, setup/unload/reload, network failure/recovery and identity-preserving reconfiguration. Live public API checks are read-only and must remain separate from mocked regression tests. Do not modify a working Home Assistant instance during development.

У Linux/WSL запускайте HA runtime-тести на HA 2026.10/Python 3.14; автоматичні перевірки HA 2024.6 прибрано, заявлений мінімум у HACS поки незмінний. Перед змінами читайте `AGENTS.md`, зберігайте domain, entity/device identity та публічні атрибути. Після змін запускайте релевантні перевірки; статичні, runtime, CI та live API результати повідомляйте окремо. Не підміняйте черги автоматично, не перетворюйте невідомий графік на відсутність відключень і не публікуйте реліз без дозволу власника.

For regional changes, cover the region/district/community/settlement flow, exact operators/queues, unavailable-directory retry/back, area-qualified duplicates and atomic reconfiguration. Keep the old Kyiv entity/device identity and test minor-version migration without a directory request. Source directories do not map addresses to queues.

Optional local hassfest with Docker (read-only checkout mount):

```sh
docker run --rm -v "$PWD:/github/workspace:ro" ghcr.io/home-assistant/hassfest
```

For forecasts, test half-hour/midnight/DST boundaries, unknown start/end at the published horizon, typed entities and an actual HA timestamp automation. For shared polling, prove concurrent setup coalesces requests, one entry unloading preserves the others, failed setup releases resources and `pref_disable_polling` is respected.

Release notes: [docs/RELEASE_NOTES_v2.7.0.md](docs/RELEASE_NOTES_v2.7.0.md). Hosted CI/HACS must pass for the exact commit/tag before publication.
