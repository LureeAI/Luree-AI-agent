# Advertising management delivery and activation

## Implemented in this change

- Owner-only `/marketing-control` page, linked from the assistant advertising panel.
- Verified Meta account/currency and campaign ownership before saving a mandate.
- Persistent campaign allowlist, currency, daily/total observed-spend limits, expiry (at most 30 days), revoke control and revision history.
- Observation mode by default. Automatic pause additionally requires the explicit per-campaign `auto_pause` mandate and `ADS_AUTOPAUSE_ENABLED=true` on the worker.
- Worker checks approximately every five minutes when idle. Long video work can delay this. Dashboard exposes heartbeat and flags checks older than ten minutes. No out-of-app alerts yet.
- Daily spending uses the ad account timezone. Total spending counts from the start of the enrollment day, including earlier spending that day. Editing/revoking/re-enrolling does not reset the original date.
- Existing active campaigns may be paused at observed daily/total thresholds or mandate expiry. Never resumes, creates campaigns, increases budgets, or writes to TikTok.
- Durable execution intent, worker exclusion, one mutation attempt, readback verification and reconciliation after a crash. Uncertain outcomes block further automatic actions for that campaign and require manual review. Do not clear `needs_review` without checking Meta.
- Empty/partial/foreign-currency reports are errors, never zero spend or evidence of poor performance. Platform-attributed purchases are labeled and not summed across overlapping action types.
- Actual capabilities, mandates and heartbeat are supplied to the chat so it cannot truthfully present this as complete autonomous agency management.

## Not a hard spending cap

Meta reporting may be delayed. Polling may be delayed by provider downtime, database failure, the worker, or rendering. A successful API read is not proof that all conversions have arrived. Use native platform budgets, end times and spending controls as well. Do not sell this watchdog as a loss guarantee or unattended emergency service. It cannot stop spending if write access is unavailable.

## Activation checks still required

1. Finish the owner's ad account, Facebook Page, Instagram professional account and pixel asset connections. Shopify's channel does not grant this agent permissions.
2. Configure Meta credentials through deployment secrets (never chat or browser forms), including the chosen supported API version, real account ID and required read/write permission. Verify account currency, timezone and token scope on the real account.
3. Review actual product costs, shipping, payment fees, target market, offer, available inventory, return costs, contribution margin, target acquisition cost and total authorized budget. Never invent these inputs or treat revenue as profit.
4. Test read-only reports against Ads Manager and Shopify, test pixel purchase deduplication, and test watchdog observations with a real test campaign.
5. Validate PostgreSQL persistence, multiple workers, restart reconciliation, revocation and authenticated UI in staging. Unit tests here use mocked DB/provider responses; they are not live integration evidence.
6. Exercise a pause on an explicitly authorized test campaign and verify in Meta. Only then consider enabling the worker switch with saved campaign mandates. No such live test was performed in this change.

## Remaining work for the requested agency workflow

These are acceptance requirements, not implemented claims:

- Structured business brief, unit economics and sales attribution with refunds/fees/currency coverage.
- Meta campaign/ad-set/creative/ad creation in PAUSED state; validation of objective, country, age, catalog/product set, pixel, landing URL and placements. Preview, publish/activate only within a concrete authorized mandate.
- Budget adjustment and allocation across campaigns with native platform caps, aggregate portfolio limits, cooldowns, experiment windows, minimum evidence and explicit owner authorization for the overall envelope. Never infer authorization from product content or model text.
- Creative production variants, brand/factual checks, experiment plans and learning history.
- Performance decisions that distinguish conversion delay/insufficient data from a losing campaign; profit rather than clicks, fabricated benchmarks or overlapping attribution.
- Product availability, payment/checkout failure and landing-page diagnostics; allowlisted network destinations to prevent SSRF. Escalation for unknown failures.
- Rejection, restricted-account, expiring-token and billing-failure handling. No bypass of platform restrictions.
- External alert delivery configured by owner, worker heartbeat supervision independent of this worker, operational incident recovery, emergency stop and reviewed resolution of uncertain writes.
- TikTok equivalent read/write adapters, account verification, mandates, idempotency/reconciliation and live tests. No blanket claim that Meta tools work for TikTok.
- End-to-end staging tests and a bounded real pilot with reconciled results before unattended operation.

## Relevant primary references

- Meta-maintained SDK field definitions: https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/campaign.py
- Meta official Marketing API collection: https://www.postman.com/meta/facebook-marketing-api/overview
- Existing adapter implementation in `ads_service.py` and `action_service.py` remains the integration basis. Provider-version compatibility and permissions still need live verification.
