import logging
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, current_user
from app import db
from models.user import User
import metrics

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        logger.warning('Signup failed | reason=missing_fields ip=%s', request.remote_addr)
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(username=data['username']).first():
        logger.warning('Signup failed | reason=username_taken username=%s ip=%s', data['username'], request.remote_addr)
        return jsonify({'error': 'Username already exists'}), 400

    if User.query.filter_by(email=data['email']).first():
        logger.warning('Signup failed | reason=email_taken email=%s ip=%s', data['email'], request.remote_addr)
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
        metrics.user_signups_total.inc()
        logger.info('User registered | user_id=%s username=%s', user.id, user.username)
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error('Signup DB error | username=%s error=%s', data.get('username'), e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('email_or_username') or not data.get('password'):
        logger.warning('Login failed | reason=missing_fields ip=%s', request.remote_addr)
        metrics.login_failures_total.labels(reason='missing_fields').inc()
        return jsonify({'error': 'Missing required fields'}), 400

    identifier = data['email_or_username']
    user = User.query.filter(
        (User.email == identifier) |
        (User.username == identifier)
    ).first()

    if not user or not user.check_password(data['password']):
        logger.warning('Login failed | reason=invalid_credentials identifier=%s ip=%s', identifier, request.remote_addr)
        metrics.login_failures_total.labels(reason='invalid_credentials').inc()
        return jsonify({'error': 'Invalid credentials'}), 401

    remember = data.get('remember_me', False)
    login_user(user, remember=remember)
    metrics.user_logins_total.labels(remember_me=str(remember).lower()).inc()
    logger.info('User logged in | user_id=%s username=%s remember=%s', user.id, user.username, remember)

    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    if current_user.is_authenticated:
        logger.info('User logged out | user_id=%s username=%s', current_user.id, current_user.username)
    logout_user()
    return jsonify({'success': True}), 200


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    if current_user.is_authenticated:
        logger.info('Current user fetched | user_id=%s', current_user.id)
        return jsonify({'user': current_user.to_dict()}), 200
    logger.warning('Unauthenticated /me request | ip=%s', request.remote_addr)
    return jsonify({'error': 'Not authenticated'}), 401
