"""Infrastructure adapters for source HTTP access and local state storage."""

import base64
import csv
import os
import urllib.request
import wave
from datetime import date, datetime, timedelta
from pathlib import Path

from busylib import BusyBar, types
from pydantic import BaseModel, ConfigDict, Field

from busy_shopify_stats.model import SalesHistoryPoint, SalesSnapshot


class BasicAuthHttpSource:
    """Read Shopify Stats JSON over HTTPS with HTTP Basic authentication.

    Credentials are supplied by runtime configuration and are never included in
    the requested URL or persisted state.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        timeout_seconds: float = 20,
    ) -> None:
        """Configure source address, credentials, and network timeout.

        The adapter performs no retry because scheduling and failure policy
        belong to the application service.
        """
        self._url = url
        self._username = username
        self._password = password
        self._timeout_seconds = timeout_seconds

    def fetch(self) -> bytes:
        """Return the raw endpoint body for validation by representation code.

        Network and HTTP errors propagate to the use case, which preserves the
        previous persisted state when a polling cycle fails.
        """
        credentials = f"{self._username}:{self._password}".encode()
        authorization = base64.b64encode(credentials).decode("ascii")
        request = urllib.request.Request(
            self._url,
            headers={
                "Authorization": f"Basic {authorization}",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "busy-shopify-stats/1.0",
            },
        )
        with urllib.request.urlopen(
            request,
            timeout=self._timeout_seconds,
        ) as response:
            return response.read()


class JsonSnapshotRepository:
    """Persist the last valid snapshot atomically next to application code.

    Replacing a fully written temporary file prevents interrupted writes from
    corrupting the last known sales value.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Configure the state path, defaulting to this package directory.

        Deployment may pass another filename inside the same installed code
        directory without changing repository behavior.
        """
        self.path = path or Path(__file__).resolve().parent / "state.json"

    def load(self) -> SalesSnapshot | None:
        """Load the last snapshot or return no baseline when the file is absent.

        Invalid persisted JSON is surfaced to the caller instead of silently
        turning corrupted state into a first-run transition.
        """
        if not self.path.exists():
            return None
        return SalesSnapshot.model_validate_json(self.path.read_bytes())

    def save(self, snapshot: SalesSnapshot) -> None:
        """Atomically replace the persisted snapshot with the current value.

        The temporary file is created in the destination directory so the final
        replace remains atomic on a single filesystem.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.tmp")
        temporary_path.write_text(
            snapshot.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, self.path)


class SalesHistoryState(BaseModel):
    """Represent the persisted envelope for minute-level history points.

    An explicit envelope leaves room for future schema metadata without changing
    the JSON root type.
    """

    model_config = ConfigDict(frozen=True)

    points: list[SalesHistoryPoint] = Field(default_factory=list)


