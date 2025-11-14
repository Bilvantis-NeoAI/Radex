from app.database import engine
from sqlalchemy import text

with engine.begin() as conn:  # begin() commits automatically
    result = conn.execute(
        text("UPDATE provider_configs SET is_enabled = true WHERE provider = 'sharepoint'")
    )
    if result.rowcount == 0:
        raise RuntimeError("⚠️ SharePoint provider row not found or not updated!")

print("✓ SharePoint provider enabled in database")
