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

## Automatic inventory monitoring

Deploy a second always-on service from the same repository with start command
`python inventory_worker.py`. Give it the same DATABASE_URL and SHOPIFY_STORE_DOMAIN.
The stored Shopify OAuth token is read from PostgreSQL. No OpenAI calls or new provider
subscriptions are used by this worker; a second Railway service uses Railway resources.

The worker retries every minute and performs a complete product read at most once every
15 minutes. PostgreSQL locking and an atomic transaction prevent duplicated alerts from
concurrent workers and partial scans. Keep the worker running even when the web UI is closed.
Existing web service start command is unchanged. This worker is portable to a standard
container/process on Google Cloud with the same environment and database.

Active products with totalInventory <= 50 create an initial alert. Subsequent alerts occur
only when entering low stock, entering out-of-stock, or recovering above 50 and dropping
again. Non-active and unknown-inventory products are ignored. This is product aggregate
inventory, not size/color variant monitoring. Acknowledgement does not reset the threshold.
Historical alerts retain the quantity at detection; they are not current stock reports.

Private interface: expand "تنبيهات المخزون". The last successful scan time and stale-worker
notice are shown, with the last 100 persisted alerts and per-alert acknowledgement.
Alerts are in-app only; no email/WhatsApp/push delivery is configured. AliExpress links
are search shortcuts, not verified supplier recommendations or automatic supplier research.
Do not confuse preserved owner instructions with an enabled monitor.


## Advertising reports and planning

Shopify social channels and this agent's API access are separate connections.
Connect Facebook and Instagram by Meta and TikTok channels in Shopify for catalog/pixel
setup. These channels do not give the agent advertising account API tokens.

For read-only Meta reports, set META_ACCESS_TOKEN with ads_read account access,
META_AD_ACCOUNT_ID and META_API_VERSION (explicit supported version, e.g. v25.0).
For TikTok reports, obtain authorized TikTok API for Business access and set
TIKTOK_ACCESS_TOKEN and TIKTOK_ADVERTISER_ID. Enter tokens only in host environment
secrets. Token issuance, app review and account permissions remain account-side tasks.
The UI reports configuration separately from a successfully verified API report.

Private endpoints: /ai/marketing/status and /ai/marketing/report?start=YYYY-MM-DD&end=YYYY-MM-DD.
Default: last seven completed dates using Seoul to select dates; providers interpret
report dates in their ad account timezone. Meta results split publisher_platform.
TikTok report currency remains unknown until confirmed from the account.
The agent includes available reports for marketing-related messages and can prepare
plans/copy. Unconnected accounts are disclosed, never represented by invented metrics.
Missing metrics are null, not zero. Platform-attributed conversions are not confirmed
Shopify orders; do not aggregate overlapping Meta actions or different currencies.

This version does not create/launch ads, publish social posts, change product prices,
or spend money. Those writes need separate adapters plus explicit campaign budget,
audience and creative approval. Supplier links remain search shortcuts.

API references:
- https://developers.facebook.com/docs/marketing-api/insights/
- https://developers.facebook.com/docs/marketing-api/insights/breakdowns/
- https://github.com/tiktok/tiktok-business-api-sdk/blob/main/python_sdk/docs/ReportingApi.md
- https://help.shopify.com/en/manual/online-sales-channels/social-commerce/facebook-instagram-by-meta/setup

## Reviewed execution

The model can save concrete proposals using a function tool. It cannot execute them.
Supported actions: product title, plain-text product description, and Meta campaign pause.
The owner sees target, before/after and reason in the private UI and approves/rejects.
Shopify writes require write_products. Meta pause requires ads_management; ads_read
only allows reporting. Full store administration and campaign creation are not yet implemented.

Proposals expire after 24 hours. Execution checks that the product/campaign snapshot
has not changed, locks the stored action, preserves product handles, escapes description
HTML and refuses already-decided actions. Transport uncertainty becomes needs_review
and is never automatically retried. Check the provider before creating a replacement.
All action and report endpoints retain the existing owner session and write CSRF protection.
No provider credentials or raw errors are returned to the model/UI.

## Dress video builder

The private assistant includes an Arabic "إنشاء فيديو فستان" panel. Select an active
Shopify product, choose 1–5 photos (up to the first 30 product images shown), choose
whether to show the price, and queue a 15-second 720×1280, 24fps MP4 with a hook, product showcase, price and CTA.
Images are contain-fitted to preserve the garment, with gentle zoom/crossfades.
English product titles and price overlays use actual product data at request time;
non-Latin titles fall back to a generic English headline. If variant prices differ,
the minimum is explicitly labeled From. An original synthesized instrumental is included.
The optional AI voiceover uses OpenAI gpt-4o-mini-tts/nova and the existing API credit;
the UI discloses this before creation, and narration is labeled as AI-generated.
Disable voice to avoid TTS charges. There is no generative video, automatic publication
or automatic ad launch.

Run the existing worker service using `python inventory_worker.py`: it now processes
video jobs as well as inventory scans. Without this process, jobs remain queued.
The web start command remains unchanged. The worker only requires the same
DATABASE_URL and SHOPIFY_STORE_DOMAIN to read the existing stored Shopify OAuth token.
Pillow and imageio-ffmpeg are installed from requirements.txt; the bundled FFmpeg
binary supports normal Linux x86_64 deployments. Other platforms can provide a
compatible binary with IMAGEIO_FFMPEG_EXE. Music is generated locally. Optional narration makes one paid OpenAI speech request
with no automatic API retries; rendering also consumes hosting CPU and database storage.
OPENAI_API_KEY is needed on the worker when voiceover is selected.

