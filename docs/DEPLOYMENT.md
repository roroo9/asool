# Deployment

| Part | Platform | Address |
|---|---|---|
| Website (Next.js) | Vercel, project `asool`, Hobby, functions in `fra1` | https://asool-tawny.vercel.app |
| API (FastAPI) | Railway, project `asool`, service `asool-api`, Hobby, Amsterdam (`europe-west4`), one always-on replica | https://asool-api-production.up.railway.app |

**Why this split.** Railway runs the API as a container that stays up all the time: no sleep and no cold start. Vercel serves the Next.js site and the 30 page images from its global network. The site forwards `/api/*` to the API, configured by `API_URL` in `web/next.config.ts`, so browsers talk only to the site. The API accepts cross-origin browser calls only from the site (`CORS_ORIGINS`).

## Settings
- **Railway variables:**
  - `OPENROUTER_API_KEY` (secret)
  - `REVIEW_TOKEN`: the production review code (secret)
  - `CORS_ORIGINS`
  - `DAILY_BUDGET_USD=3`
  - `OPENROUTER_BUDGET_USD=40`
  - `HARD_BUDGET_USD=38`
  - `ANSWER_RATE_LIMIT_PER_HOUR=20`
  - `PORT=8000`
- **Vercel variable:** `API_URL`, the Railway address.
- **Secrets** are set from the local `.env` and never committed.

## Redeploy
**API:**
1. Clone the repository.
2. Copy into the clone, as a private upload only: `data/reference/quran/kfgqpc/` (King Fahd Complex Hafs data) and `data/reference/quranenc/`. They are not redistributed on GitHub, and Railway's network cannot reach `download.qurancomplex.gov.sa`.
3. Remove those two paths from the clone's `.gitignore`, then run `railway up --service asool-api --ci`.

The Dockerfile downloads the Mushaf search vectors from the GitHub release `data-v1`.

**Website:** from `web/` (the page images in `web/public/pages` are uploaded from the local copy, never from GitHub), run:
```bash
vercel deploy --prod
```

## Monitoring
`.github/workflows/keepalive.yml` checks the site, the API through the site, and the API directly every 30 minutes. A failure turns the workflow red, and GitHub emails the owner. Repository variables: `ASOOL_SITE_URL`, `ASOOL_API_URL`.
