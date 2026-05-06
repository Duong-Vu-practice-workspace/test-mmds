-- PostgreSQL initialization script for OTTO Recommender System
-- Create database (already created by POSTGRES_DB env var)
\c otto_recommender;

-- User events table (raw events from Kafka)
CREATE TABLE IF NOT EXISTS user_events (
    id SERIAL PRIMARY KEY,
    session TEXT NOT NULL,
    aid INT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_events_session ON user_events(session);
CREATE INDEX idx_user_events_timestamp ON user_events(ts);
CREATE INDEX idx_user_events_type ON user_events(type);

-- Processed events table (with features)
CREATE TABLE IF NOT EXISTS processed_events (
    id SERIAL PRIMARY KEY,
    session TEXT NOT NULL,
    aid INT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    type TEXT NOT NULL,
    features JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processed_events_session ON processed_events(session);

-- Predictions table
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    session TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    predicted_items INT[],
    input_items INT[],
    model_type TEXT DEFAULT 'covisitation',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_predictions_session ON predictions(session);

-- Evaluation results table
CREATE TABLE IF NOT EXISTS evaluation_results (
    id SERIAL PRIMARY KEY,
    session TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    hit BOOLEAN,
    latency_ms DOUBLE PRECISION,
    metric_name TEXT,
    metric_value DOUBLE PRECISION,
    predicted_items INT[],
    actual_aid INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_evaluation_session ON evaluation_results(session);
CREATE INDEX idx_evaluation_metric ON evaluation_results(metric_name);

-- Anomaly alerts table
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id SERIAL PRIMARY KEY,
    session TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT,
    alert_timestamp TIMESTAMPTZ,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_type ON anomaly_alerts(alert_type);
CREATE INDEX idx_alerts_severity ON anomaly_alerts(severity);

-- User segments table
CREATE TABLE IF NOT EXISTS user_segments (
    session TEXT PRIMARY KEY,
    segment TEXT,
    session_length INT,
    click_count INT,
    cart_count INT,
    order_count INT,
    conversion_rate DOUBLE PRECISION,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Metrics summary table (for dashboard)
CREATE TABLE IF NOT EXISTS metrics_summary (
    id SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO otto;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO otto;
