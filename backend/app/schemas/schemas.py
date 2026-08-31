from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SourcingConstraintBase(BaseModel):
    """
    Base properties for a sourcing policy. 
    Defines who the policy targets, what action it takes (boost or restrict), 
    and its valid timeframe.
    """
    constraint_type: str
    target_value: str
    scope: str
    action: str
    weight: Optional[float] = None
    priority: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    reason: Optional[str] = None
    set_by: Optional[str] = None
    active: bool = True

class SourcingConstraintCreate(SourcingConstraintBase):
    """
    Schema used when creating a new policy. 
    Inherits all base fields without requiring an ID, as the database generates it.
    """
    pass

class SourcingConstraintUpdate(SourcingConstraintBase):
    """
    Schema used when updating an existing policy.
    """
    pass

class SourcingConstraintResponse(SourcingConstraintBase):
    """
    Schema used when reading policies from the database. 
    Includes the database-generated ID.
    """
    id: int

    class Config:
        from_attributes = True


class YarnSupplierResponse(BaseModel):
    """
    Read-only schema for fetching yarn supplier details.
    Used by the AI agent to display available yarn matches to the user.
    """
    Material_No: int
    Descripion: Optional[str] = None
    Type: Optional[str] = None
    Supplier: Optional[str] = None
    Price: Optional[float] = None
    Manufacture_LT: Optional[str] = None
    MOQ: Optional[str] = None
    # We can add more fields if needed for the AI Agent later

    class Config:
        from_attributes = True

class DesignDatabaseResponse(BaseModel):
    """
    Read-only schema for fetching design article details.
    Used by the AI agent to understand the current article requirements.
    """
    id: int
    Article_Number: Optional[str] = None
    Description_Technologist: Optional[str] = None
    Customer: Optional[str] = None
    Yarn_Code_Technologist: Optional[int] = None

    class Config:
        from_attributes = True

class YarnFilterRequest(BaseModel):
    """
    Structured request for deterministic hard filters.
    All properties are optional; the filter engine only applies the ones provided.
    """
    price_max: Optional[float] = None
    tenacity_min: Optional[float] = None
    elongation_min: Optional[float] = None
    count_dtex_min: Optional[float] = None
    count_dtex_max: Optional[float] = None
    shrinkage_max: Optional[float] = None
    twist_per_metre_min: Optional[float] = None
    material_type: Optional[str] = None
    supplier: Optional[str] = None
