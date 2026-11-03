"""Verify the reusable module independently of its current host application."""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from request_analytics import AnalyticsProfile, UsageRepository, refresh_usage
from test_usage import NOW


def test_module_imports_and_runs_without_profit_package(tmp_path: Path) -> None:
    """Run a generic profile in an isolated interpreter without any host code.

    Only request_analytics and its declared Pydantic dependency may be available.
    """
    source = Path(__file__).resolve().parents[1] / "src/request_analytics"
    shutil.copytree(source, tmp_path / "request_analytics")
    script = r"""
import importlib.util, json, sys
from datetime import UTC, datetime
from pathlib import Path
sys.path.insert(0, sys.argv[1])
assert importlib.util.find_spec('busy_profit') is None
from request_analytics import AnalyticsProfile, InfographicLabels, UsageRepository, parse_usage_line, refresh_usage, render_usage_svg
root = Path(sys.argv[1])
profile = AnalyticsProfile(endpoints=frozenset({'/heartbeat'}), session_endpoint='/heartbeat')
record = {'ts':1762128000, 'status':200, 'request':{'method':'GET','uri':'/heartbeat','remote_ip':'192.0.2.1','headers':{'X-Device-ID':['client-a']}}}
line = (json.dumps(record)+'\n').encode()
assert parse_usage_line(line, profile).hardware_id == 'client-a'
(root/'requests.json').write_bytes(line)
store = UsageRepository(root/'analytics.sqlite3', profile.session_endpoint)
published = []
result = refresh_usage(root, store, profile, published.append, datetime(2025,11,3,tzinfo=UTC))
assert result.imported_records == 1 and len(published) == 1 and result.summary.active == 1
svg = render_usage_svg(result.summary, labels=InfographicLabels(title='Generic usage'))
assert 'Generic usage' in svg and 'BUSY' not in svg and 'client-a' not in svg
store.close()
"""
    result = subprocess.run([sys.executable, "-I", "-c", script, str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_existing_cursor_and_database_survive_module_extraction(tmp_path: Path) -> None:
    """Open a pre-extraction database without changing or resetting its checkpoint.

    Existing tables are reused and newly initialized adapters do not count old logs.
    """
    path = tmp_path / "usage.sqlite3"
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE log_cursors(file_id TEXT PRIMARY KEY, offset INTEGER NOT NULL, updated_at TEXT NOT NULL)")
        database.execute("INSERT INTO log_cursors VALUES ('existing-inode-fingerprint',1234,?)", (NOW.isoformat(),))
    repository = UsageRepository(path, "/heartbeat")
    assert repository.offset("existing-inode-fingerprint") == 1234
    profile = AnalyticsProfile(endpoints=frozenset({"/heartbeat"}), session_endpoint="/heartbeat")
    results = []
    result = refresh_usage(tmp_path, repository, profile, results.append, NOW)
    assert result.imported_records == 0
    assert results == [result.summary]
    assert repository.offset("existing-inode-fingerprint") == 1234
    repository.close()
