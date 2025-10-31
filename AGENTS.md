# Repository Guidelines

## Project Structure & Module Organization
- Core runtime `franky.py` manages OpenAI streaming, UDP audio, and MQTT device control.
- Firmware sources sit under `devices/`; read `devices/README.md` before flashing a board.
- Diagnostic utilities live in `experiments/` (e.g., `test_esp32_udp.py`, `test_mqtt_subscribe.py`) and supplement ad-hoc testing.
- `mqtt/` contains Mosquitto docker configs, while `virtual_skull/` holds Blender assets and viewers for jaw animation work.
- Shared media lives in `sounds/`; runtime artifacts (`logs/`, `conversation_logs/`) are generated automatically.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate` — create and enter a virtual environment.
- `pip install -r requirements.txt` — install Python dependencies required by `franky.py` and the experiment tools.
- `python3 franky.py --voice ash` — launch the primary skull runtime; use `--voice` or toggles (`--no-mqtt`, `--output speakers`) for local iteration.
- `python3 experiments/test_esp32_udp.py` — validate UDP audio with the ESP32 before running the full bot.
- `docker compose -f mqtt/docker-compose.yml up` — start a local MQTT broker when testing servo or LED flows without cloud infrastructure.

## Coding Style & Naming Conventions
- Target Python 3.9+ with PEP 8: 4-space indents, `snake_case` module/function names, and descriptive `CamelCase` classes.
- Prefer `asyncio` coroutines for new flows, matching existing websocket and UDP handling patterns.
- Centralize configuration at module tops, rely on `os.path`/`pathlib` for paths, and guard optional hardware imports with `try/except`.
- Reserve inline comments for protocol timing or device-specific behavior; add docstrings to public entry points.

## Testing Guidelines
- There is no central `tests/` package; pick experiment scripts that mirror your change scope and document new ones in `experiments/README.md`.
- For skull visuals, run `python3 virtual_skull/test_model_load.py` and, when needed, `virtual_skull/run_viewer.sh` to validate assets.
- Attach relevant `logs/` or `conversation_logs/` snippets to PRs, noting which hardware setup captured the data.

## Commit & Pull Request Guidelines
- Follow current history style: imperative subjects under ~72 characters (e.g., `Enable conversation logging by default`) plus contextual bodies when needed.
- Summaries should cover motivation, experiment or device runs performed, and linked issues or hardware tickets.
- Include configuration notes (such as `.env` keys or MQTT endpoints) and visual evidence when altering physical behavior or visuals.

## Security & Configuration Tips
- Keep `.env` secrets and device credentials out of version control; update `.env.example` for new keys.
- Rotate MQTT credentials and OpenAI keys after demos, and rely on CLI overrides (`--mqtt-server`, `--esp32-ip`) instead of in-code literals.
