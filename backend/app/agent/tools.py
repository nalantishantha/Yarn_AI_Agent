import json
import uuid
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from app.db.database import SessionLocal
from app.services.filtering import get_matching_yarns
from app.schemas.schemas import YarnFilterRequest
from app.db import crud, models
from app.schemas import schemas
from app.services.scoring import score_and_sort_yarns
from app.services.policy_engine import apply_policies

@tool
def filter_yarns_tool(
    price_max: Optional[float] = None,
    tenacity_min: Optional[float] = None,
    elongation_min: Optional[float] = None,
    count_dtex_min: Optional[float] = None,
    count_dtex_max: Optional[float] = None,
    shrinkage_max: Optional[float] = None,
    twist_per_metre_min: Optional[float] = None,
    twist_per_metre_max: Optional[float] = None,
    material_type: Optional[str] = None,
    supplier: Optional[str] = None,
    tensile_strength_min: Optional[float] = None,
    breaking_tenacity_min: Optional[float] = None,
    supplier_tenacity_min: Optional[float] = None,
    supplier_elongation_min: Optional[float] = None,
    lustre: Optional[str] = None,
    country: Optional[str] = None,
    fully_drawn_textured: Optional[str] = None,
    lead_time_max_days: Optional[int] = None,
    moq_max: Optional[float] = None
):
    """
    Finds yarns matching technical and business requirements from the database.
    Use this tool whenever the user asks to find, search, or filter yarns.
    Returns a structured list of matching yarns with their Material_No (yarn ID) values.
    Use the returned Material_No values directly as yarn_ids in the next scoring step.

    Args:
        price_max: Maximum acceptable price in dollars (e.g. "cheaper than 10 dollars").
        tenacity_min: Minimum acceptable tenacity.
        elongation_min: Minimum acceptable elongation.
        count_dtex_min: Minimum count dtex (thickness).
        count_dtex_max: Maximum count dtex (thickness).
        shrinkage_max: Maximum acceptable shrinkage percentage.
        twist_per_metre_min: Minimum twist per metre (TPM).
        twist_per_metre_max: Maximum twist per metre (TPM).
        material_type: The fiber composition or type of yarn (e.g. "elastane", "cotton", "polyester").
        supplier: The name of the supplier/vendor.
        tensile_strength_min: Minimum tensile strength.
        breaking_tenacity_min: Minimum breaking tenacity (cN/tex).
        supplier_tenacity_min: Minimum supplier tenacity.
        supplier_elongation_min: Minimum supplier elongation.
        lustre: The visual finish/shine (e.g. "bright", "semi-dull").
        country: Country of origin.
        fully_drawn_textured: Whether it is fully drawn textured (e.g. "FDY", "DTY").
        lead_time_max_days: Maximum acceptable lead time or delivery time in days (e.g. "within 4 weeks" = 28).
        moq_max: Maximum Minimum Order Quantity (MOQ) the user is willing to accept.
    """
    req = YarnFilterRequest(
        price_max=price_max,
        tenacity_min=tenacity_min,
        elongation_min=elongation_min,
        count_dtex_min=count_dtex_min,
        count_dtex_max=count_dtex_max,
        shrinkage_max=shrinkage_max,
        twist_per_metre_min=twist_per_metre_min,
        twist_per_metre_max=twist_per_metre_max,
        material_type=material_type,
        supplier=supplier,
        tensile_strength_min=tensile_strength_min,
        breaking_tenacity_min=breaking_tenacity_min,
        supplier_tenacity_min=supplier_tenacity_min,
        supplier_elongation_min=supplier_elongation_min,
        lustre=lustre,
        country=country,
        fully_drawn_textured=fully_drawn_textured,
        lead_time_max_days=lead_time_max_days,
        moq_max=moq_max
    )

    db = SessionLocal()
    try:
        results = get_matching_yarns(db, req)

        if not results:
            return json.dumps({"count": 0, "candidates": []})
            
        all_yarn_ids = [y.Material_No for y in results]
        search_id = str(uuid.uuid4())
        crud.create_search_session(db, search_id, all_yarn_ids)

        candidates = []
        for y in results[:10]:  # Limit to 10 to save LLM context window
            candidates.append({
                "yarn_id": y.Material_No,
                "type": y.Type,
                "supplier": y.Supplier,
                "price": y.Price,
                "lead_time_days": y.lt_max_days,
                "moq": y.moq_max,
                "quality_grade": y.Brecking_Tenacity,
                "country": y.Country,
                "count_dtex": y.Count_dtex,
                "lustre": y.Lustre,
            })

        return json.dumps({"count": len(all_yarn_ids), "search_id": search_id, "candidates": candidates})
    finally:
        db.close()


