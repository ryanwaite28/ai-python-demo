import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.tag import Tag
from models.post import Post
import metrics

tags_bp = Blueprint('tags', __name__)
logger = logging.getLogger(__name__)


@tags_bp.route('', methods=['GET'])
def get_tags():
    popular = request.args.get('popular', 'false').lower() == 'true'
    limit = request.args.get('limit', 50, type=int)
    logger.info('Listing tags | popular=%s limit=%s', popular, limit)

    query = Tag.query

    if popular:
        tags = db.session.query(Tag).join(Tag.posts).group_by(Tag.id).order_by(
            db.func.count(Post.id).desc()
        ).limit(limit).all()
    else:
        tags = query.order_by(Tag.name).limit(limit).all()

    return jsonify({
        'tags': [tag.to_dict(include_stats=True) for tag in tags]
    }), 200


@tags_bp.route('/<tag_name>/posts', methods=['GET'])
def get_posts_by_tag(tag_name):
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    logger.info('Fetching posts by tag | tag_name=%s page=%s limit=%s', tag_name, page, limit)
    tag = Tag.query.filter_by(name=Tag.normalize_name(tag_name)).first_or_404()

    pagination = tag.posts.filter_by(status='published').order_by(Post.created_at.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )

    return jsonify({
        'posts': [post.to_dict() for post in pagination.items],
        'tag': tag.to_dict(),
        'total': pagination.total
    }), 200


@tags_bp.route('/<int:tag_id>/favorite', methods=['POST'])
@login_required
def favorite_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)

    if tag in current_user.favorite_tags:
        logger.info('Tag already favorited | tag_id=%s user_id=%s', tag_id, current_user.id)
        return jsonify({'success': True, 'favorited': True}), 200

    current_user.favorite_tags.append(tag)

    try:
        db.session.commit()
        metrics.tag_favorites_total.inc()
        logger.info('Tag favorited | tag_id=%s tag_name=%s user_id=%s', tag_id, tag.name, current_user.id)
        return jsonify({'success': True, 'favorited': True}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Favorite tag DB error | tag_id=%s user_id=%s error=%s', tag_id, current_user.id, e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@tags_bp.route('/<int:tag_id>/favorite', methods=['DELETE'])
@login_required
def unfavorite_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)

    if tag in current_user.favorite_tags:
        current_user.favorite_tags.remove(tag)
        try:
            db.session.commit()
            metrics.tag_unfavorites_total.inc()
            logger.info('Tag unfavorited | tag_id=%s tag_name=%s user_id=%s', tag_id, tag.name, current_user.id)
            return jsonify({'success': True, 'favorited': False}), 200
        except Exception as e:
            db.session.rollback()
            logger.error('Unfavorite tag DB error | tag_id=%s user_id=%s error=%s', tag_id, current_user.id, e, exc_info=True)
            return jsonify({'error': str(e)}), 500

    return jsonify({'success': True, 'favorited': False}), 200


@tags_bp.route('/favorites', methods=['GET'])
@login_required
def get_favorite_tags():
    logger.info('Fetching favorite tags | user_id=%s', current_user.id)
    tags = [tag.to_dict(include_stats=True) for tag in current_user.favorite_tags]

    return jsonify({'tags': tags}), 200


@tags_bp.route('/search', methods=['GET'])
def search_posts():
    tags_param = request.args.get('tags', '')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    match = request.args.get('match', 'all')

    if not tags_param:
        logger.warning('Tag search failed | reason=no_tags_provided')
        return jsonify({'error': 'No tags provided'}), 400

    logger.info('Searching posts by tags | tags=%s match=%s page=%s limit=%s', tags_param, match, page, limit)

    tag_names = [Tag.normalize_name(t.strip()) for t in tags_param.split(',')]
    tags = Tag.query.filter(Tag.name.in_(tag_names)).all()

    if not tags:
        logger.info('Tag search returned no matching tags | tags_searched=%s', tag_names)
        return jsonify({'posts': [], 'total': 0, 'tags_searched': []}), 200

    query = Post.query.filter_by(status='published')

    if match == 'all':
        for tag in tags:
            query = query.filter(Post.tags.contains(tag))
    else:
        query = query.filter(Post.tags.any(Tag.id.in_([t.id for t in tags])))

    pagination = query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )

    logger.info('Tag search complete | tags=%s match=%s total=%s', tags_param, match, pagination.total)
    return jsonify({
        'posts': [post.to_dict() for post in pagination.items],
        'total': pagination.total,
        'tags_searched': [tag.to_dict() for tag in tags]
    }), 200
