from app import app, db
from models import Barber, Service
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        # Create tables
        db.create_all()

        # Check if we already have data
        if Barber.query.first() is not None:
            print("Database already initialized!")
            return

        # Create sample barbers
        barbers = [
            Barber(
                username="john",
                password=generate_password_hash("password123"),
                name="John Smith",
                email="vojjta99@gmail.com"
            ),
        ]

        # Create services
        services = [
            Service(name="Men's Haircut", duration=30, price=30.00),
            Service(name="Beard Trim", duration=15, price=15.00),
            Service(name="Hair & Beard Combo", duration=45, price=40.00),
            Service(name="Kids Haircut", duration=20, price=20.00),
            Service(name="Senior's Haircut", duration=30, price=25.00)
        ]

        # Add to database
        for barber in barbers:
            db.session.add(barber)
        
        for service in services:
            db.session.add(service)

        # Commit changes
        db.session.commit()
        print("Database initialized with sample data!")

if __name__ == "__main__":
    init_db() 