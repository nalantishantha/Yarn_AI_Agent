from sqlalchemy.orm import Session
from typing import List, Dict
from app.db.models import YarnSupplier

LOWER_IS_BETTER = ['Price', 'lt_max_days', 'moq_max', 'Hot_Water_Shrinkage']
HIGHER_IS_BETTER = [
    'Brecking_Tenacity', 'Elongation', 'Count_dtex', 'Tensile_Strength',
    'Supplier_Tenacity', 'Supplier_Elongation', 'TPM', 'PPM'
]

def score_and_sort_yarns(db: Session, yarn_ids: List[int], weights: Dict[str, float]) -> List[dict]:
    """
    Applies the Weighted Scoring Formula to a list of candidate yarns.
    Returns a sorted list of dictionaries containing the yarn and its final score.
    """
    if not yarn_ids or not weights:
        # If no yarns or no weights, just return the yarns in original order
        yarns = db.query(YarnSupplier).filter(YarnSupplier.Material_No.in_(yarn_ids)).all()
        return [{"yarn": y, "score": 0.0} for y in yarns]

    # Pre-process 'Quality' pseudo-attribute
    # The user defined Quality as a combination of Tenacity and Elongation
    if 'Quality' in weights:
        q_weight = weights.pop('Quality')
        weights['Brecking_Tenacity'] = weights.get('Brecking_Tenacity', 0.0) + (q_weight / 2.0)
        weights['Elongation'] = weights.get('Elongation', 0.0) + (q_weight / 2.0)

    # Validate weight keys
    valid_keys = set(LOWER_IS_BETTER) | set(HIGHER_IS_BETTER)
    unrecognized = set(weights.keys()) - valid_keys
    if unrecognized:
        raise ValueError(f"Unrecognized weight keys: {sorted(list(unrecognized))}. Valid keys are: {sorted(list(valid_keys.union({'Quality'})))}")

    # Normalize weights so they sum to 1.0 (just in case LLM math was slightly off)
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}

    yarns = db.query(YarnSupplier).filter(YarnSupplier.Material_No.in_(yarn_ids)).all()
    
    # Identify valid attributes that actually exist on the model
    valid_attrs = []
    for k in weights.keys():
        if k in LOWER_IS_BETTER or k in HIGHER_IS_BETTER:
            valid_attrs.append(k)
            
    # Calculate min/max for each valid attribute to establish the normalization range
    ranges = {}
    for attr in valid_attrs:
        values = [getattr(y, attr) for y in yarns if getattr(y, attr) is not None]
        if not values:
            continue
        ranges[attr] = {'min': min(values), 'max': max(values)}

    # Score each yarn
    scored_yarns = []
    for yarn in yarns:
        final_score = 0.0
        
        for attr in valid_attrs:
            if attr not in ranges:
                continue
                
            val = getattr(yarn, attr)
            if val is None:
                # Missing data gets 0 score for this attribute
                continue
                
            min_val = ranges[attr]['min']
            max_val = ranges[attr]['max']
            weight = weights[attr]
            
            # Normalization
            if max_val == min_val:
                # If all candidates have the exact same value for this attribute, 
                # they all get full score (1.0) for this component because there's no differentiation
                norm_val = 1.0
            else:
                if attr in LOWER_IS_BETTER:
                    norm_val = (max_val - val) / (max_val - min_val)
                else:
                    norm_val = (val - min_val) / (max_val - min_val)
                    
            final_score += norm_val * weight
            
        scored_yarns.append({
            "yarn": yarn,
            "score": round(final_score, 4)
        })

    # Sort descending by score
    scored_yarns.sort(key=lambda x: x['score'], reverse=True)
    return scored_yarns
