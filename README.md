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


### Advertising report verification

Chat can request read-only ad reports with server-resolved periods (today, yesterday,
last 7/30 completed days, previous calendar month, current month, or a custom range
of up to 31 inclusive days). Meta periods use the verified ad account timezone.
The report includes the account identity, currency, range and partial-day flag.
Missing credentials and failed reads remain unavailable data, never zero sales.
TikTok relative dates currently use Asia/Seoul and require advertiser-timezone confirmation.

The owner-only `GET /ai/marketing/verify` endpoint and **فحص ربط ميتا** button verify
the account metadata and an Insights read. Configure `META_ACCESS_TOKEN`,
`META_AD_ACCOUNT_ID` and `META_API_VERSION` on the web service. Optional
`META_EXPECTED_ACCOUNT_NAME`, `META_EXPECTED_CURRENCY`, `META_EXPECTED_TIMEZONE`
reject unexpected account metadata. Verification does not expose credentials.
Token expiry remains unknown; account task names do not prove write access.
No live Meta connection is claimed until verification succeeds.

Approved actions now commit an `executing` claim before any external mutation.
An interrupted execution cannot be approved again. Meta pause additionally reads
back the campaign status; an uncertain result needs review. The authenticated,
CSRF-protected `POST /ai/actions/<id>/reconcile` only reads campaign state and never
repeats the pause. An active state leaves the uncertain claim in place.
No ad launch, budget change or automatic execution has been added.

## Durable advertising warehouse

The additive `migrations/001_advertising.sql` migration introduces account metadata,
entity hierarchy, sync jobs, immutable daily snapshots, current snapshot pointers,
and typed numeric facts with separate action counts/values. Existing Shopify tokens,
messages and approvals are untouched. `advertising_store.prepare` applies it once
under a PostgreSQL advisory lock. PostgreSQL remains portable across hosts.

The private **أرشيف نتائج الحملات** panel queues a selected platform and up to 31
completed account-local dates. Run `python advertising_worker.py` as a separate
process with the same DATABASE_URL, SHOPIFY_STORE_DOMAIN and advertising credentials.
Queued does not mean synced; job state and completed days are visible. Multiple
workers are excluded by a session advisory lock. A crashed running job becomes failed
on restart; completed daily partitions survive, and the owner can request a new sync.
There are at most four pending/running jobs per store. No automatic provider write,
ad launch, budget increase, model API call or paid subscription is introduced.
The additional process consumes hosting resources; storing snapshot revisions uses
PostgreSQL storage. No automatic deletion/retention is performed.

Readers fetch **campaign, ad group and ad** levels independently for each day.
Meta splits publisher_platform (Facebook, Instagram and any other returned placements).
TikTok covers Auction BASIC reports only, not TikTok Shop GMV Max, organic activity
or every Ads Manager dimension. Lower-level TikTok hierarchy may be incomplete.
Meta account currency/timezone are verified using its existing account reader.
TikTok account ID, currency and timezone are checked with advertiser/info; unrecognized
zones (including offset-only responses) fail closed rather than defaulting to Seoul.
Access tokens remain environment secrets and are never written to warehouse JSON.
Missing permissions or unsupported metric/dimension combinations fail the job,
leaving previously published partitions intact; no successful live connection is
implied by code deployment.

A whole level/day publishes in one transaction only after complete pagination and
validation. Re-syncing replaces that partition pointer, preserving the earlier
snapshot for audit without double counting. Even an empty verified report publishes
an explicit zero-row partition; missing or failed days never become zero. An older
request cannot overwrite a newer partition. Account currency or timezone changes
require explicit reconciliation. Campaign, adgroup and ad totals must not be added
together. Decimal values are preserved in storage; totals recompute CTR/CPC/CPM from
summed base metrics and keep unknown metrics null. Reach/frequency are not summed.

Actions and values retain exact event names and attribution windows separately:
purchase aliases/windows are never added together. Platform attribution is not proof
of a Shopify order. TikTok generic conversion is not necessarily purchase, so ROAS,
purchase CPA and profit are not fabricated. A budget, objective, targeting, creative
asset or demographic not supplied by the report is **not** inferred; these richer
resource/dimension adapters remain future work. This is an integrated performance
archive, not a claim that every field from every platform is available.

The model can call `read_ad_archive_status` to discover stored account IDs and then
`read_ad_history` with platform/account/dates/level (up to 92 inclusive days and 5,000
rows; larger reads fail rather than truncate). It must disclose missing dates and
snapshot timestamps. Stored history can be read even after provider tokens expire.
Live `read_ad_report` remains distinct and unchanged by archive availability.

Owner-only endpoints:
- `GET /ai/marketing/archive/status`
- `GET /ai/marketing/archive?platform=meta&account_id=123&start=2026-10-01&end=2026-10-07&level=campaign`
- `POST /ai/marketing/sync` with JSON platform/start/end and the normal CSRF header.

