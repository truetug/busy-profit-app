# BUSY Profit collector

The collector polls its configured source every minute, saves every observation in monthly CSV archives and publishes compact daily projections for the Bar. `current.csv` contains the latest eight days and an earlier anchor; `older.csv` contains the preceding 28 days and an anchor. The legacy `history.csv` remains available for older clients. The private 38-day rolling file is a recoverable cache, not the archive.

Configure credentials and paths using the variables in [`.env.example`](.env.example); do not commit secrets. The Docker Compose service stores persistent files in its data directory. The image also builds the landing page from the repository README and publishes it alongside the feeds.

Run `python -m pip install -r backend/requirements-dev.txt` and `PYTHONPATH=backend/src:. python -m pytest backend/tests -q` from the repository root. The `collector-image.yml` workflow builds the image on changes to the backend, landing, README or screenshots.

The original notification WAV files are in `assets/sounds`; run `sh tools/prepare_sounds.sh` with FFmpeg installed to regenerate the headerless 44.1 kHz, 16-bit mono PCM files used by the Bar.
