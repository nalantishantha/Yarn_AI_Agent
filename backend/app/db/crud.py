from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.db import models
from app.schemas import schemas


def get_active_sourcing_constraints(db: Session, scope: Optional[str] = None) -> List[models.SourcingConstraint]:
    """
    Fetches all active business policies.
    If a specific scope (like an article category) is provided, it returns policies 
    that apply to that scope AND policies that apply globally to all orders.
    """
    query = db.query(models.SourcingConstraint).filter(models.SourcingConstraint.active == True)
    if scope:
        query = query.filter(or_(
            models.SourcingConstraint.scope == scope,
            models.SourcingConstraint.scope == "all_orders"
        ))
    return query.all()

def create_sourcing_constraint(db: Session, constraint: schemas.SourcingConstraintCreate) -> models.SourcingConstraint:
    """
    Saves a new business policy (like a supplier restriction or boost) into the database.
    """
    db_constraint = models.SourcingConstraint(**constraint.model_dump())
    db.add(db_constraint)
    db.commit()
    db.refresh(db_constraint)
    return db_constraint


def get_yarn_suppliers(db: Session, skip: int = 0, limit: int = 100) -> List[models.YarnSupplier]:
    """
    Retrieves a paginated list of all available yarns and their suppliers.
    """
    return db.query(models.YarnSupplier).offset(skip).limit(limit).all()



def get_design_articles(db: Session, skip: int = 0, limit: int = 100) -> List[models.DesignDatabase]:
    """
    Retrieves a paginated list of design articles.
    """
    return db.query(models.DesignDatabase).offset(skip).limit(limit).all()
