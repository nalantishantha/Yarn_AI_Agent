from sqlalchemy.orm import Session
from typing import List

from app.db import models
from app.schemas import schemas

def get_matching_yarns(db: Session, filters: schemas.YarnFilterRequest) -> List[models.YarnSupplier]:
    """
    Applies deterministic hard filters to the yarn database.
    Acts as a dynamic SQL WHERE clause.
    """
    query = db.query(models.YarnSupplier)
    
    if filters.price_max is not None:
        query = query.filter(models.YarnSupplier.Price <= filters.price_max)
    
    if filters.tenacity_min is not None:
        query = query.filter(models.YarnSupplier.Supplier_Tenacity >= filters.tenacity_min)
        
    if filters.elongation_min is not None:
        query = query.filter(models.YarnSupplier.Elongation >= filters.elongation_min)
        
    if filters.count_dtex_min is not None:
        query = query.filter(models.YarnSupplier.Count_dtex >= filters.count_dtex_min)
        
    if filters.count_dtex_max is not None:
        query = query.filter(models.YarnSupplier.Count_dtex <= filters.count_dtex_max)
        
    if filters.shrinkage_max is not None:
        query = query.filter(models.YarnSupplier.Hot_Water_Shrinkage <= filters.shrinkage_max)
        
    if filters.twist_per_metre_min is not None:
        query = query.filter(models.YarnSupplier.TPM >= filters.twist_per_metre_min)
        
    if filters.material_type is not None:
        query = query.filter(models.YarnSupplier.Type.ilike(f"%{filters.material_type}%"))
        
    if filters.supplier is not None:
        query = query.filter(models.YarnSupplier.Supplier.ilike(f"%{filters.supplier}%"))
        
    if filters.twist_per_metre_max is not None:
        query = query.filter(models.YarnSupplier.TPM <= filters.twist_per_metre_max)
        
    if filters.tensile_strength_min is not None:
        query = query.filter(models.YarnSupplier.Tensile_Strength >= filters.tensile_strength_min)
        
    if filters.supplier_tenacity_min is not None:
        query = query.filter(models.YarnSupplier.Supplier_Tenacity >= filters.supplier_tenacity_min)
        
    if filters.supplier_elongation_min is not None:
        query = query.filter(models.YarnSupplier.Supplier_Elongation >= filters.supplier_elongation_min)
        
    if filters.lustre is not None:
        query = query.filter(models.YarnSupplier.Lustre.ilike(f"%{filters.lustre}%"))
        
    if filters.country is not None:
        query = query.filter(models.YarnSupplier.Country.ilike(f"%{filters.country}%"))
        
    if filters.fully_drawn_textured is not None:
        query = query.filter(models.YarnSupplier.Fully_drawn_Textured.ilike(f"%{filters.fully_drawn_textured}%"))
        
    if filters.lead_time_max_days is not None:
        query = query.filter(models.YarnSupplier.lt_max_days <= filters.lead_time_max_days)
        
    if filters.moq_max is not None:
        query = query.filter(models.YarnSupplier.moq_max <= filters.moq_max)
        
    return query.all()
