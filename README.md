# BUSY Profit

BUSY Profit shows lifetime sales, days since launch and the latest eight days on your BUSY Bar. Press Start for the 36-day chart and turn the encoder to select a day; gray pixels mark weekends. New sales appear for ten seconds with a cash sound, or applause when a hundred is crossed. Data refreshes every minute from [profit.busy.truetug.info](https://profit.busy.truetug.info/).

## Screenshots

![Sales overview on BUSY Bar](screenshots/lifetime-summary.png)

![Daily sales chart on BUSY Bar](screenshots/daily-chart.png)

## Build

Install Node.js 24 and pnpm, then run `pnpm install`, `pnpm test`, `pnpm typecheck` and `pnpm build`. Releases are packaged automatically by GitHub Actions.

The [collector](https://github.com/truetug/busy-profit-app/blob/main/backend/README.md) maintains the full sales history and publishes the compact feeds used by the app.
