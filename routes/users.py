import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.user import User
from models.post import Post
import metrics

users_bp = Blueprint('users', __name__)
logger = logging.getLogger(__name__)


@users_bp.route('/<username>', methods=['GET'])
def get_user(username):
    logger.info('Fetching user profile | username=%s', username)
    user = User.query.filter_by(username=username).first_or_404()

    stats = {
        'posts_count': user.posts.count(),
        'followers_count': user.followers.count(),
        'following_count': user.following.count()
    }

    return jsonify({
        'user': user.to_dict(),
        'stats': stats
    }), 200


@users_bp.route('/<username>/posts', methods=['GET'])
def get_user_posts(username):
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    logger.info('Fetching user posts | username=%s page=%s limit=%s', username, page, limit)
    user = User.query.filter_by(username=username).first_or_404()

    pagination = user.posts.filter_by(status='published').order_by(Post.created_at.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )

    return jsonify({
        'posts': [post.to_dict() for post in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    }), 200


@users_bp.route('/<username>/follow', methods=['POST'])
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first_or_404()

    if user.id == current_user.id:
        logger.warning('Follow self attempted | user_id=%s', current_user.id)
        return jsonify({'error': 'Cannot follow yourself'}), 400

    current_user.follow(user)

    try:
        db.session.commit()
        metrics.user_follows_total.inc()
        logger.info('User followed | follower_id=%s followed_id=%s followed_username=%s', current_user.id, user.id, username)
        return jsonify({'success': True, 'following': True}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Follow user DB error | follower_id=%s followed_username=%s error=%s', current_user.id, username, e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@users_bp.route('/<username>/follow', methods=['DELETE'])
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()

    current_user.unfollow(user)

    try:
        db.session.commit()
        metrics.user_unfollows_total.inc()
        logger.info('User unfollowed | follower_id=%s unfollowed_id=%s unfollowed_username=%s', current_user.id, user.id, username)
        return jsonify({'success': True, 'following': False}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Unfollow user DB error | follower_id=%s unfollowed_username=%s error=%s', current_user.id, username, e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@users_bp.route('/<username>/followers', methods=['GET'])
def get_followers(username):
    logger.info('Fetching followers | username=%s', username)
    user = User.query.filter_by(username=username).first_or_404()

    followers = [follower.to_dict() for follower in user.followers]

    return jsonify({'followers': followers}), 200


@users_bp.route('/<username>/following', methods=['GET'])
def get_following(username):
    logger.info('Fetching following | username=%s', username)
    user = User.query.filter_by(username=username).first_or_404()

    following = [followed.to_dict() for followed in user.following]

    return jsonify({'following': following}), 200


@users_bp.route('/me/saved', methods=['GET'])
@login_required
def get_saved_posts():
    logger.info('Fetching saved posts | user_id=%s', current_user.id)
    posts = [post.to_dict() for post in current_user.saved_posts]

    return jsonify({'posts': posts}), 200