Validation: `python -m unittest discover -s tests -v`.
Optional real PostgreSQL integration suite: set `TEST_ADS_DATABASE_URL` to an **empty,
disposable test database** and run the same command. Integration tests create a uniquely named schema in that test database and remove
it after the run; existing schemas are not truncated. Never point this
variable at production. Back up the production database before normal deployment.

A GitHub Actions job runs the full suite against a disposable PostgreSQL 16 service.
Local SQL integration can also use a PostgreSQL-compatible PGlite server; that validates
SQL/storage behavior but does not prove native PostgreSQL multi-process locking.

## Marketing decision support and monitoring

`marketing_analysis.py` is a deterministic analysis engine; `marketing_manager.py`
persists owner policies, analysis evidence, deduplicated in-app alerts and review
outcomes. The owner panel provides per-order average product/shipping costs, payment
fees, refund/tax estimates, account currency, exact purchase event, revenue-basis
confirmation, a daily spend alert and an explicit monitoring opt-in. Unknown costs
remain null. Do not use per-piece costs for multi-item orders. Separate account
policies must be reviewed when switching accounts.

Analyses compute weighted CTR/CPC/CPM, exact-event purchase CPA/ROAS and estimated
contribution before/after ads. Currency mismatches, incomplete or stale snapshots,
unknown dates/timezones and immature conversion dates block performance decisions.
Only one exact Meta action name is used; purchase aliases/windows are not summed.
Absent purchase values remain unknown. A default two-day conversion buffer is only
an owner-configurable heuristic; increase it to match actual attribution and delay.
Re-sync older dates to incorporate delayed conversions.

The engine compares one level at a time, using adjacent equal-length periods with
matching account/currency/timezone/attribution, and reports spend, CTR, purchase CPA,
ROAS and contribution changes for matching entities. Missing previous data prevents
comparison. It does not claim statistical significance or causal audience insights.
Default review gates are 1,000 impressions, 50 clicks, five purchases and 0.5% CTR;
these are transparent heuristics, not universal media-buying rules. Cost estimates
exclude overhead and any unspecified costs. They are platform-attributed contribution,
not reconciled Shopify accounting profit or incremental sales.

Recommendations include request more data, continue observation, review creative,
hold, propose pause, or propose a limited budget increase (default at most 15%, policy
guardrail 25%). No proposal automatically pauses, launches, edits or spends. Owner
`accepted_for_review`, reject and defer choices are append-only review records with
source analysis IDs, not execution. Review campaign objective, current budget, tracking,
margin assumptions and provider state before a separate approved change.

The existing `advertising_worker.py` also schedules opt-in hourly refreshes of two
seven-day periods, excluding the policy conversion-delay buffer. It respects the
stored account ID and does not silently switch to new credentials. Analysis and optional Shopify reconciliation run after a successful queued refresh
when monitoring is enabled. Separate refresh/analysis/reconciliation health is shown
in the panel; a sync completing does not prove every downstream analysis succeeded. Alerts are private
in-app only; no push/email/WhatsApp notifications or 24/7 human supervision is claimed.
A failed refresh leaves prior data and warnings intact. Acknowledgement and review do
not execute platform changes. Monitoring is off until explicitly saved by the owner.

