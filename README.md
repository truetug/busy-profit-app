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

Серверный сборщик — один Python loop-скрипт в Docker Compose, который опрашивает `https://busy.marketing/shopifystats/count` раз в минуту и пишет каждую выборку в приватный rolling CSV на 28 дней, а при смене месяца архивирует её в месячный CSV. Для JS-приложения он атомарно публикует компактный CSV с последним значением каждого часа (до 672 строк) по адресу `https://profit.busy.truetug.info/history.csv`; это ограничивает объём ответа на дисплее. При первом запуске сборщика история начинается с первой успешной выборки.

Уменьшение счётчика Shopify остаётся в текущем значении, но не даёт отрицательного столбца на графике. При росте количества на экране Busy Bar звучит cha-ching, а при переходе через сотню — applause.

Basic Auth credentials хранятся только в runtime-файле `/srv/busy-profit-app/.env` на сервере. Контейнер запускается от UID 1001 и сохраняет приватную минутную историю и публичную почасовую проекцию в `/srv/busy-profit-app/data`; эти файлы не входят в Git или Docker image.

Образ `ghcr.io/truetug/busy-profit-app-collector` собирает workflow `collector-image.yml` при изменениях `backend/**` в `main`. На сервере `vps-autodeploy` обновляет checkout, скачивает образ и применяет `backend/docker-compose.yml`. Caddy отдаёт только `data/public/history.csv` на `https://profit.busy.truetug.info/history.csv`.

Доступность публичного CSV, CORS и сетевой запрос нужно проверить на физическом устройстве. Локальные `pnpm typecheck` и `pnpm build` не эмулируют ограничения прошивки.