@tool
def score_yarns_tool(search_id: str, weights: Dict[str, float]):
    """
    Applies the Weighted Scoring Formula to a list of candidate yarns to rank them based on user priorities.
    Use this tool AFTER calling filter_yarns_tool to sort the returned yarns according to what the user values most.
    Returns ranked yarns and the search_id to pass to apply_policies_tool.

    Args:
        search_id: The search_id returned from filter_yarns_tool.
        weights: A dictionary where keys are the attributes to prioritize and values are decimals
                 between 0.0 and 1.0 representing the percentage weight. The sum of all values should equal 1.0.
                 Valid keys MUST be chosen from this exact list:
                 ['Price', 'lt_max_days', 'Quality', 'moq_max', 'Hot_Water_Shrinkage', 'Tensile_Strength', 'Count_dtex']
    """
    db = SessionLocal()
    try:
        session = crud.get_search_session(db, search_id)
        if not session:
            return "Error: Invalid or expired search_id."
            
        yarn_ids = json.loads(session.yarn_ids)
        
        try:
            results = score_and_sort_yarns(db, yarn_ids, weights)
        except ValueError as e:
            return str(e)

        if not results:
            return json.dumps({"search_id": search_id, "ranked": []})
            
        # Save scores to DB
        scores_dict = {str(item["yarn"].Material_No): item["score"] for item in results}
        crud.update_search_session_scores(db, search_id, scores_dict)

        ranked = []
        for item in results[:10]:
            y = item["yarn"]
            ranked.append({
                "rank": len(ranked) + 1,
                "yarn_id": y.Material_No,
                "score": item["score"],
                "type": y.Type,
                "supplier": y.Supplier,
                "price": y.Price,
                "lead_time_days": y.lt_max_days,
                "country": y.Country,
            })

        return json.dumps({"search_id": search_id, "ranked": ranked})
    finally:
        db.close()


@tool
def add_sourcing_constraint_tool(
    constraint_type: str,
    target_value: str,
    scope: str,
    action: str,
    weight: Optional[float] = None,
    reason: Optional[str] = None
):
    """
    Creates a new long-term business policy (sourcing constraint) in the database.
    Use this when the user explicitly mentions a long-term rule (e.g. "blacklist supplier X for all orders", "we have a discount from supplier Y").

    Args:
        constraint_type: Type of constraint (e.g. "exclude_supplier", "prefer_supplier", "exclude_country", "prefer_country")
        target_value: The name of the supplier or country (e.g. "China", "Supplier X")
        scope: The scope of the policy (use "all_orders" by default unless specified)
        action: "hard_restrict" (for excludes/blacklists or strict inclusions) or "boost" (for soft preferences/discounts). NOTE: "prefer_supplier" + "hard_restrict" means MUST USE ONLY this supplier.
        weight: If action is "boost", a decimal weight to add to the score (e.g. 0.2). Leave null for hard_restrict.
        reason: Optional text explaining why this policy exists.
    """
    db = SessionLocal()
    try:
        req = schemas.SourcingConstraintCreate(
            constraint_type=constraint_type,
            target_value=target_value,
            scope=scope,
            action=action,
            weight=weight,
            reason=reason
        )
        crud.create_sourcing_constraint(db, req)
        return "Successfully proposed the new policy. It is pending user confirmation."
    finally:
        db.close()


