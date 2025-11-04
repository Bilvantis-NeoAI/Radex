-- Migration: Add Confluence Provider Support
-- Description: Adds Confluence to ProviderType enum and makes tenant_id nullable
-- Date: 2025-01-03

-- Step 1: Add 'confluence' to ProviderType enum
ALTER TYPE providertype ADD VALUE IF NOT EXISTS 'confluence';

-- Step 2: Make tenant_id nullable (it was required for SharePoint but optional for Confluence)
ALTER TABLE provider_connections ALTER COLUMN tenant_id DROP NOT NULL;

-- Step 3: Update comment for tenant_id to reflect generic usage
COMMENT ON COLUMN provider_connections.tenant_id IS 'Provider instance ID (Microsoft 365 tenant ID or Atlassian cloud ID)';

-- Step 4: Update comments for provider_item_refs columns to reflect multi-provider usage
COMMENT ON COLUMN provider_item_refs.drive_id IS 'Container ID (SharePoint drive ID or Confluence space key)';
COMMENT ON COLUMN provider_item_refs.item_id IS 'Item ID (SharePoint item ID or Confluence page/content ID)';

-- Step 5: Insert Confluence provider config (if not exists)
INSERT INTO provider_configs (provider, is_enabled, created_at, updated_at)
VALUES ('confluence', false, NOW(), NOW())
ON CONFLICT (provider) DO NOTHING;

-- Verification queries (optional - for manual verification)
-- SELECT * FROM provider_configs WHERE provider = 'confluence';
-- SELECT enum_range(NULL::providertype);
