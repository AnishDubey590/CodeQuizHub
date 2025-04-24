from app import app, db

with app.app_context():
    print("Entering app context")
    db.create_all()
    print("Database created!")
