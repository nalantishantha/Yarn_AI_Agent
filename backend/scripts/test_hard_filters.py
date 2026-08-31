import sys
import os

# Add the backend directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.services.filtering import get_matching_yarns
from app.schemas.schemas import YarnFilterRequest

def test_filters():
    db = SessionLocal()
    try:
        print("--- Testing Hard Filters ---")
        
        # Test 1: Price Max
        print("\nTest 1: price_max = 10.0")
        req1 = YarnFilterRequest(price_max=10.0)
        results1 = get_matching_yarns(db, req1)
        print(f"Found {len(results1)} yarns.")
        for y in results1[:3]:
            print(f"  - Material_No: {y.Material_No}, Price: {y.Price}")
            assert y.Price <= 10.0, "Filter Failed!"
            
        # Test 2: Material Type + Price Max
        print("\nTest 2: material_type = 'elastane', price_max = 12.0")
        req2 = YarnFilterRequest(material_type='Elastane', price_max=12.0)
        results2 = get_matching_yarns(db, req2)
        print(f"Found {len(results2)} yarns.")
        for y in results2[:3]:
            print(f"  - Material_No: {y.Material_No}, Price: {y.Price}, Type: {y.Type}")
            assert y.Price <= 12.0 and y.Type == 'Elastane', "Filter Failed!"
            
        # Test 3: Multiple numerical constraints
        print("\nTest 3: count_dtex_max = 100, tenacity_min = 35.0")
        req3 = YarnFilterRequest(count_dtex_max=100.0, tenacity_min=35.0)
        results3 = get_matching_yarns(db, req3)
        print(f"Found {len(results3)} yarns.")
        for y in results3[:3]:
            print(f"  - Material_No: {y.Material_No}, Count_dtex: {y.Count_dtex}, Tenacity: {y.Supplier_Tenacity}")
            # Safely check because some values might be None in DB
            if y.Count_dtex is not None:
                assert y.Count_dtex <= 100.0, "Filter Failed!"
            if y.Supplier_Tenacity is not None:
                assert y.Supplier_Tenacity >= 35.0, "Filter Failed!"
                
        print("\nAll tests passed successfully!")
        
        # Test 4: New parsed columns (MOQ, Lead Time)
        print("\nTest 4: moq_max = 25.0, lead_time_max_days = 28")
        req4 = YarnFilterRequest(moq_max=25.0, lead_time_max_days=28)
        results4 = get_matching_yarns(db, req4)
        print(f"Found {len(results4)} yarns.")
        for y in results4[:3]:
            print(f"  - Material_No: {y.Material_No}, MOQ string: {y.MOQ}, Max MOQ: {y.moq_max}, Max Lead Time: {y.lt_max_days}")
            if y.moq_max is not None:
                assert y.moq_max <= 25.0, "Filter Failed!"
            if y.lt_max_days is not None:
                assert y.lt_max_days <= 28, "Filter Failed!"
    finally:
        db.close()

if __name__ == "__main__":
    test_filters()
