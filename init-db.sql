-- Create Letta database and user
CREATE USER letta WITH PASSWORD 'letta';
CREATE DATABASE letta OWNER letta;
GRANT ALL PRIVILEGES ON DATABASE letta TO letta;

-- Enable pgvector extension in both databases
\c epsilon
CREATE EXTENSION IF NOT EXISTS vector;

\c letta
CREATE EXTENSION IF NOT EXISTS vector;
