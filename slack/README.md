# BUSY Profit Slack app

Import `manifest.json` in the Slack app configuration. The endpoints are planned
runtime routes and must be deployed before interactive testing. Reinstall the app
after changing scopes. No message-history permission or public-channel posting
permission is requested; invite the bot to approved report channels.

Runtime secrets: `SLACK_SIGNING_SECRET`, a bot access token, expected workspace ID,
and the persistent access-code HMAC pepper. Existing rotating tokens also require
the app's OAuth client ID and client secret to renew them; never commit any token.

Personal reports use the member's profile timezone. Channel reports are recomputed
in UTC. Every chart labels its period and timezone. Private reports are the default;
channel sharing requires confirmation and a server-side approved-channel check.
External/shared channels are rejected. Personal access codes are never published.

The bot requires `users:read` for profile timezone and membership checks,
`channels:read`/`groups:read` for destination verification, `chat:write` for
confirmed publication, and `files:write` for privately hosted chart images.
Email access is not required because credentials bind to Slack user IDs.
