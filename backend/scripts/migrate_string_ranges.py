import sys
import os
import re

# Add the backend directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import SessionLocal
from app.db.models import YarnSupplier

def parse_lt_to_days(val):
    if not val or str(val).lower() == 'nan':
        return None, None
    nums = [int(x) for x in re.findall(r'\d+', str(val))]
    if len(nums) == 1:
        return nums[0] * 7, nums[0] * 7
    elif len(nums) >= 2:
        return nums[0] * 7, nums[1] * 7
    return None, None

def parse_moq(val):
    if not val or str(val).lower() == 'nan':
        return None, None
    nums = [float(x) for x in re.findall(r'\d+\.?\d*', str(val))]
    if len(nums) == 1:
        return nums[0], nums[0]
    elif len(nums) >= 2:
        return nums[0], nums[1]
    return None, None

def migrate():
    db = SessionLocal()
    try:
        print("Adding new columns to table...")
        # Add columns if they don't exist
        db.execute(text("ALTER TABLE yarn_and_supplier_database ADD COLUMN IF NOT EXISTS lt_min_days INTEGER;"))
        db.execute(text("ALTER TABLE yarn_and_supplier_database ADD COLUMN IF NOT EXISTS lt_max_days INTEGER;"))
        db.execute(text("ALTER TABLE yarn_and_supplier_database ADD COLUMN IF NOT EXISTS moq_min FLOAT;"))
        db.execute(text("ALTER TABLE yarn_and_supplier_database ADD COLUMN IF NOT EXISTS moq_max FLOAT;"))
        db.commit()

        print("Fetching yarns to migrate...")
        yarns = db.query(YarnSupplier).all()
        updated_lt = 0
        updated_moq = 0
        
        for y in yarns:
            # Parse Lead time
            if y.Manufacture_LT:
                min_lt, max_lt = parse_lt_to_days(y.Manufacture_LT)
                if min_lt is not None:
                    y.lt_min_days = min_lt
                    y.lt_max_days = max_lt
                    updated_lt += 1
                
            # Parse MOQ
            if y.MOQ:
                min_moq, max_moq = parse_moq(y.MOQ)
                if min_moq is not None:
                    y.moq_min = min_moq
                    y.moq_max = max_moq
                    updated_moq += 1
                    
        print(f"Migrated {updated_lt} lead times and {updated_moq} MOQs.")
        db.commit()
        print("Migration complete!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
