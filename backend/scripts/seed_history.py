import sys
import os
import random

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from sqlalchemy.orm import Session
from app.db.database import engine, Base
from app.db.models import YarnSupplier, YarnCombination, ArticleRequirement

# Ensure tables exist
Base.metadata.create_all(bind=engine)

def seed_history():
    with Session(engine) as session:
        # Clear existing data
        print("Clearing existing historical records...")
        session.query(YarnCombination).delete()
        session.query(ArticleRequirement).delete()
        session.commit()

        print("Seeding new historical records based on richer archetypes...")
        
        article_counter = 1

        def add_article(article_no, yarns, reqs_list):
            combo = YarnCombination(
                Item="Dummy Item",
                Article_No=article_no,
                Sketch_No=f"SK_{article_counter:03d}"
            )
            for j, y_id in enumerate(yarns):
                setattr(combo, f"Yarn_{j+1}", y_id)
            session.add(combo)

            for j, req_data in enumerate(reqs_list):
                req = ArticleRequirement(
                    Article_No=article_no,
                    Yarn_Slot=f"Yarn_{j+1}",
                )
                for k, v in req_data.items():
                    setattr(req, k, v)
                session.add(req)

        # 1. Budget Fast-Fashion (8 Articles)
        for i in range(8):
            article_no = f"ART_SIM_{article_counter:03d}"
            yarns = [1002166, random.choice([1002186, 1002177])]
            reqs = [
                {
                    "material_type": "Cotton", 
                    "price_max": round(random.uniform(6.0, 9.9), 2),
                    "lead_time_max_days": random.choice([28, 35, 42]),
                    "moq_max": round(random.uniform(30.0, 50.0), 2),
                    "count_dtex_max": round(random.uniform(100.0, 150.0), 2),
                    "tenacity_min": round(random.uniform(10.0, 20.0), 2)
                },
                {
                    "material_type": "Polyester", 
                    "price_max": round(random.uniform(5.0, 10.0), 2), 
                    "lead_time_max_days": random.choice([21, 28, 35]),
                    "moq_max": round(random.uniform(30.0, 50.0), 2),
                    "count_dtex_max": round(random.uniform(80.0, 120.0), 2),
                    "tenacity_min": round(random.uniform(15.0, 25.0), 2)
                }
            ]
            add_article(article_no, yarns, reqs)
            article_counter += 1

        # 2. Premium Sportswear (7 Articles)
        for i in range(7):
            article_no = f"ART_SIM_{article_counter:03d}"
            yarns = [random.choice([1002167, 1000014]), 1002189]
            reqs = [
                {
                    "material_type": "Elastane", 
                    "price_max": round(random.uniform(15.0, 25.0), 2),
                    "lead_time_max_days": random.choice([14, 21]), 
                    "tenacity_min": round(random.uniform(15.0, 25.0), 2),
                    "elongation_min": round(random.uniform(15.0, 25.0), 2),
                    "moq_max": round(random.uniform(20.0, 40.0), 2),
                    "count_dtex_max": round(random.uniform(30.0, 50.0), 2)
                },
                {
                    "material_type": "Nylon66", 
                    "price_max": round(random.uniform(20.0, 30.0), 2),
                    "lead_time_max_days": random.choice([14, 21, 28]), 
                    "tenacity_min": round(random.uniform(20.0, 30.0), 2),
                    "elongation_min": round(random.uniform(10.0, 20.0), 2),
                    "moq_max": round(random.uniform(20.0, 40.0), 2),
                    "count_dtex_max": round(random.uniform(40.0, 60.0), 2)
                }
            ]
            add_article(article_no, yarns, reqs)
            article_counter += 1

        # 3. Heavy Duty / High Tenacity (5 Articles)
        for i in range(5):
            article_no = f"ART_SIM_{article_counter:03d}"
            yarns = [1002181, 1002170]
            reqs = [
                {
                    "material_type": "Nylon66", 
                    "tenacity_min": round(random.uniform(40.0, 48.0), 2),
                    "price_max": round(random.uniform(20.0, 35.0), 2),
                    "lead_time_max_days": random.choice([28, 35]),
                    "elongation_min": round(random.uniform(5.0, 15.0), 2),
                    "shrinkage_max": round(random.uniform(3.0, 8.0), 2)
                },
                {
                    "material_type": "Viscose", 
                    "tenacity_min": round(random.uniform(40.0, 48.0), 2),
                    "price_max": round(random.uniform(20.0, 35.0), 2),
                    "lead_time_max_days": random.choice([28, 35]),
                    "elongation_min": round(random.uniform(5.0, 15.0), 2),
                    "shrinkage_max": round(random.uniform(3.0, 8.0), 2)
                }
            ]
            add_article(article_no, yarns, reqs)
            article_counter += 1

        # 4. General Blends (5 Articles)
        valid_yarns = session.query(YarnSupplier.Material_No, YarnSupplier.Type, YarnSupplier.Price).all()
        valid_yarn_ids = [y.Material_No for y in valid_yarns]
        
        for i in range(5):
            article_no = f"ART_SIM_{article_counter:03d}"
            num_yarns = random.randint(2, 4)
            selected_yarns = random.sample(valid_yarn_ids, num_yarns)
            reqs = []
            for y_id in selected_yarns:
                actual_yarn = next((y for y in valid_yarns if y.Material_No == y_id), None)
                req_data = {}
                if random.random() > 0.1 and actual_yarn.Type:
                    req_data["material_type"] = actual_yarn.Type
                if random.random() > 0.2 and actual_yarn.Price is not None:
                    req_data["price_max"] = round(actual_yarn.Price * random.uniform(1.1, 1.5), 2)
                if random.random() > 0.3:
                    req_data["lead_time_max_days"] = random.choice([21, 28, 35, 42])
                if random.random() > 0.4:
                    req_data["tenacity_min"] = round(random.uniform(15.0, 35.0), 2)
                if random.random() > 0.5:
                    req_data["elongation_min"] = round(random.uniform(10.0, 30.0), 2)
                if random.random() > 0.6:
                    req_data["moq_max"] = round(random.uniform(20.0, 60.0), 2)
                if random.random() > 0.7:
                    req_data["count_dtex_max"] = round(random.uniform(30.0, 150.0), 2)
                
                reqs.append(req_data)
            add_article(article_no, selected_yarns, reqs)
            article_counter += 1

        session.commit()
        print(f"Successfully seeded {article_counter - 1} dummy Articles (ArticleRequirements and YarnCombinations) with expanded attributes.")

if __name__ == "__main__":
    seed_history()
