import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.post import Post
from models.tag import Tag

feed_bp = Blueprint('feed', __name__)
logger = logging.getLogger(__name__)


@feed_bp.route('', methods=['GET'])
@login_required
def get_feed():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)

    favorite_tags = current_user.favorite_tags

    if not favorite_tags:
        logger.info('Feed empty | reason=no_favorite_tags user_id=%s', current_user.id)
        return jsonify({
            'posts': [],
            'total': 0,
            'based_on_tags': []
        }), 200

    logger.info('Fetching feed | user_id=%s page=%s limit=%s num_tags=%s', current_user.id, page, limit, len(favorite_tags))

    query = Post.query.filter_by(status='published').filter(
        Post.tags.any(Tag.id.in_([tag.id for tag in favorite_tags]))
    ).order_by(Post.created_at.desc())

    pagination = query.paginate(page=page, per_page=limit, error_out=False)

    logger.info('Feed fetched | user_id=%s total=%s page=%s', current_user.id, pagination.total, page)
    return jsonify({
        'posts': [post.to_dict() for post in pagination.items],
        'total': pagination.total,
        'based_on_tags': [tag.to_dict() for tag in favorite_tags]
    }), 200
