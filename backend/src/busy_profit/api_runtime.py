"""Compose API, source indexing and Slack infrastructure for deployment."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from busy_profit.access import AccessRepository
from busy_profit.api import create_app, shared_key_policy
from busy_profit.oauth_storage import OAuthStorage
from busy_profit.slack_access import SlackAccessService
from busy_profit.slack_client import SlackClient
from busy_profit.slack_oauth import SlackOAuthService
from busy_profit.slack_routes import slack_router
from busy_profit.slack_reports import SlackReports
from busy_profit.view_import import ArchiveImporter
from busy_profit.view_service import ViewService
from busy_profit.view_storage import ObservationIndex


class APISettings(BaseSettings):
    """Load API runtime secrets without mixing them with browser build variables."""

    model_config = SettingsConfigDict(extra="ignore")
    profit_data: Path = Path("/data")
    profit_access_pepper: SecretStr
    profit_installation_key: SecretStr
    busy_profit_access_key: SecretStr = SecretStr("")
    slack_team_id: str
    slack_app_client_id: str
    slack_app_client_secret: SecretStr
    slack_app_signing_secret: SecretStr
    slack_access_token: SecretStr = SecretStr("")
    slack_refresh_token: SecretStr = SecretStr("")
    slack_redirect_uri: str = "https://profit.busy.truetug.info/slack/oauth/callback"


class TokenManager:
    """Serialize rotating-token refreshes within the single API process."""

    def __init__(self, settings: APISettings, storage: OAuthStorage, client: SlackClient) -> None:
        """Keep credential handling inside the infrastructure composition.

        Existing runtime tokens bootstrap only an otherwise empty installation.
        """
        self._settings, self._storage, self._client = settings, storage, client
        self._lock = Lock()

    def get(self) -> str:
        """Return a usable bot token, renewing expiring credentials atomically.

        Never fall back to an old token after a failed refresh.
        """
        with self._lock:
            now = int(time.time())
            team = self._settings.slack_team_id
            tokens = self._storage.tokens(team)
            if tokens is None:
                access = self._settings.slack_access_token.get_secret_value()
                refresh = self._settings.slack_refresh_token.get_secret_value()
                if not access:
                    raise ValueError("Slack installation required")
                if refresh:
                    renewed = self._client.refresh(refresh)
                    self._storage.save_tokens(team, renewed.access_token, renewed.refresh_token, now + renewed.expires_in)
                else:
                    self._storage.save_tokens(team, access, "", 0)
                tokens = self._storage.tokens(team)
            if tokens is None:
                raise ValueError("Slack installation required")
            access, refresh, expires = tokens
            if expires and expires <= now + 120:
                if not refresh:
                    raise ValueError("Slack reinstallation required")
                renewed = self._client.refresh(refresh)
                self._storage.save_tokens(team, renewed.access_token, renewed.refresh_token, now + renewed.expires_in)
                return renewed.access_token
            return access


def build_app():
    """Wire representation, services, domain projection and infrastructure.

    Source import runs outside request handling and retains the last good index
    on transient source failures. Run exactly one API worker for token rotation.
    """
    settings = APISettings()
    index = ObservationIndex(settings.profit_data / "views.sqlite3")
    importer = ArchiveImporter(settings.profit_data / "history.csv", index)
    storage = OAuthStorage(settings.profit_data / "slack.sqlite3")
    access = AccessRepository(settings.profit_data / "access.sqlite3", settings.profit_access_pepper.get_secret_value())
    client = SlackClient(settings.slack_app_client_id, settings.slack_app_client_secret.get_secret_value(), settings.slack_redirect_uri)
    tokens = TokenManager(settings, storage, client)
    shared = shared_key_policy(settings.busy_profit_access_key.get_secret_value())
    views = ViewService(index)
    app = create_app(views, lambda code: access.authorize(code) or shared(code))

    def eligible(user: str) -> bool:
        """Consult Slack membership using the current installation token.

        Network or token errors fail closed through the command handler.
        """
        return client.member(user, tokens.get()).eligible(settings.slack_team_id)

    app.include_router(slack_router(
        SlackAccessService(settings.slack_app_signing_secret.get_secret_value(), settings.slack_team_id, access, eligible),
        SlackOAuthService(storage, settings.slack_team_id, client.exchange), storage,
        settings.slack_app_client_id, settings.slack_redirect_uri,
        settings.profit_installation_key.get_secret_value(),
        reports=SlackReports(client, tokens.get, views, index).execute,
    ))

    @asynccontextmanager
    async def lifespan(application):
        """Index archives before serving and refresh them in a cancellable loop.

        Log error types only, avoiding sensitive source rows and credentials.
        """
        await asyncio.to_thread(importer.refresh)
        async def refresh() -> None:
            """Refresh the index every minute without blocking API requests.

            Keep the last consistent database snapshot when import fails.
            """
            while True:
                await asyncio.sleep(60)
                try:
                    await asyncio.to_thread(importer.refresh)
                except Exception as error:
                    logging.getLogger("busy_profit.api").warning("Index refresh failed: %s", type(error).__name__)
        task = asyncio.create_task(refresh())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    app.router.lifespan_context = lifespan
    return app
