# Request analytics module

Reusable private request-log analytics and aggregate SVG publication. This is an internal Python module, not a published package yet. Runtime dependency: Pydantic v2; everything else uses Python 3.13+ standard library. It does not import the host application, read environment variables, start background jobs or access cloud services on import.

## Boundaries

- Domain: `models.py` defines validated requests and identifier-free public summaries.
- Application: `application.py` imports complete batches and orchestrates retention, summaries and publication through `UsageStore`, `AnalyticsStore` and `SummaryPublisher` protocols.
- Representation: `caddy.py` maps access JSON using an explicit `AnalyticsProfile`; `svg.py` renders summaries with configurable `InfographicLabels`.
- Infrastructure: `logs.py` reads bounded rotated files; `sqlite.py` persists events and checkpoints transactionally. The SVG publisher atomically writes public files.

Use public imports from `request_analytics`; internal module names are not the future package API. `AnalyticsProfile` contains endpoint selection, session endpoint, log glob and header names. Product-specific values belong in the host, currently `busy_profit.analytics`. Device identifiers preserve case by default; uppercase normalization is opt-in.

```python
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from request_analytics import (
    AnalyticsProfile, InfographicLabels, UsageRepository,
    publish_usage_infographic, refresh_usage,
)

profile = AnalyticsProfile(
    endpoints=frozenset({"/heartbeat"}),
    session_endpoint="/heartbeat",
)
store = UsageRepository(Path("private/usage.sqlite3"), profile.session_endpoint)
try:
    result = refresh_usage(
        directory=Path("logs"),
        store=store,
        profile=profile,
        publisher=partial(
            publish_usage_infographic,
            directory=Path("public"),
            labels=InfographicLabels(title="My application usage"),
        ),
        now=datetime.now(UTC),
    )
finally:
    store.close()
```

The host owns scheduling, retries, logging, configuration, filesystem permissions, connection lifecycle and dependency composition. `refresh_usage` does not swallow failures. Custom publishers receive only `UsageSummary`, never private records. The standard publisher writes `usage.svg` and `usage-mobile.svg`.

## Compatibility and constraints

SQLite tables and cursor identity format remain unchanged from the original integration, including the legacy column name `hardware_id`. No migration or history reset is required. Files must use uncompressed rename rotation, not copy/truncate. Use one importer per database and one database per profile; profiles are not tenant-isolation boundaries. No secrets or account emails are stored. Source IP comes from Caddy's socket peer. Client device/session metadata is unverified.

Weekly activity means seven UTC calendar days including partial today; regular devices appear on at least three distinct days. Session counters use maxima, not request sums. Runtime/detail opens stop at the last reported snapshot; the unreported final interval is missing. Preserve these definitions and the database/cursor compatibility tests when extracting a standalone distribution. Packaging metadata, versioning and registry publication are deliberately deferred.
