# models.py
import enum
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Enum,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class PointEventType(enum.Enum):
    STAGE_ADVANCE = "STAGE_ADVANCE"
    BONUS_LEAD_INTAKE_SAME_DAY = "BONUS_LEAD_INTAKE_SAME_DAY"
    BONUS_WON_FAST = "BONUS_WON_FAST"
    DEAL_ROTTED_SUSPENSION = "DEAL_ROTTED_SUSPENSION"
    DEAL_REVIVED = "DEAL_REVIVED"

class PointsLedger(Base):
    __tablename__ = 'points_ledger'
    
    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(Enum(PointEventType), nullable=False)
    points = Column(Integer, nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DealStageEvent(Base):
    __tablename__ = 'deal_stage_events'
    
    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, nullable=False, index=True)
    stage_id = Column(Integer, nullable=False)
    entered_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # You can add a unique constraint later to ensure idempotency