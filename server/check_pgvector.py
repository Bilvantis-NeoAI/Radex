#!/usr/bin/env python
from app.database import engine
from sqlalchemy import text

try:
    conn = engine.connect()
    result = conn.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"))
    row = result.fetchone()

    if row:
        print(f"✅ pgvector extension: {row[0]} (version {row[1]})")
        print("🎯 RAG vector search will work!")
    else:
        print("❌ pgvector extension: NOT INSTALLED")
        print("📋 To install:")
        print("   psql -U your_username -d your_database")
        print("   CREATE EXTENSION IF NOT EXISTS vector;")
        print("   \\q")

    conn.close()
except Exception as e:
    print(f"❌ Database connection error: {e}")
    print("Make sure you're in the server directory with your virtual environment activated")