class CsvSalesHistoryRepository:
    """Persist minute observations in rolling and calendar-month CSV files.

    The rolling file retains 28 days for flexible display experiments. Monthly
    files are append-only canonical archives and remain complete indefinitely.
    """

    _fieldnames = ("observed_at", "bars_sold", "source_updated_at")

    def __init__(
        self,
        path: Path | None = None,
        retention: timedelta = timedelta(days=28),
        graph_window: timedelta = timedelta(days=28),
        legacy_json_path: Path | None = None,
    ) -> None:
        """Configure rolling CSV, retention, graph window, and legacy source.

        Legacy JSON is migrated once and renamed only after rolling and monthly
        CSV files have been written successfully.
        """
        self.path = path or Path(__file__).resolve().parent / "history.csv"
        self._retention = retention
        self._graph_window = graph_window
        self._legacy_json_path = legacy_json_path or self.path.with_suffix(".json")
        self._last_pruned_date: date | None = None

    def load(self) -> list[SalesHistoryPoint]:
        """Return the complete retained rolling history chronologically.

        Missing CSV is valid before the first successful source observation.
        """
        return self._read_csv(self.path)

    def append(self, point: SalesHistoryPoint) -> list[SalesHistoryPoint]:
        """Append one point to rolling/monthly CSV and return the graph window.

        Rolling pruning happens once per UTC date to limit SD-card rewrites.
        Equal values remain explicit minute rows for future display strategies.
        """
        self._migrate_legacy(point)
        observed_date = point.observed_at.date()
        if observed_date != self._last_pruned_date:
            retained = [
                existing
                for existing in self.load()
                if existing.observed_at >= point.observed_at - self._retention
            ]
            self._rewrite_csv(self.path, retained)
            self._last_pruned_date = observed_date

        self._append_csv(self.path, point)
        self._append_csv(self._monthly_path(point), point)
        return self._read_csv(
            self.path,
            cutoff=point.observed_at - self._graph_window,
        )

    def _migrate_legacy(self, current: SalesHistoryPoint) -> None:
        """Migrate the former JSON envelope into rolling and monthly CSV files.

        Migration is skipped once the rolling CSV exists. The old file receives
        a `.migrated` suffix only after every target write succeeds.
        """
        if self.path.exists() or not self._legacy_json_path.exists():
            return
        state = SalesHistoryState.model_validate_json(
            self._legacy_json_path.read_bytes(),
        )
        retained = [
            point
            for point in state.points
            if point.observed_at >= current.observed_at - self._retention
        ]
        self._rewrite_csv(self.path, retained)
        monthly_points: dict[str, list[SalesHistoryPoint]] = {}
        for point in state.points:
            key = point.observed_at.strftime("%Y-%m")
            monthly_points.setdefault(key, []).append(point)
        for key, points in monthly_points.items():
            self._rewrite_csv(self.path.with_name(f"history-{key}.csv"), points)
        os.replace(
            self._legacy_json_path,
            self._legacy_json_path.with_suffix(".json.migrated"),
        )

    def _monthly_path(self, point: SalesHistoryPoint) -> Path:
        """Return the append-only archive path for one UTC observation month.

        UTC timestamps keep month boundaries independent from host timezone and
        daylight-saving changes.
        """
        return self.path.with_name(f"history-{point.observed_at:%Y-%m}.csv")

    def _read_csv(
        self,
        path: Path,
        cutoff: datetime | None = None,
    ) -> list[SalesHistoryPoint]:
        """Read validated chronological points from one CSV file.

        An optional cutoff limits returned objects for graph rendering without
        changing the longer retained rolling file.
        """
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != self._fieldnames:
                raise ValueError(f"invalid sales history CSV header: {path}")
            points = [SalesHistoryPoint.model_validate(row) for row in reader]
        if cutoff is not None:
            points = [point for point in points if point.observed_at >= cutoff]
        return sorted(points, key=lambda point: point.observed_at)

    def _append_csv(self, path: Path, point: SalesHistoryPoint) -> None:
        """Append and flush one row, creating the header when necessary.

        Monthly and rolling files share a stable schema for shell tools,
        spreadsheets, and future display renderers.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self._fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(self._row(point))
            stream.flush()
            os.fsync(stream.fileno())

    def _rewrite_csv(self, path: Path, points: list[SalesHistoryPoint]) -> None:
        """Atomically replace a CSV with supplied chronological points.

        Rewrites are reserved for daily rolling pruning and one-time legacy
        migration rather than routine minute appends.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_name(f".{path.name}.tmp")
        with temporary_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self._fieldnames)
            writer.writeheader()
            writer.writerows(self._row(point) for point in points)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)

    @staticmethod
    def _row(point: SalesHistoryPoint) -> dict[str, str | int]:
        """Map one domain point to the stable flat CSV representation.

        ISO-8601 values preserve timezone offsets and are accepted directly by
        Pydantic when the file is read again.
        """
        return {
            "observed_at": point.observed_at.isoformat(),
            "bars_sold": point.bars_sold,
            "source_updated_at": point.source_updated_at.isoformat(),
        }