TikTok generic Auction conversion is never purchase. Archive sync now requests explicit
website complete_payment and total_complete_payment_rate (the provider's total monetary value field) at adgroup/ad levels. The normalized event is
tiktok_website_complete_payment. Campaign purchase totals roll up the disjoint
adgroup grain only, never ads plus adgroups. Missing parent IDs or any missing
count/value remain unavailable. Provider compatibility/permissions must still be
verified on the live advertiser account; unsupported field combinations fail the sync. No creative asset reading,
demographic/targeting ingestion, experiment design automation, automatic ad launch,
exact platform-event-to-Shopify-order identity matching or guaranteed business outcome is included.

Additional owner-authenticated endpoints (writes also require CSRF):
- GET/PUT `/ai/marketing/policy` (platform/account_id and owner policy)
- POST `/ai/marketing/analysis` (platform/account_id/start/end/level)
- GET `/ai/marketing/manager` (saved analyses, alerts and review audit)
- POST `/ai/marketing/alerts/<id>/acknowledge`
- POST `/ai/marketing/decisions` (evidence reference and review outcome)

The model's `analyze_ad_performance` tool uses saved policies only. It cannot invent
costs, change policies, acknowledge alerts or execute decisions. Policies and analysis
are stored additively beside the warehouse. Production rollout and live account
validation remain separate from local test success.


## Purchase, funnel and Shopify reconciliation extension

Archive sync requests explicit TikTok website purchases/value and landing-page/cart
metrics at supported lower levels, alongside video play/retention metrics. Meta
archive reads now include link clicks, daily reach/frequency and video quartiles.
Legacy live reports remain basic unless website_metrics is explicitly requested.
Every level is validated before publishing any level for that day; unsupported fields,
invalid values or incomplete pagination do not silently become zero. Later database
failures can still leave valid independently committed levels; job state and per-level
coverage must be checked. Historical snapshots need re-sync to contain new metrics.

Configure purchase_event=tiktok_website_complete_payment for TikTok website purchase
analysis. App, onsite and generic conversion events are never substituted. Shopify
Pixel/Events API configurations may require different event families; this adapter
covers the documented website complete_payment family only and requires live validation.
Sources:
- https://business-api.tiktok.com/portal/docs/supported-metrics-in-creative-basic-reports/v1.3
- https://business-api.tiktok.com/portal/docs/supported-metrics-for-a-dimension-in-basic-reports/v1.3

Owner-configured funnel_events maps exact landing_page_view/add_to_cart/initiate_checkout
names from Meta actions. TikTok normalized landing-page/cart events have verified
field mappings; an unavailable checkout metric stays unavailable. Ratios compare
attributed event counts, not unique session cohorts. They can exceed 100% and are
flagged rather than clamped. Video 2s/6s/completion ratios, hypotheses for opening
variants and descriptive CPA/ROAS rankings are evidence aids, not creative inspection,
audience demographic profiling, causal tests or statistical winners.

POST /ai/marketing/reconcile (platform/account_id/start/end) reads Shopify orders
with full pagination and strict UTC boundaries derived from the selected ad account
timezone, limited to 31 dates/25,000 orders/90 seconds. The GraphQL operation was
cross-checked with the Admin schema and executed successfully through Shopify's
validating query tool. The app still uses its own stored token and configured API
version, so its read_orders/read_all_orders scopes must be verified independently.
Without read_all_orders, older-than-60-day requests fail rather than imply completeness.
The reader excludes test orders, separates cancelled/unpaid orders, and preserves
unknown currency/amount errors. It does not request names, email, addresses or phones.

The reconciliation compares a **created-order cohort**: received/refunded fields are
current cumulative amounts for those orders, including cash for cancelled non-test
orders. They are not payment/refund transactions occurring during the report dates.
Net cash includes taxes/shipping and is not accounting revenue/profit. Numeric paid
last-touch UTM campaign IDs, from ready customer journeys, can associate paid orders
with campaigns actually present in the archive. Missing/organic/non-numeric/other
source evidence is listed as unmatched. No fuzzy name matching, first-touch fallback,
click-ID guessing, exact event-ID linkage or cross-platform conversion summation occurs.
Only aggregate reconciliation evidence is stored; raw order/customer/UTM data is not.
Ad event timing/windows and Shopify creation/payment timing differ, so a discrepancy
is not automatically a tracking error or an incremental sale.

POST /ai/marketing/tracking-url returns a future-facing, unpublished numeric campaign/ad
UTM link. Set SHOPIFY_PUBLIC_STORE_URL to the merchant HTTPS storefront (for this store,
https://lureefashions.com). Destination hosts are restricted to that configured host
or SHOPIFY_STORE_DOMAIN, and unrelated query parameters/click identifiers are stripped.
No ad is changed or published, and past missing UTMs cannot be reconstructed.

The model's reconcile_ad_orders tool returns the same aggregate evidence. Monitor
health records downstream failures without raw provider errors. Alerts update their
evidence on repeated observations; conditions no longer present in a new analysis of
the same ending date/grain are marked resolved. Review records remain an audit trail;
no advertising execution has been enabled by these additions.

Shopify references:
- https://shopify.dev/docs/api/admin-graphql/2026-04/objects/Order
- https://shopify.dev/docs/api/admin-graphql/2026-04/objects/CustomerJourneySummary
- https://shopify.dev/docs/api/admin-graphql/2026-04/objects/UTMParameters


### Scaling evidence gate
By default require_shopify_confirmation is true. Before any budget-increase proposal,
the manager requires a reconciliation fetched within 24 hours for the same date range,
matching account/store currencies, complete ad coverage and at least one observed
paid last-touch order for the same campaign. Ad/adgroup entities resolve their parent
campaign through saved hierarchy. Missing hierarchy or UTM evidence blocks the scaling
proposal; it never guesses a match. A successful match is still not causal proof.
The pure metric engine can identify an opportunity, but the persisted manager report
applies this additional evidence gate. Descriptive rankings do not bypass it.
An explicit owner policy can disable this gate; the standard owner UI leaves it on.
Supported purchase events are constrained on policy save, preventing a cart/checkout
or generic conversion field from being silently labeled a purchase. Custom event
families need a reviewed adapter before use.

Monitoring now reconciles Shopify first, then analyzes successful refreshes. Refresh,
analysis and Shopify reconciliation have independent visible health states. A failed
Shopify read leaves scaling blocked unless a qualifying still-fresh review exists.
This is local, tested implementation; production deployment, native PostgreSQL CI,
live advertiser metric compatibility and actual conversion attribution validation
must be completed before claiming operational readiness.

The scaling gate also requires the policy minimum paid-order sample and positive
estimated contribution from the observed Shopify cash cohort after its actual
refunds, owner per-order costs, estimated fees/tax and entity ad spend. It does not
subtract an assumed refund percentage again. At ad level an exact numeric ad UTM
match is required; adgroups aggregate matched ads through verified stored hierarchy.
Campaign-only evidence does not authorize an ad-level scaling proposal. This remains
an estimate from observed last-touch tags, not audited/incremental profit.
