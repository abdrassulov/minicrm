from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import random

# Database setup
DATABASE_URL = "sqlite:///./crm.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class Operator(Base):
    __tablename__ = "operators"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    max_load = Column(Integer, default=10)
    
    source_configs = relationship("SourceOperatorConfig", back_populates="operator")
    contacts = relationship("Contact", back_populates="operator")

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
    contacts = relationship("Contact", back_populates="lead")

class Source(Base):
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    operator_configs = relationship("SourceOperatorConfig", back_populates="source")
    contacts = relationship("Contact", back_populates="source")

class SourceOperatorConfig(Base):
    __tablename__ = "source_operator_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    weight = Column(Integer, default=10)
    
    source = relationship("Source", back_populates="operator_configs")
    operator = relationship("Operator", back_populates="source_configs")

class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=True)
    message = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    lead = relationship("Lead", back_populates="contacts")
    source = relationship("Source", back_populates="contacts")
    operator = relationship("Operator", back_populates="contacts")

Base.metadata.create_all(bind=engine)

# Pydantic schemas
class OperatorCreate(BaseModel):
    name: str
    is_active: bool = True
    max_load: int = 10

class OperatorUpdate(BaseModel):
    is_active: Optional[bool] = None
    max_load: Optional[int] = None

class OperatorResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    max_load: int
    current_load: int
    
    class Config:
        from_attributes = True

class SourceCreate(BaseModel):
    name: str
    description: Optional[str] = None

class SourceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    
    class Config:
        from_attributes = True

class SourceConfigCreate(BaseModel):
    operator_id: int
    weight: int = 10

class ContactCreate(BaseModel):
    lead_external_id: str
    source_id: int
    message: Optional[str] = None
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_email: Optional[str] = None

class ContactResponse(BaseModel):
    id: int
    lead_id: int
    source_id: int
    operator_id: Optional[int]
    message: Optional[str]
    is_active: bool
    created_at: datetime
    operator_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class LeadResponse(BaseModel):
    id: int
    external_id: str
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    total_contacts: int
    
    class Config:
        from_attributes = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI app
app = FastAPI(title="Mini-CRM Lead Distribution System")

# Service functions
def get_operator_load(db: Session, operator_id: int) -> int:
    """Calculate current load of operator (active contacts)"""
    return db.query(Contact).filter(
        Contact.operator_id == operator_id,
        Contact.is_active == True
    ).count()

def select_operator_by_weight(db: Session, source_id: int) -> Optional[Operator]:
    """Select operator based on weights and availability"""
    configs = db.query(SourceOperatorConfig).filter(
        SourceOperatorConfig.source_id == source_id
    ).all()
    
    if not configs:
        return None
    
    # Filter available operators
    available = []
    for config in configs:
        operator = config.operator
        if operator.is_active:
            current_load = get_operator_load(db, operator.id)
            if current_load < operator.max_load:
                available.append((operator, config.weight))
    
    if not available:
        return None
    
    # Weighted random selection
    operators, weights = zip(*available)
    total_weight = sum(weights)
    rand_val = random.uniform(0, total_weight)
    
    cumulative = 0
    for operator, weight in zip(operators, weights):
        cumulative += weight
        if rand_val <= cumulative:
            return operator
    
    return operators[-1]

# API Endpoints

# Operators
@app.post("/operators/", response_model=OperatorResponse)
def create_operator(operator: OperatorCreate, db: Session = Depends(get_db)):
    db_operator = Operator(**operator.dict())
    db.add(db_operator)
    db.commit()
    db.refresh(db_operator)
    
    return OperatorResponse(
        id=db_operator.id,
        name=db_operator.name,
        is_active=db_operator.is_active,
        max_load=db_operator.max_load,
        current_load=get_operator_load(db, db_operator.id)
    )

@app.get("/operators/", response_model=List[OperatorResponse])
def list_operators(db: Session = Depends(get_db)):
    operators = db.query(Operator).all()
    return [
        OperatorResponse(
            id=op.id,
            name=op.name,
            is_active=op.is_active,
            max_load=op.max_load,
            current_load=get_operator_load(db, op.id)
        )
        for op in operators
    ]

@app.patch("/operators/{operator_id}", response_model=OperatorResponse)
def update_operator(operator_id: int, operator: OperatorUpdate, db: Session = Depends(get_db)):
    db_operator = db.query(Operator).filter(Operator.id == operator_id).first()
    if not db_operator:
        raise HTTPException(status_code=404, detail="Operator not found")
    
    if operator.is_active is not None:
        db_operator.is_active = operator.is_active
    if operator.max_load is not None:
        db_operator.max_load = operator.max_load
    
    db.commit()
    db.refresh(db_operator)
    
    return OperatorResponse(
        id=db_operator.id,
        name=db_operator.name,
        is_active=db_operator.is_active,
        max_load=db_operator.max_load,
        current_load=get_operator_load(db, db_operator.id)
    )

