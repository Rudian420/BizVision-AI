-- ============================================================
-- BizVision AI — PostgreSQL Initialization Script
-- Enables pgvector extension and creates MLflow database
-- ============================================================

-- Enable pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Fuzzy text search

-- Create MLflow tracking database
CREATE DATABASE bizvision_mlflow;

-- Connect to MLflow database and enable required extensions
\c bizvision_mlflow;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Return to main database
\c bizvision;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'BizVision AI database initialized with pgvector v%',
        (SELECT extversion FROM pg_extension WHERE extname = 'vector');
END $$;
