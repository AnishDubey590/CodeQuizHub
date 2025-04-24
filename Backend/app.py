from flask import Flask

from flask_sqlalchemy import SQLAlchemy

 


# Initialize the Flask application and the database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///code_quiz.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '1212121212121'
db = SQLAlchemy(app)


 
# Import routes to register them
from routes import *

# Run the application
if __name__ == "__main__":
    app.run(debug=True, port=1565)
