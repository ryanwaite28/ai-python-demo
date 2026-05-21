from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.user import User
from models.post import Post

users_bp = Blueprint('users', __name__)

@users_bp.route('/<username>', methods=['GET'])
def get_user(username):
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
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    
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
        return jsonify({'error': 'Cannot follow yourself'}), 400
    
    current_user.follow(user)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'following': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@users_bp.route('/<username>/follow', methods=['DELETE'])
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    current_user.unfollow(user)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'following': False}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@users_bp.route('/<username>/followers', methods=['GET'])
def get_followers(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    followers = [follower.to_dict() for follower in user.followers]
    
    return jsonify({'followers': followers}), 200

@users_bp.route('/<username>/following', methods=['GET'])
def get_following(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    following = [followed.to_dict() for followed in user.following]
    
    return jsonify({'following': following}), 200

@users_bp.route('/me/saved', methods=['GET'])
@login_required
def get_saved_posts():
    posts = [post.to_dict() for post in current_user.saved_posts]
    
    return jsonify({'posts': posts}), 200
