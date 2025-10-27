from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models import User
from persistence import PersistenceLayer
import logging

logger = logging.getLogger(__name__)

def register_user(username, password):
    logger.info(f"register_user() called with username: {username}")
    with PersistenceLayer() as persistence:
        password_hash = generate_password_hash(password)
        logger.debug(f"Password hashed for user: {username}")
        user_id = persistence.create_user(username, password_hash)
        if user_id:
            logger.info(f"User created successfully in database: {username} (ID: {user_id})")
            user = User(userid=user_id, username=username, passwordhash=password_hash)
            logger.debug(f"User object created. get_id(): {user.get_id()}")
            return {'success': True, 'user': user, 'message': 'User registered.'}
        else:
            logger.warning(f"User creation failed (likely duplicate): {username}")
            return {'success': False, 'user': None, 'message': 'Username already exists. Please choose a different username.'}

def login_user_controller(username, password):
    logger.info(f"login_user_controller() called with username: {username}")
    with PersistenceLayer() as persistence:
        user_data = persistence.get_user_by_username(username)
        if user_data:
            logger.debug(f"User found in database: {username}")
            if check_password_hash(user_data['PasswordHash'], password):
                logger.info(f"Password verified for user: {username}")
                user = User(userid=user_data['UserID'], username=user_data['Username'], passwordhash=user_data['PasswordHash'])
                logger.debug(f"User object created. get_id(): {user.get_id()}")
                return {'success': True, 'user': user, 'message': 'Login successful.'}
            else:
                logger.warning(f"Invalid password for user: {username}")
        else:
            logger.warning(f"User not found in database: {username}")
        return {'success': False, 'user': None, 'message': 'Invalid username or password.'}
