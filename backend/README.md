# BUSY Profit collector

The collector polls its configured source every minute, saves every observation in monthly CSV archives and publishes compact daily projections for the Bar. `current.csv` contains the latest eight days and an earlier anchor; `older.csv` contains the preceding 28 days and an anchor. The legacy `history.csv` remains available for older clients. The private 38-day rolling file is a recoverable cache, not the archive.

Configure credentials and paths using the variables in [`.env.example`](.env.example); do not commit secrets. The Docker Compose service stores persistent files in its data directory. The image also builds the landing page from the repository README and publishes it alongside the feeds.

Run `python -m pip install -r backend/requirements-dev.txt` and `PYTHONPATH=backend/src:. python -m pytest backend/tests -q` from the repository root. The `collector-image.yml` workflow builds the image on changes to the backend, landing, README or screenshots.

The original notification WAV files are in `assets/sounds`; run `sh tools/prepare_sounds.sh` with FFmpeg installed to regenerate the headerless 44.1 kHz, 16-bit mono PCM files used by the Bar.

## Private usage analytics

The separate `analytics` Compose service imports Caddy JSON access logs immediately at startup and once an hour thereafter. Its read-only `/logs` mount points to `/srv/edge/logs`; `/data/usage.sqlite3` is private and never served by Caddy. No cloud credentials, PINs or emails are stored in SQLite. Source IPs come from Caddy's socket peer, not `X-Forwarded-For`. Hardware IDs are unverified client metadata.

Tables: `devices` keeps first/last appearance and current IP; `usage_hourly` groups feed requests by UTC hour, hardware ID, endpoint and HTTP status; `device_ips` keeps counts and first/last appearance per IP; `ip_changes` records chronological transitions. Detailed aggregates and IP history expire after 90 days; device first/last appearance remains. Feed downloads do not imply that a particular screen was opened. Use `status = 200` to distinguish successful usage from rejected requests.

`log_cursors` stores inode, first-record fingerprint and byte offset. Caddy must use uncompressed rename rotation. Complete batches and offsets commit atomically, so worker restarts do not duplicate requests. Incomplete tail records wait until the next import. Run only one importer against this database.

Worker settings use `BUSY_USAGE_`: `DATABASE_PATH`, `LOG_DIRECTORY`, `INTERVAL_SECONDS` (3600), `RETENTION_DAYS` (90, minimum 8). File rotation keeps seven 10 MiB files for up to seven days; monitor worker logs for `usage_import_failed` so ingestion does not fall behind that window.

Example private queries (run on the server, not through a public endpoint):

```sql
SELECT hardware_id, first_seen_at, last_seen_at, last_ip FROM devices ORDER BY last_seen_at DESC;
SELECT hardware_id, endpoint, sum(count) FROM usage_hourly WHERE status = 200 GROUP BY hardware_id, endpoint;
SELECT observed_at, previous_ip, ip FROM ip_changes WHERE hardware_id = ? ORDER BY observed_at;
```
