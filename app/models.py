from sqlalchemy import Column, Integer, String, Text, DateTime, Float
import datetime
from .database import Base

class EvaluationResponse(Base):
    __tablename__ = "evaluation_responses"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Datos básicos
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    
    # Tiempo
    time_minutes = Column(Float, nullable=False)
    
    # Likert (1-5)
    q1_filters = Column(Integer, nullable=False)
    q2_export = Column(Integer, nullable=False)
    q3_dedup_visual = Column(Integer, nullable=False)
    q4_dedup_error = Column(Integer, nullable=False)
    q5_screen_fatigue = Column(Integer, nullable=False)
    q6_screen_fear = Column(Integer, nullable=False)
    q7_synthesis_slow = Column(Integer, nullable=False)
    q8_reproducibility = Column(Integer, nullable=False)
    
    # Cualitativo
    q9_bottleneck = Column(Text, nullable=False)

class AIEvaluationResponse(Base):
    __tablename__ = "ai_evaluation_responses"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Datos básicos
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    
    # Tiempo
    time_minutes = Column(Float, nullable=False)
    
    # Likert (1-5)
    q1_ai_dedup_effort = Column(Integer, nullable=False)
    q2_ai_dedup_trust = Column(Integer, nullable=False)
    q3_ai_screening_fatigue = Column(Integer, nullable=False)
    q4_ai_screening_trust = Column(Integer, nullable=False)
    q5_ai_synthesis_time = Column(Integer, nullable=False)
    q6_ai_reproducibility = Column(Integer, nullable=False)
    q7_ai_viability = Column(Integer, nullable=False)
    
    # Cualitativas
    q8_ai_best_feature = Column(Text, nullable=False)
    q9_ai_hallucinations = Column(Text, nullable=False)
