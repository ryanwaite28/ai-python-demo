from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.post import Post
from models.reply import Reply
from models.tag import Tag
from models.associations import saved_posts

posts_bp = Blueprint('posts', __name__)

@posts_bp.route('', methods=['GET'])
def get_posts():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    sort = request.args.get('sort', 'recent')
    
    query = Post.query.filter_by(status='published')
    
    if sort == 'recent':
        query = query.order_by(Post.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        'posts': [post.to_dict() for post in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    }), 200

@posts_bp.route('/<int:post_id>', methods=['GET'])
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    replies = Reply.query.filter_by(post_id=post_id, parent_reply_id=None).order_by(Reply.created_at.asc()).all()
    
    return jsonify({
        'post': post.to_dict(),
        'replies': [reply.to_dict(include_children=True) for reply in replies]
    }), 200

@posts_bp.route('', methods=['POST'])
@login_required
def create_post():
    data = request.get_json()
    
    if not data or not data.get('title') or not data.get('content'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    post = Post(
        title=data['title'],
        content=data['content'],
        status=data.get('status', 'published'),
        author_id=current_user.id
    )
    
    if data.get('tags'):
        for tag_name in data['tags']:
            normalized_name = Tag.normalize_name(tag_name)
            tag = Tag.query.filter_by(name=normalized_name).first()
            if not tag:
                tag = Tag(name=normalized_name)
                db.session.add(tag)
            post.tags.append(tag)
    
    try:
        db.session.add(post)
        db.session.commit()
        return jsonify({
            'success': True,
            'post': post.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/<int:post_id>', methods=['PUT'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.author_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if data.get('title'):
        post.title = data['title']
    if data.get('content'):
        post.content = data['content']
    if data.get('status'):
        post.status = data['status']
    
    if 'tags' in data:
        post.tags = []
        for tag_name in data['tags']:
            normalized_name = Tag.normalize_name(tag_name)
            tag = Tag.query.filter_by(name=normalized_name).first()
            if not tag:
                tag = Tag(name=normalized_name)
                db.session.add(tag)
            post.tags.append(tag)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'post': post.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/<int:post_id>', methods=['DELETE'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.author_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        db.session.delete(post)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/<int:post_id>/save', methods=['POST'])
@login_required
def save_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post in current_user.saved_posts:
        return jsonify({'success': True, 'saved': True}), 200
    
    current_user.saved_posts.append(post)
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'saved': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/<int:post_id>/save', methods=['DELETE'])
@login_required
def unsave_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post in current_user.saved_posts:
        current_user.saved_posts.remove(post)
        try:
            db.session.commit()
            return jsonify({'success': True}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'success': True}), 200

@posts_bp.route('/<int:post_id>/replies', methods=['POST'])
@login_required
def create_reply(post_id):
    post = Post.query.get_or_404(post_id)
    data = request.get_json()
    
    if not data or not data.get('content'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    reply = Reply(
        content=data['content'],
        author_id=current_user.id,
        post_id=post_id,
        parent_reply_id=data.get('parent_reply_id')
    )
    
    try:
        db.session.add(reply)
        db.session.commit()
        return jsonify({
            'success': True,
            'reply': reply.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
