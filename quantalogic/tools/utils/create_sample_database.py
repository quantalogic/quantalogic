import random
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()
fake = Faker()

def create_sample_database(db_path: str) -> None:
    """
    Creates a sample SQLite database with 5 tables and 10 rows each.
    
    Args:
        db_path: Path to the SQLite database file (e.g., 'sample.db')
    """
    # Define database schema
    class Customer(Base):
        __tablename__ = 'customers'
        id = Column(Integer, primary_key=True)
        name = Column(String)
        email = Column(String)
        addresses = relationship("Address", back_populates="customer")
        orders = relationship("Order", back_populates="customer")

    class Address(Base):
        __tablename__ = 'addresses'
        id = Column(Integer, primary_key=True)
        street = Column(String)
        city = Column(String)
        customer_id = Column(Integer, ForeignKey('customers.id'))
        customer = relationship("Customer", back_populates="addresses")

    class Product(Base):
        __tablename__ = 'products'
        id = Column(Integer, primary_key=True)
        name = Column(String)
        price = Column(Float)

    class Order(Base):
        __tablename__ = 'orders'
        id = Column(Integer, primary_key=True)
        order_date = Column(Date)
        customer_id = Column(Integer, ForeignKey('customers.id'))
        customer = relationship("Customer", back_populates="orders")
        items = relationship("OrderItem", back_populates="order")

    class OrderItem(Base):
        __tablename__ = 'order_items'
        id = Column(Integer, primary_key=True)
        quantity = Column(Integer)
        order_id = Column(Integer, ForeignKey('orders.id'))
        product_id = Column(Integer, ForeignKey('products.id'))
        order = relationship("Order", back_populates="items")
        product = relationship("Product")

    # Create database and tables
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)  # noqa: N806
    session = Session()

    # Generate sample data
    try:
        # Create 10 customers
        customers = []
        for _ in range(10):
            customer = Customer(
                name=fake.name(),
                email=fake.email()
            )
            customers.append(customer)
            session.add(customer)
        
        session.commit()

        # Create 10 addresses (1 per customer)
        for customer in customers:
            address = Address(
                street=fake.street_address(),
                city=fake.city(),
                customer=customer
            )
            session.add(address)
        
        # Create 10 products
        products = []
        for _ in range(10):
            product = Product(
                name=fake.word().capitalize(),
                price=round(random.uniform(10, 1000), 2)
            )
            products.append(product)
            session.add(product)
        
        # Create 10 orders (1 per customer)
        orders = []
        start_date = datetime.now() - timedelta(days=365)
        for customer in customers:
            order = Order(
                order_date=fake.date_between(start_date=start_date),
                customer=customer
            )
            orders.append(order)
            session.add(order)
        
        # Create 10 order items (1 per order)
        for order in orders:
            order_item = OrderItem(
                quantity=random.randint(1, 5),
                order=order,
                product=random.choice(products)
            )
            session.add(order_item)

        session.commit()
    finally:
        session.close()

# Example usage
if __name__ == "__main__":
    create_sample_database("sample.db")
    print("Sample database created successfully!")