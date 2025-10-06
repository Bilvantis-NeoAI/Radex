-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Define enum type for auth provider
CREATE TYPE auth_type AS ENUM ('radex', 'okta');

-- Users table
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    auth_provider auth_type NOT NULL DEFAULT 'radex',  -- tells how user authenticates
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100),
    hashed_password VARCHAR(255),                      -- only for local users
    groups TEXT[],                                     -- only meaningful for Okta
    roles TEXT[],
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_logged_in TIMESTAMP,
    CHECK (
        (auth_provider = 'radex' AND hashed_password IS NOT NULL) OR
        (auth_provider = 'okta' AND hashed_password IS NULL)
    )
);

-- Folders table
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    owner_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, parent_id)
);

-- Documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    file_path TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    uploaded_by VARCHAR(255) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Permissions table
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    can_read BOOLEAN DEFAULT false,
    can_write BOOLEAN DEFAULT false,
    can_delete BOOLEAN DEFAULT false,
    is_admin BOOLEAN DEFAULT false,
    granted_by VARCHAR(255) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, folder_id)
);

-- Embeddings table
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

-- Chat sessions table
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat messages table
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    sources JSONB DEFAULT '[]',   -- list of sources
    chat_metadata JSONB DEFAULT '{}',  -- arbitrary key-value metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_folders_parent ON folders(parent_id);
CREATE INDEX idx_folders_owner ON folders(owner_id);
CREATE INDEX idx_documents_folder ON documents(folder_id);
CREATE INDEX idx_permissions_user_folder ON permissions(user_id, folder_id);
CREATE INDEX idx_embeddings_document ON embeddings(document_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops);
-- Sessions by user (fetch all chats of a user)
CREATE INDEX idx_chat_sessions_user ON chat_sessions(user_id);

-- Messages by session (fetch conversation history in order)
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);

-- Messages chronological order (useful if you often fetch ordered chats)
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);

-- Insert default admin user (password: admin123456)
-- Password hash generated with bcrypt for 'admin123456'
-- INSERT INTO users (user_id, email, username, hashed_password, is_active, is_superuser) 
-- VALUES (
--     '001',
--     'admin@gmail.com', 
--     'super_admin', 
--     '$2b$12$lHxIUidRs7M4NTGG7bNu1exg0z/S9r/V7tPsuQABxdfDnL.xmesNC',
--     true, 
--     true
-- ) ON CONFLICT (email) DO NOTHING;