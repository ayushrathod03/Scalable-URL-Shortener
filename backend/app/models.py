from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Index, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class URL(Base):
    __tablename__ = 'urls'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    short_token = Column(String(10), unique=True, nullable=False)
    long_url = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_urls_token', 'short_token'),
    )


class ClickAnalytics(Base):
    __tablename__ = 'click_analytics'
    
    id = Column(BigInteger, nullable=False)
    short_token = Column(String(10), ForeignKey('urls.short_token', ondelete='CASCADE'), nullable=False)
    clicked_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    country_code = Column(String(3), nullable=True)

    # Composite primary key for partitioning support
    __table_args__ = (
        PrimaryKeyConstraint('id', 'clicked_at'),
        Index('idx_analytics_token_time', 'short_token', 'clicked_at'),
        # Specify partitioning parameter for PostgreSQL
        {"postgresql_partition_by": "RANGE (clicked_at)"}
    )
