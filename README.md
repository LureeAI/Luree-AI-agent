# Luree AI Agent

## Private deployment

Set Railway service Variables before merging/deploying this version:

- `AGENT_PASSWORD`: your private login password, at least 12 characters. Never commit or send it in chat. Alternatively use `AGENT_PASSWORD_HASH` generated with Werkzeug.
- `AGENT_SESSION_SECRET`: a separate random secret of at least 32 characters; keep stable across redeployments.
- Existing `DATABASE_URL`, `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `OPENAI_API_KEY` remain required.

Generate a session secret locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste it directly into Railway Variables.

Use HTTPS. Open `/assistant`; sign in with your password. The app blocks all private routes if login configuration is missing. Public `/health` and `/ai/health` contain no store data. Sessions expire after 12 hours; POST/PUT requests require a CSRF token. Five failed login attempts block further attempts for five minutes across workers (single-owner deployment). `/logout` clears the session.

## Persistent memory

PostgreSQL tables are created automatically without replacing Shopify tokens. Chat exchanges are saved atomically. The UI reloads the last 100 messages; the model receives the latest 20 messages. All exchanges remain in the database, but older messages beyond the context window are not automatically summarized. Saved owner instructions (up to 4000 characters) are included in each turn and editable from the interface. Failed generation does not create a saved exchange. Use PostgreSQL backups when migrating hosts.

## Shopify coverage

Products and accessible orders are fetched with cursor pagination, 100 records per page. All product routes use the same reader and stored OAuth connection. Shopify normally restricts order access to the last 60 days. Older orders need Shopify approval for `read_all_orders` and reauthorization; this version reports current scope coverage and never assumes all-time order access.

Pagination failures, repeated cursors, and excessive sync size raise errors rather than silently returning a partial sample. Synchronous reads allow up to 25,000 records / 90 seconds per resource; model context over 250,000 characters is rejected pending bulk analysis support. For large stores use background bulk operations. Product price ranges are complete aggregates; variant records are not downloaded in this phase.

No new paid services are introduced. More store data and recent conversation context can increase existing text API usage. Browser speech uses device voices; dictation support varies by browser.

Start: `gunicorn app:app --bind 0.0.0.0:8080 --timeout 240`

Verify: `python -m unittest discover -s tests -v`