Jobs, selected image/price snapshots and completed MP4 bytes survive web redeploys
in PostgreSQL. Temporary rendering files are removed. For this small-store version
there is a limit of ten stored jobs and three queued/rendering jobs. Completed outputs
are capped at 15 MiB. The owner can explicitly delete old videos or queued requests
in the UI; active jobs cannot be deleted. No hidden retention deletion is performed.
For larger libraries migrate MP4 storage to an object store without changing jobs.

Photo downloads allow only HTTPS cdn.shopify.com, no redirects, bounded bytes/time
and bounded decoded pixels. No arbitrary user URL or shell command is accepted.
All routes retain owner login; create/delete require CSRF. Outputs stay private.
Failed jobs are shown as failed; abandoned rendering jobs become failed after
15 minutes when a worker resumes. Review the price against the current product
before publishing, as it may have changed since the snapshot.

Additional endpoints: GET /ai/videos/product?id=gid://shopify/Product/...
GET/POST /ai/videos; GET /ai/videos/<id>/file; DELETE /ai/videos/<id>.

Narration may use the default English script or an owner-provided script (max 40 words/
300 characters). Price in the default script comes from the approved image/price snapshot.
Custom scripts are owner copy and are not factual product verification. Voice requests
can fail if credit/model access is unavailable; the job reports failure rather than
silently dropping selected audio. Speech up to 22.5 seconds is gently sped up to fit
within the 15-second cut; longer speech requires a shorter script. Stock images are
not used and clothing is not reimagined by a video model.

### Three narration languages
Choose Arabic (`ar`), English (`en`), Korean (`ko`), or all three in the video panel. The all-three option atomically queues three versions using the same photos and visual design, with a separate native-language default script and narration per version. Custom scripts are edited separately in three fields; they are not automatically translated. Three versions require three free queue slots and three available storage slots. Each narration invokes a separate paid TTS request. Existing jobs default to English. Visual text remains the existing English design; this option localizes narration only.

### Automatic conversation recall
Each chat request searches all older stored messages for related keywords and adds bounded excerpts and nearby turns alongside the latest 20 messages and saved preferences. A standard PostgreSQL GIN full-text index supports Arabic, English and Korean Unicode terms using the simple dictionary. Retrieval is store-scoped, capped at six hits, eighteen excerpts and 12,000 content characters, with no duplicate recent messages. This is keyword/prefix retrieval, not semantic embeddings: paraphrases, Arabic spelling variants and Korean spacing differences may not match. Old excerpts are historical evidence, never approval to execute an action. No new service or external search/TTS API is needed. Excerpts increase model input usage. The index is created automatically; its first build can take time on a large history.

## Owner-reviewed product preparation

The preparation panel works on **existing Shopify products**. Import a chosen
AliExpress product using DSers as a Shopify draft with the supplier mapping first.
This change does not provide a merchant DSers API, import AliExpress links, or
independently check supplier availability. Recorded Shopify stock and owner
supplier confirmation are labeled separately. Supplier URLs are provenance only.

The owner enters a proposed uniform variant price, maximum variant purchase cost,
shipping cost and payment fees, all in shop currency. Missing inputs are not zero.
The Decimal calculation reports contribution and break-even before ads, taxes,
returns or other omitted expenses. The chat has read-only pricing and detailed
product tools for discussion. Final prices are selected in the panel, not by the
model. English copy/SEO generation uses OpenAI; the owner can edit everything.
Sizes/options are preserved, and unsupported garment facts must not be invented.
Copy generation sends product data and up to the first 12 eligible Shopify CDN photos to OpenAI for a proposed media order; unseen media must not be described as inspected. Existing media can be reordered, not deleted or regenerated. A proposed uniform
price also clears old compare-at prices, which is disclosed in the preview.

Previews persist in `agent_product_preparations` scoped to the connected shop.
Owner approval writes prices, copy/SEO and image order, then optionally activates
and publishes to an explicitly selected Shopify publication. Activating a draft
can expose it on previously assigned channels too; the panel discloses this.
Publishing requires owner supplier confirmation and complete price inputs.
Never recreate options/variants, change SKUs, inventory quantities, fulfillment
settings or handle, so existing DSers identifiers are preserved; mapping is not
independently validated. `write_products` is needed for editing and
`read_publications`/`write_publications` for publication. Existing installations
must grant the new scopes via Shopify app settings and reconnect; deploying code
alone does not grant them. Without publication scopes, edit-only preparation works.

Approval commits an executing claim before external writes. Stale full product
snapshots fail before writes; partial mutations, timeout or process loss must be
manually reconciled in Shopify and are never automatically retried. These operations
are not a cross-mutation atomic transaction, and Shopify does not provide a compare-
and-swap guard here; concurrent outside edits can still race preflight. Execution
state and last stage remain visible. Reconcile an uncertain operation in Shopify,
then use the explicit owner reconciliation control before making another proposal.

Endpoints under `/ai/product-preparations`: GET/POST root; GET product and
publications; POST copy, price, `<id>/approve`, `<id>/reject`, `<id>/reconcile`.
All are behind existing owner login and writes require CSRF. Limits: 100 variants
and media, 20 pending previews, and 24-hour approval expiry. Live store writes and
DSers mapping have not been exercised by the unit suite.

The default Gunicorn configuration uses a 180-second worker timeout for the
multi-step approval request. A custom start command can override this setting.
Copy generation has a 90-second timeout and no automatic OpenAI retries.
Preparation request bodies have a 64 KiB cap; field-level limits still apply.
