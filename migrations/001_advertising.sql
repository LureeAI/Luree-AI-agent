-- Additive PostgreSQL migration. Never changes existing Shopify or memory tables.
CREATE TABLE IF NOT EXISTS advertising_schema_versions (
    version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS advertising_accounts (
    shop TEXT NOT NULL, platform TEXT NOT NULL CHECK (platform IN ('meta','tiktok')),
    account_id TEXT NOT NULL, name TEXT, currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    timezone TEXT NOT NULL, metadata_source TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (shop, platform, account_id)
);
CREATE TABLE IF NOT EXISTS advertising_entities (
    shop TEXT NOT NULL, platform TEXT NOT NULL, account_id TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('campaign','adgroup','ad')),
    entity_id TEXT NOT NULL, name TEXT, parent_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (shop, platform, account_id, level, entity_id),
    FOREIGN KEY (shop, platform, account_id) REFERENCES advertising_accounts
);
CREATE TABLE IF NOT EXISTS advertising_sync_runs (
    id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, platform TEXT NOT NULL,
    account_id TEXT, start_date DATE NOT NULL, end_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    days_saved INTEGER NOT NULL DEFAULT 0, error_code TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ,
    CHECK (start_date <= end_date)
);
CREATE INDEX IF NOT EXISTS advertising_sync_shop ON advertising_sync_runs(shop, id DESC);
CREATE TABLE IF NOT EXISTS advertising_snapshots (
    id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, platform TEXT NOT NULL,
    account_id TEXT NOT NULL, report_date DATE NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('campaign','adgroup','ad')),
    attribution TEXT NOT NULL, requested_at TIMESTAMPTZ NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), run_id BIGINT REFERENCES advertising_sync_runs,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    FOREIGN KEY (shop, platform, account_id) REFERENCES advertising_accounts,
    UNIQUE (shop, platform, account_id, report_date, level, attribution, id)
);
CREATE TABLE IF NOT EXISTS advertising_partitions (
    shop TEXT NOT NULL, platform TEXT NOT NULL, account_id TEXT NOT NULL,
    report_date DATE NOT NULL, level TEXT NOT NULL, attribution TEXT NOT NULL,
    snapshot_id BIGINT NOT NULL,
    PRIMARY KEY (shop, platform, account_id, report_date, level, attribution),
    FOREIGN KEY (shop, platform, account_id, report_date, level, attribution, snapshot_id)
        REFERENCES advertising_snapshots(shop, platform, account_id, report_date, level, attribution, id)
);
CREATE TABLE IF NOT EXISTS advertising_facts (
    snapshot_id BIGINT NOT NULL REFERENCES advertising_snapshots ON DELETE CASCADE,
    entity_id TEXT NOT NULL, placement TEXT NOT NULL, dimensions JSONB NOT NULL DEFAULT '{}',
    spend NUMERIC CHECK (spend >= 0), impressions NUMERIC CHECK (impressions >= 0),
    clicks NUMERIC CHECK (clicks >= 0), metrics JSONB NOT NULL,
    actions JSONB NOT NULL DEFAULT '[]', action_values JSONB NOT NULL DEFAULT '[]',
    PRIMARY KEY (snapshot_id, entity_id, placement)
);
INSERT INTO advertising_schema_versions(version) VALUES (1) ON CONFLICT DO NOTHING;
