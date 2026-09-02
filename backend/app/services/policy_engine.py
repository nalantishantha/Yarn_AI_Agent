from typing import List, Dict, Any
from app.db.models import SourcingConstraint

def apply_policies(scored_yarns: List[Dict[str, Any]], db_policies: List[SourcingConstraint], one_off_policies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Applies both long-term (DB) and short-term (one-off) situational policies to a list of scored yarns.
    
    Args:
        scored_yarns: List of dicts, e.g., [{"yarn": <YarnSupplier>, "score": 0.85}, ...]
        db_policies: List of active SourcingConstraint objects from the database.
        one_off_policies: List of dicts representing prompt-based policies, e.g., 
                          [{"constraint_type": "exclude_supplier", "target_value": "China", "action": "hard_restrict"}]
                          
    Returns:
        A dictionary containing:
        - final_ranked: The new list of scored yarns, filtered by hard_restricts and re-ranked by boosts.
        - excluded: List of dicts recording yarns excluded and why.
        - applied_boosts: List of dicts recording yarns boosted and why.
        - all_excluded_by_policy: True if candidates existed but all were eliminated by hard_restricts.
    """
    if one_off_policies is None:
        one_off_policies = []
        
    # Unify policies into a common dictionary format for easy processing
    all_policies = []
    
    for p in db_policies:
        all_policies.append({
            "constraint_type": p.constraint_type,
            "target_value": p.target_value.lower(),
            "action": p.action,
            "weight": p.weight or 0.0
        })
        
    for p in one_off_policies:
        all_policies.append({
            "constraint_type": p.get("constraint_type", ""),
            "target_value": p.get("target_value", "").lower(),
            "action": p.get("action", ""),
            "weight": p.get("weight", 0.0)
        })
        
    # Split policies by action
    hard_restricts = [p for p in all_policies if p["action"] == "hard_restrict"]
    boosts = [p for p in all_policies if p["action"] == "boost"]
    
    final_yarns = []
    excluded = []
    applied_boosts = []
    
    for item in scored_yarns:
        yarn = item["yarn"]
        current_score = item["score"]
        is_restricted = False
        
        # 1. Apply Hard Restricts (Exclude)
        for hr in hard_restricts:
            c_type = hr["constraint_type"]
            target = hr["target_value"]
            reason_str = f"excluded by policy: {c_type}={target}"
            
            if c_type == "exclude_supplier" and yarn.Supplier and target in yarn.Supplier.lower():
                is_restricted = True
                excluded.append({"yarn_id": yarn.Material_No, "reason": reason_str})
                break
            if c_type == "exclude_country" and yarn.Country and target in yarn.Country.lower():
                is_restricted = True
                excluded.append({"yarn_id": yarn.Material_No, "reason": reason_str})
                break
            if c_type == "prefer_supplier" and yarn.Supplier and target not in yarn.Supplier.lower():
                # If there's a hard restrict to ONLY use a specific supplier
                is_restricted = True
                excluded.append({"yarn_id": yarn.Material_No, "reason": reason_str})
                break
                
        if is_restricted:
            continue
            
        # 2. Apply Boosts
        for boost in boosts:
            c_type = boost["constraint_type"]
            target = boost["target_value"]
            weight = float(boost["weight"])
            reason_str = f"{c_type}={target}"
            
            if c_type == "prefer_supplier" and yarn.Supplier and target in yarn.Supplier.lower():
                current_score += weight
                applied_boosts.append({"yarn_id": yarn.Material_No, "boost": weight, "reason": reason_str})
            if c_type == "prefer_country" and yarn.Country and target in yarn.Country.lower():
                current_score += weight
                applied_boosts.append({"yarn_id": yarn.Material_No, "boost": weight, "reason": reason_str})
                
        final_yarns.append({
            "yarn": yarn,
            "score": round(current_score, 4)
        })
        
    # 3. Re-sort based on updated scores
    final_yarns.sort(key=lambda x: x['score'], reverse=True)
    
    all_excluded_by_policy = bool(scored_yarns) and not final_yarns
    
    return {
        "final_ranked": final_yarns,
        "excluded": excluded,
        "applied_boosts": applied_boosts,
        "all_excluded_by_policy": all_excluded_by_policy
    }
