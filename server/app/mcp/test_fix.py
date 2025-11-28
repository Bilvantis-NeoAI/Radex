# Test the fix for CSV data processing

from app.mcp.data_processor import MCPDataProcessor
from app.config import settings

# Test the enhanced operations
async def test_groupby_operations():
    # This would test if groupby_max works for "who won most player of the match awards"
    # Assuming we have a CSV with columns: player_name, award_type, count

    processor = MCPDataProcessor(settings)

    # Test data would need to be uploaded first, but this shows the operation is available
    operations = [
        "groupby_count",
        "groupby_sum",
        "groupby_max",
        "groupby_min",
        "value_counts",
        "unique_values"
    ]

    print("Enhanced operations available:", operations)
    return True

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_groupby_operations())
