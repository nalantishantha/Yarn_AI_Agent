from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from app.db.database import SessionLocal
from app.services.filtering import get_matching_yarns
from app.schemas.schemas import YarnFilterRequest
from app.db import crud
from app.schemas import schemas
from app.services.scoring import score_and_sort_yarns
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
            return "No matching yarns found for these criteria."
            
        formatted = []
        for y in results[:10]:  # Limit to 10 to save LLM context window
            formatted.append(
                f"Material_No: {y.Material_No}, Type: {y.Type}, Price: ${y.Price}, Lead Time: {y.lt_max_days} days, Country: {y.Country}"
            )
        return "\n".join(formatted)
    finally:
        db.close()

@tool
def score_yarns_tool(yarn_ids: List[int], weights: Dict[str, float]):
    """
    Applies the Weighted Scoring Formula to a list of candidate yarns to rank them based on user priorities.
    Use this tool AFTER calling filter_yarns_tool to sort the returned yarns according to what the user values most.
    
    Args:
        yarn_ids: A list of Material Numbers (IDs) returned from the previous filtering step.
        weights: A dictionary where keys are the attributes to prioritize (e.g. 'Price', 'lt_max_days', 'Quality', 'Brecking_Tenacity')
                 and values are decimals between 0.0 and 1.0 representing the percentage weight (e.g. 0.5 for 50%).
                 The sum of all values should equal 1.0.
    """
    db = SessionLocal()
    try:
        results = score_and_sort_yarns(db, yarn_ids, weights)
        
        if not results:
            return "No yarns could be scored."
            
        formatted = []
        for i, item in enumerate(results[:10], 1):
            y = item["yarn"]
            score = item["score"]
            formatted.append(
                f"{i}. [Score: {score}] Material_No: {y.Material_No}, Type: {y.Type}, Price: ${y.Price}, Lead Time: {y.lt_max_days} days, Country: {y.Country}"
            )
        return "\n".join(formatted)
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
        action: "hard_restrict" (for excludes/blacklists) or "boost" (for prefers/discounts)
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
    Use this as STEP 3 to see if there are any restrictions or score boosts you need to apply to the final results.
    
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

# List of tools to be bound to the agent
AGENT_TOOLS = [filter_yarns_tool, score_yarns_tool, add_sourcing_constraint_tool, get_active_policies_tool]