class BusyBarCanvasClient:
    """Adapt application display operations to the official busylib client.

    Element layout remains in the representation factory while busylib owns
    request validation, retries, API compatibility, and HTTP transport.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 12,
        client: BusyBar | None = None,
    ) -> None:
        """Configure or accept a reusable official BusyBar client.

        Client injection lets tests use busylib's supported MockTransport path
        without replacing application behavior.
        """
        self._application_name = "shopify_stats"
        self._client = client or BusyBar(
            base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def draw(self, payload: dict[str, object]) -> None:
        """Validate and draw one complete Canvas frame through busylib.

        Library and transport failures propagate to the runtime loop for
        structured logging and retry on the next scheduled cycle.
        """
        display_elements = types.DisplayElements.model_validate(payload)
        self._client.display_draw(display_elements)

    def play_audio(self, path: str) -> None:
        """Start one uploaded application audio file through busylib.

        WAV playback is supported by the deployed Busy Bar firmware and uses
        the same application namespace as Canvas assets.
        """
        self._client.audio_play(
            path=path,
            application_name=self._application_name,
        )

    def upload_asset(self, path: Path) -> None:
        """Upload one image or audio file into the application namespace.

        Deployment can call the same typed adapter for PNG and WAV assets rather
        than constructing multipart or octet-stream requests manually.
        """
        self.upload_asset_bytes(path.name, prepare_busy_bar_asset(path))

    def delete_assets(self) -> None:
        """Delete the complete application asset namespace before replacement.

        Deployment uses this operation only when static files changed, ensuring
        renamed assets do not leave obsolete filenames on the Busy Bar.
        """
        self._client.assets_delete(application_name=self._application_name)

    def upload_asset_bytes(self, filename: str, data: bytes) -> None:
        """Upload in-memory generated content into application assets.

        Dynamic graph PNGs avoid an unnecessary intermediate file while static
        deployment assets can continue using upload_asset.
        """
        self._client.assets_upload(
            application_name=self._application_name,
            filename=filename,
            data=data,
        )

    def close(self) -> None:
        """Close the underlying reusable busylib HTTP client.

        The long-running service normally calls this only during graceful
        lifecycle shutdown.
        """
        self._client.close()


def prepare_busy_bar_asset(path: Path) -> bytes:
    """Return bytes in the firmware-ready format for one application asset.

    Images are uploaded unchanged. WAV files are converted to raw signed
    16-bit little-endian mono at 44.1 kHz because Busy Bar firmware expects
    that payload format even when the stored asset name keeps a WAV suffix.
    """
    if path.suffix.lower() != ".wav":
        return path.read_bytes()
    return convert_wav_to_busy_bar_pcm(path)


def convert_wav_to_busy_bar_pcm(path: Path) -> bytes:
    """Convert a WAV file to Busy Bar raw PCM audio bytes.

    The converter covers the existing mono 8-bit PCM assets and standard
    16-bit PCM files. Linear interpolation is sufficient for short notification
    cues and avoids depending on ffmpeg on the Raspberry Pi.
    """
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        frame_rate = source.getframerate()
        frames = source.readframes(source.getnframes())

    samples = _decode_pcm_samples(frames, channels, sample_width)
    if frame_rate != 44_100:
        samples = _resample_samples(samples, frame_rate, 44_100)
    return b"".join(
        max(-32768, min(32767, sample)).to_bytes(2, "little", signed=True)
        for sample in samples
    )


def _decode_pcm_samples(
    frames: bytes,
    channels: int,
    sample_width: int,
) -> list[int]:
    """Decode PCM frames to mono signed 16-bit integer samples.

    Multi-channel input is averaged per frame, though current assets are mono.
    """
    if channels < 1:
        raise ValueError("WAV must contain at least one channel")
    if sample_width == 1:
        raw_samples = [((byte - 128) << 8) for byte in frames]
    elif sample_width == 2:
        raw_samples = [
            int.from_bytes(frames[index : index + 2], "little", signed=True)
            for index in range(0, len(frames), 2)
        ]
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width}")

    if channels == 1:
        return raw_samples
    return [
        round(sum(raw_samples[index : index + channels]) / channels)
        for index in range(0, len(raw_samples), channels)
        if len(raw_samples[index : index + channels]) == channels
    ]


def _resample_samples(
    samples: list[int],
    source_rate: int,
    target_rate: int,
) -> list[int]:
    """Resample mono PCM samples with linear interpolation.

    Empty inputs remain empty, and a single input sample is repeated to preserve
    the target duration.
    """
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("sample rates must be positive")
    if not samples:
        return []
    target_count = max(1, round(len(samples) * target_rate / source_rate))
    if len(samples) == 1:
        return [samples[0]] * target_count
    return [
        _interpolate_sample(samples, index, target_count)
        for index in range(target_count)
    ]


def _interpolate_sample(samples: list[int], index: int, target_count: int) -> int:
    """Return one linearly interpolated sample for a resampled stream.

    The first and last output samples match the first and last source samples.
    """
    position = index * (len(samples) - 1) / max(target_count - 1, 1)
    left = int(position)
    right = min(left + 1, len(samples) - 1)
    fraction = position - left
    return round(samples[left] * (1 - fraction) + samples[right] * fraction)
