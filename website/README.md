# BUSY Profit landing

The landing page is generated from the repository's root `README.md` and `screenshots/`; edit those files to change its content. `template.html` and `style.css` control presentation, and raw HTML in Markdown is escaped.

To preview locally, install `backend/requirements-dev.txt`, run `python website/build.py`, and serve `website/dist/` with a static HTTP server. The directory is generated and is not committed.

The backend image builds the page and publishes it under `data/public/landing/` at startup. A publication error is logged without stopping the sales collector. Caddy serves only `/`, `/style.css`, and `/screenshots/*` from this directory; the three CSV feeds keep their separate routes.

Changes to this directory, the root README, or screenshots trigger the backend image workflow so the published page follows the deployed revision.
