-- Run once against existing DBs (Docker volume) before restarting services.
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS technique_id VARCHAR(20);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS recommended_action TEXT;
