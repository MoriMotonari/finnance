# Import flask and template operators
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

# Define the WSGI application object
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configurations
app.config.from_object('finnance.config')
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'

# Define the database object which is imported
# by modules and controllers
db = SQLAlchemy(app)
from . import models
with app.app_context():
    db.create_all()


# Import a module / component using its blueprint handler variable
from finnance.main import main
from finnance.creation import creation
from finnance.analysis import anal, anal_api
from finnance.category import category
from finnance.queries import queries
from finnance.api import api_bp

# Register blueprints
app.register_blueprint(main)
app.register_blueprint(creation)
app.register_blueprint(anal)
app.register_blueprint(anal_api)
app.register_blueprint(category)
app.register_blueprint(queries)
app.register_blueprint(api_bp)