# Sources
@app.post("/sources/", response_model=SourceResponse)
def create_source(source: SourceCreate, db: Session = Depends(get_db)):
    db_source = Source(**source.dict())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source

@app.get("/sources/", response_model=List[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    return db.query(Source).all()

# Source configuration
@app.post("/sources/{source_id}/operators/")
def add_operator_to_source(source_id: int, config: SourceConfigCreate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    operator = db.query(Operator).filter(Operator.id == config.operator_id).first()
    if not operator:
        raise HTTPException(status_code=404, detail="Operator not found")
    
    # Check if config already exists
    existing = db.query(SourceOperatorConfig).filter(
        SourceOperatorConfig.source_id == source_id,
        SourceOperatorConfig.operator_id == config.operator_id
    ).first()
    
    if existing:
        existing.weight = config.weight
        db.commit()
        return {"message": "Configuration updated", "weight": config.weight}
    
    db_config = SourceOperatorConfig(
        source_id=source_id,
        operator_id=config.operator_id,
        weight=config.weight
    )
    db.add(db_config)
    db.commit()
    
    return {"message": "Operator added to source", "weight": config.weight}

@app.get("/sources/{source_id}/operators/")
def get_source_operators(source_id: int, db: Session = Depends(get_db)):
    configs = db.query(SourceOperatorConfig).filter(
        SourceOperatorConfig.source_id == source_id
    ).all()
    
    return [
        {
            "operator_id": c.operator_id,
            "operator_name": c.operator.name,
            "weight": c.weight,
            "is_active": c.operator.is_active,
            "current_load": get_operator_load(db, c.operator_id),
            "max_load": c.operator.max_load
        }
        for c in configs
    ]

# Contacts (main distribution logic)
@app.post("/contacts/", response_model=ContactResponse)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    # Find or create lead
    lead = db.query(Lead).filter(Lead.external_id == contact.lead_external_id).first()
    if not lead:
        lead = Lead(
            external_id=contact.lead_external_id,
            name=contact.lead_name,
            phone=contact.lead_phone,
            email=contact.lead_email
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
    
    # Check source exists
    source = db.query(Source).filter(Source.id == contact.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Select operator
    operator = select_operator_by_weight(db, contact.source_id)
    
    # Create contact
    db_contact = Contact(
        lead_id=lead.id,
        source_id=contact.source_id,
        operator_id=operator.id if operator else None,
        message=contact.message,
        is_active=True
    )
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    
    return ContactResponse(
        id=db_contact.id,
        lead_id=db_contact.lead_id,
        source_id=db_contact.source_id,
        operator_id=db_contact.operator_id,
        message=db_contact.message,
        is_active=db_contact.is_active,
        created_at=db_contact.created_at,
        operator_name=operator.name if operator else None
    )

@app.get("/contacts/", response_model=List[ContactResponse])
def list_contacts(db: Session = Depends(get_db)):
    contacts = db.query(Contact).all()
    return [
        ContactResponse(
            id=c.id,
            lead_id=c.lead_id,
            source_id=c.source_id,
            operator_id=c.operator_id,
            message=c.message,
            is_active=c.is_active,
            created_at=c.created_at,
            operator_name=c.operator.name if c.operator else None
        )
        for c in contacts
    ]

# Leads
@app.get("/leads/", response_model=List[LeadResponse])
def list_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).all()
    return [
        LeadResponse(
            id=lead.id,
            external_id=lead.external_id,
            name=lead.name,
            phone=lead.phone,
            email=lead.email,
            total_contacts=len(lead.contacts)
        )
        for lead in leads
    ]

@app.get("/leads/{lead_id}/contacts/")
def get_lead_contacts(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return [
        {
            "id": c.id,
            "source_id": c.source_id,
            "source_name": c.source.name,
            "operator_id": c.operator_id,
            "operator_name": c.operator.name if c.operator else None,
            "message": c.message,
            "created_at": c.created_at,
            "is_active": c.is_active
        }
        for c in lead.contacts
    ]

# Statistics
@app.get("/statistics/")
def get_statistics(db: Session = Depends(get_db)):
    return {
        "total_operators": db.query(Operator).count(),
        "active_operators": db.query(Operator).filter(Operator.is_active == True).count(),
        "total_leads": db.query(Lead).count(),
        "total_contacts": db.query(Contact).count(),
        "active_contacts": db.query(Contact).filter(Contact.is_active == True).count(),
        "total_sources": db.query(Source).count()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)