@tool
def get_active_policies_tool(scope: str = "all_orders"):
    """
    Fetches the currently active long-term business policies from the database.
    Use this only when the user explicitly asks to VIEW or LIST the current policies.
    Do NOT use this as part of the yarn selection pipeline — apply_policies_tool handles
    policy fetching and application internally.

    Args:
        scope: The scope of the policies to fetch. Usually "all_orders".
    """
    db = SessionLocal()
    try:
        policies = crud.get_active_sourcing_constraints(db, scope=scope)
        if not policies:
            return "No active policies found."

        formatted = []
        for p in policies:
            formatted.append(f"- Type: {p.constraint_type}, Target: {p.target_value}, Action: {p.action}, Weight: {p.weight}")
        return "\n".join(formatted)
    finally:
        db.close()


@tool
def apply_policies_tool(
    search_id: str,
    one_off_constraints: Optional[List[Dict[str, Any]]] = None,
):
    """
    Applies active sourcing policies (from the database) plus any one-off,
    query-specific constraints the user stated, to a scored list of candidate yarns.
    Removes yarns that violate a hard_restrict policy, adds boost weight to yarns
    matching a boost policy, and re-sorts. ALWAYS call this after filtering (and
    scoring, if it happened) and before presenting results — never compute policy
    effects yourself.

    This tool fetches active DB policies internally — do NOT call get_active_policies_tool
    before calling this tool.

    Args:
        search_id: The search_id returned from filter_yarns_tool or score_yarns_tool.
        one_off_constraints: Structured constraints stated for THIS QUERY ONLY, not
            persisted to the DB — same shape as a DB policy:
            [{"constraint_type": "...", "target_value": "...",
              "action": "boost" | "hard_restrict", "weight": float | None}]
    """
    db = SessionLocal()
    try:
        session = crud.get_search_session(db, search_id)
        if not session:
            return "Error: Invalid or expired search_id."
            
        yarn_ids = json.loads(session.yarn_ids)
        scores = json.loads(session.scores) if session.scores else {}
        
        db_policies = crud.get_active_sourcing_constraints(db, scope="all_orders")

        yarns = db.query(models.YarnSupplier).filter(models.YarnSupplier.Material_No.in_(yarn_ids)).all()
        scored_yarns = []
        for yarn in yarns:
            # Cast string keys to int — JSON keys are always strings,
            # so the LLM will pass {"101": 0.85} not {101: 0.85}
            score_key = str(yarn.Material_No)
            scored_yarns.append({"yarn": yarn, "score": scores.get(score_key, 0.0)})

        result = apply_policies(scored_yarns, db_policies, one_off_constraints)

        # Format structured output for LLM
        output = {
            "all_excluded_by_policy": result["all_excluded_by_policy"],
            "excluded": [
                {"yarn_id": ex["yarn_id"], "reason": ex["reason"]}
                for ex in result["excluded"]
            ],
            "applied_boosts": [
                {"yarn_id": b["yarn_id"], "boost": b["boost"], "reason": b["reason"]}
                for b in result["applied_boosts"]
            ],
            "final_ranked": []
        }

        for i, item in enumerate(result["final_ranked"][:10], 1):
            y = item["yarn"]
            output["final_ranked"].append({
                "rank": i,
                "yarn_id": y.Material_No,
                "final_score": item["score"],
                "type": y.Type,
                "supplier": y.Supplier,
                "price": y.Price,
                "lead_time_days": y.lt_max_days,
                "country": y.Country,
            })

        return json.dumps(output)
    finally:
        db.close()


# List of tools to be bound to the agent.
# get_active_policies_tool is intentionally excluded from this list:
# - apply_policies_tool fetches DB policies internally as part of the selection pipeline.
# - get_active_policies_tool is kept as a function but NOT exposed to the agent to avoid
#   confusion about which tool to call during the sequential selection flow.
AGENT_TOOLS = [filter_yarns_tool, score_yarns_tool, add_sourcing_constraint_tool, apply_policies_tool]
