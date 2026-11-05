"""HTTP representation for signed Slack commands and OAuth callbacks."""

import time
from collections.abc import Callable
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Cookie, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from busy_profit.oauth_storage import OAuthStorage
from busy_profit.slack_access import SlackAccessService
from busy_profit.slack_oauth import SlackOAuthService


def slack_router(
    access: SlackAccessService,
    oauth: SlackOAuthService,
    storage: OAuthStorage,
    client_id: str,
    redirect_uri: str,
    installation_key: str,
    clock: Callable[[], int] = lambda: int(time.time()),
    reports: Callable[[dict[str, str]], None] | None = None,
) -> APIRouter:
    """Bind Slack transports to application services without accessing tables.

    Public initiation is browser-bound; only the configured workspace is accepted.
    """
    router = APIRouter()

    @router.get("/slack/oauth/start")
    def start() -> RedirectResponse:
        """Create browser-bound state without exposing an operator secret.

        The state cookie is secure, HTTP-only and limited to OAuth callbacks.
        """
        state = storage.issue_state(clock())
        query = urlencode({
            "client_id": client_id, "redirect_uri": redirect_uri, "state": state,
            "scope": "commands,users:read,chat:write,files:write,channels:read,groups:read",
        })
        response = RedirectResponse("https://slack.com/oauth/v2/authorize?" + query, status_code=303)
        response.set_cookie("profit_oauth_state", state, max_age=600, secure=True,
            httponly=True, samesite="lax", path="/slack/oauth")
        response.headers["Cache-Control"] = "no-store"
        return response

    @router.get("/slack/oauth/callback")
    def callback(
        code: str = "",
        state: str = "",
        profit_oauth_state: str = Cookie(default=""),
    ) -> HTMLResponse:
        """Complete the browser-bound exchange without exposing token payloads.

        Always remove the temporary cookie after a successful installation.
        """
        try:
            oauth.complete(code, state, profit_oauth_state, clock())
        except (ValueError, PermissionError) as error:
            raise HTTPException(400, "Slack installation could not be verified") from error
        response = HTMLResponse("BUSY Profit installed. You can close this window.")
        response.delete_cookie("profit_oauth_state", path="/slack/oauth")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @router.post("/slack/commands")
    async def command(
        request: Request,
        background_tasks: BackgroundTasks,
        x_slack_request_timestamp: str = Header(default=""),
        x_slack_signature: str = Header(default=""),
    ) -> Response:
        """Read a bounded raw body before signature validation and issuance.

        Never send credentials into a channel or include them in error bodies.
        """
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 16384:
                raise HTTPException(413, "Command too large")
        from starlette.concurrency import run_in_threadpool
        try:
            if reports is not None:
                fields = await run_in_threadpool(access.verify, bytes(body),
                    x_slack_request_timestamp, x_slack_signature, clock())
                if fields.get("text", "").strip() != "access":
                    background_tasks.add_task(reports, fields)
                    if fields.get("channel_id", "").startswith(("C", "G")):
                        return Response(status_code=200)
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"response_type": "ephemeral", "text": "Preparing your private report…"})
            code = await run_in_threadpool(access.execute, bytes(body),
                x_slack_request_timestamp, x_slack_signature, clock())
        except PermissionError as error:
            raise HTTPException(403, "Employee access required") from error
        except ValueError as error:
            raise HTTPException(400, "Invalid Slack command") from error
        from fastapi.responses import JSONResponse
        return JSONResponse({"response_type": "ephemeral", "text": "Your personal BUSY Profit PIN: " + code + "\nIssuing a new PIN revokes this one."})

    return router
