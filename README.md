# BUSY Profit

Приложение для BUSY Bar: показывает общую статистику продаж, динамику по часам за 24 часа и по дням за последние 28 дней. Колесо переключает три представления.

## Настройка и сборка

```sh
pnpm install
cp .env.example .env   # VITE_BUSY_ADDR — адрес бара для локальной разработки
pnpm typecheck
pnpm build
```

Для проверки на Busy Bar 21: `pnpm exec busy-cli build --out /tmp/busy-profit-build`, затем упаковать только `app.busy.profit` из этого каталога и установить его через локальный Apps API бара. `api_version` в манифесте должен быть не ниже API версии целевого бара.

Приложение читает готовую историю с `https://profit.busy.truetug.info/history.csv`. Basic Auth остаётся только на сервере-сборщике и не попадает в JS-бандл.

## Источник данных и серверный сборщик

Python backend находится в `backend/src/busy_profit` и разделён по ответственности: `main.py` собирает зависимости и запускает процесс, `application.py` координирует polling-сценарий, `models.py` описывает типизированные Pydantic-модели, `shopify.py` отвечает за HTTP-источник, а `csv_storage.py` — за историю и публичную проекцию. `settings.py` валидирует runtime-конфигурацию.

Сборщик опрашивает Shopify Stats с настраиваемым интервалом (по умолчанию минута), пишет каждую выборку в приватный rolling CSV за 28 дней и месячный CSV-архив. Для JS-приложения он атомарно публикует компактный CSV с последним значением каждого часа (до 672 строк) по адресу `https://profit.busy.truetug.info/history.csv`; это ограничивает объём ответа на дисплее. При первом запуске сборщика история начинается с первой успешной выборки.

URL источника и Basic Auth задаются только через переменные окружения `SHOPIFY_STATS_SOURCE_URL`, `SHOPIFY_STATS_BASIC_AUTH_USERNAME` и `SHOPIFY_STATS_BASIC_AUTH_PASSWORD`; пример имён настроек — в `backend/.env.example`. Реальные значения не попадают в Git, JS-бандл, Docker image или логи. На `sh` Git checkout остаётся `/srv/busy-profit-app` (это имя репозитория), а Compose service/container и образ называются `busy-profit-app-backend`. Персистентные CSV и публичная история остаются в `/srv/busy-profit-app/data`.

Уменьшение счётчика Shopify остаётся в текущем значении, но не даёт отрицательного столбца на графике. При росте количества на экране Busy Bar звучит cha-ching, а при переходе через сотню — applause.

Basic Auth credentials хранятся только в runtime-файле `/srv/busy-profit-app/.env` на сервере. Контейнер запускается от UID 1001 и сохраняет приватную минутную историю и публичную почасовую проекцию в `/srv/busy-profit-app/data`; эти файлы не входят в Git или Docker image.

Образ `ghcr.io/truetug/busy-profit-app-backend` собирает workflow `collector-image.yml` при изменениях `backend/**` в `main`. На сервере `vps-autodeploy` обновляет checkout, скачивает образ и применяет `backend/docker-compose.yml`. Caddy отдаёт только `data/public/history.csv` на `https://profit.busy.truetug.info/history.csv`.

Backend tests can be run locally with `python -m pip install -r backend/requirements-dev.txt` and `PYTHONPATH=backend/src python -m pytest backend/tests -q`.

Доступность публичного CSV, CORS и сетевой запрос нужно проверить на физическом устройстве. Локальные `pnpm typecheck` и `pnpm build` не эмулируют ограничения прошивки.
