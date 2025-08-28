from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    ForeignKey,
    JSON,
    BigInteger,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Product(Base):
    """
    SQLAlchemy ORM model for a product.
    Represents the core, static information about a product.
    """

    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, index=True)
    uniq_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String(512), nullable=False)
    category_tree = Column(String(1024))
    pid = Column(String(255), index=True)
    description = Column(Text)
    brand = Column(String(255), index=True)
    product_url = Column(String(2048))
    image_urls = Column(JSON)

    # Relationship to variants
    variants = relationship("ProductVariant", back_populates="product")


class ProductVariant(Base):
    """
    SQLAlchemy ORM model for a product variant.
    Stores dynamic data related to a product, like price and stock.
    """

    __tablename__ = "product_variants"

    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False)
    retail_price = Column(Float)
    discounted_price = Column(Float)
    stock = Column(Integer, default=100, nullable=False)

    # Relationship to product
    product = relationship("Product", back_populates="variants")
