CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_ip VARCHAR(45) NOT NULL,
  destination_ip VARCHAR(45),
  destination_port INTEGER,
  protocol VARCHAR(10),
  event_type VARCHAR(50) NOT NULL,
  bytes_transferred INTEGER DEFAULT 0,
  username VARCHAR(100),
  raw_message TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_id UUID REFERENCES logs(id),
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  severity INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 10),
  anomaly_score FLOAT NOT NULL,
  model_used VARCHAR(50),
  event_type VARCHAR(50),
  source_ip VARCHAR(45),
  mitre_tactic VARCHAR(100),
  mitre_technique VARCHAR(100),
  technique_id VARCHAR(20),
  confidence DOUBLE PRECISION,
  recommended_action TEXT,
  explanation TEXT,
  raw_context JSONB,
  acknowledged BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_logs_timestamp ON logs(timestamp DESC);
CREATE INDEX idx_logs_source_ip ON logs(source_ip);
CREATE INDEX idx_alerts_timestamp ON alerts(timestamp DESC);
CREATE INDEX idx_alerts_severity ON alerts(severity DESC);
CREATE INDEX idx_alerts_acknowledged ON alerts(acknowledged);
