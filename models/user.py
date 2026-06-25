from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Account(Base):
    """Canonical Schema Definition."""
    __tablename__ = 'accounts'
    
    account_id = Column(String(36), primary_key=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
