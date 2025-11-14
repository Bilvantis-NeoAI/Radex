from app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text("""UPDATE provider_configs SET is_enabled = true WHERE provider='sharepoint'"""))

print('✓ SharePoint provider enabled in database')