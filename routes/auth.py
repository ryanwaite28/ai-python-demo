from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user
from app import db
from models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    user = User(
        username=data['username'],
        email=data['email'],
        bio=data.get('bio'),
        avatar_url=data.get('avatar_url')
    )
    user.set_password(data['password'])
    
    try:
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('email_or_username') or not data.get('password'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    user = User.query.filter(
        (User.email == data['email_or_username']) | 
        (User.username == data['email_or_username'])
    ).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    remember = data.get('remember_me', False)
    login_user(user, remember=remember)
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'success': True}), 200

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    if current_user.is_authenticated:
        return jsonify({'user': current_user.to_dict()}), 200
    return jsonify({'error': 'Not authenticated'}), 401
