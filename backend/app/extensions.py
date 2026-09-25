"""
Shared Flask extension singletons.

Defined here (not in __init__.py) to break circular import chains:
  models.py imports db  →  auth.py imports db + models  →  __init__.py imports all
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
