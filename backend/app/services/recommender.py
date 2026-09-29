import math
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import ArticleRequirement, YarnCombination

NUMERICAL_KEYS = [
    'price_max', 'tenacity_min', 'elongation_min', 'count_dtex_min', 
    'count_dtex_max', 'shrinkage_max', 'twist_per_metre_min', 'twist_per_metre_max', 
    'tensile_strength_min', 'breaking_tenacity_min', 'supplier_tenacity_min', 
    'supplier_elongation_min', 'lead_time_max_days', 'moq_max'
]
CATEGORICAL_KEYS = ['material_type', 'supplier', 'lustre', 'country', 'fully_drawn_textured']

def calculate_historical_boosts(db: Session, current_req: Dict[str, Any], candidates: List[int]) -> Dict[str, float]:
    """
    Calculates historical boosts for candidate yarns based on similarity 
    between current_req and all historical ArticleRequirement records.
    Returns a dict mapping yarn_id (as string) to a normalized boost score (0.0 to 1.0).
    """
    if not current_req:
        return {}

    all_past_reqs = db.query(ArticleRequirement).all()
    if not all_past_reqs:
        return {}

    # Calculate min/max for normalization
    ranges = {}
    for key in NUMERICAL_KEYS:
        vals = [getattr(r, key) for r in all_past_reqs if getattr(r, key) is not None]
        if key in current_req and current_req[key] is not None:
            vals.append(current_req[key])
        if vals:
            ranges[key] = {'min': min(vals), 'max': max(vals)}
        else:
            ranges[key] = {'min': 0, 'max': 0}

    # Find similarity for each past requirement
    similarities = []
    for past in all_past_reqs:
        vec1 = []
        vec2 = []

        for key in NUMERICAL_KEYS:
            if key in current_req and current_req[key] is not None:
                v1 = current_req[key]
                v2 = getattr(past, key)
                min_v = ranges[key]['min']
                max_v = ranges[key]['max']
                
                # Normalize to 0.1 - 1.0 to avoid zero magnitude vectors causing issues
                range_span = max_v - min_v
                norm1 = (v1 - min_v) / range_span if range_span > 0 else 1.0
                # Scale from 0-1 to 0.1-1.0
                norm1 = 0.1 + (norm1 * 0.9)
                
                if v2 is not None:
                    norm2 = (v2 - min_v) / range_span if range_span > 0 else 1.0
                    norm2 = 0.1 + (norm2 * 0.9)
                    vec1.append(norm1)
                    vec2.append(norm2)
                else:
                    vec1.append(norm1)
                    vec2.append(0.0)

        for key in CATEGORICAL_KEYS:
            if key in current_req and current_req[key] is not None:
                v1 = current_req[key]
                v2 = getattr(past, key)
                if v2 is not None:
                    if str(v1).lower() == str(v2).lower():
                        vec1.append(1.0)
                        vec2.append(1.0)
                    else:
                        vec1.append(1.0)
                        vec2.append(0.0)
                else:
                    vec1.append(1.0)
                    vec2.append(0.0)

        if not vec1:
            continue

        dot_product = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
        mag1 = math.sqrt(sum(v**2 for v in vec1))
        mag2 = math.sqrt(sum(v**2 for v in vec2))

        if mag1 > 0 and mag2 > 0:
            sim = dot_product / (mag1 * mag2)
            similarities.append((past, sim))

    # Aggregate scores for yarns
    # Only consider high similarity matches (e.g. > 0.6)
    yarn_strengths = {}
    for past_req, sim in similarities:
        if sim > 0.6:
            # Find the YarnCombination where this article is used
            combo = db.query(YarnCombination).filter(YarnCombination.Article_No == past_req.Article_No).first()
            if combo:
                # Get the yarn id from the specific slot
                yarn_id = getattr(combo, past_req.Yarn_Slot, None)
                if yarn_id and yarn_id in candidates:
                    yarn_id_str = str(yarn_id)
                    yarn_strengths[yarn_id_str] = yarn_strengths.get(yarn_id_str, 0.0) + sim

    # Normalize yarn_strengths from 0 to 1
    if not yarn_strengths:
        return {}

    max_strength = max(yarn_strengths.values())
    min_strength = min(yarn_strengths.values())
    
    normalized_boosts = {}
    for y_id, strength in yarn_strengths.items():
        if max_strength > min_strength:
            norm_val = (strength - min_strength) / (max_strength - min_strength)
        else:
            norm_val = 1.0 # If all have same strength, give them full boost
        normalized_boosts[y_id] = round(norm_val, 4)

    return normalized_boosts
