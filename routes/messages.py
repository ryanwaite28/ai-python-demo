import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from models.message import Message
from models.user import User
import metrics

messages_bp = Blueprint('messages', __name__)
logger = logging.getLogger(__name__)


@messages_bp.route('', methods=['GET'])
@login_required
def get_inbox():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    logger.info('Fetching inbox | user_id=%s page=%s limit=%s', current_user.id, page, limit)

    pagination = current_user.received_messages.order_by(Message.created_at.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )

    unread_count = current_user.received_messages.filter_by(is_read=False).count()

    return jsonify({
        'messages': [msg.to_dict() for msg in pagination.items],
        'total': pagination.total,
        'unread_count': unread_count
    }), 200


@messages_bp.route('/sent', methods=['GET'])
@login_required
def get_sent():
    logger.info('Fetching sent messages | user_id=%s', current_user.id)
    messages = current_user.sent_messages.order_by(Message.created_at.desc()).all()

    return jsonify({
        'messages': [msg.to_dict() for msg in messages]
    }), 200


@messages_bp.route('/<int:message_id>', methods=['GET'])
@login_required
def get_message(message_id):
    message = Message.query.get_or_404(message_id)

    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        logger.warning(
            'Message access unauthorized | message_id=%s user_id=%s sender_id=%s recipient_id=%s',
            message_id, current_user.id, message.sender_id, message.recipient_id,
        )
        return jsonify({'error': 'Unauthorized'}), 403

    logger.info('Message fetched | message_id=%s user_id=%s', message_id, current_user.id)
    return jsonify({'message': message.to_dict()}), 200


@messages_bp.route('', methods=['POST'])
@login_required
def send_message():
    data = request.get_json()

    if not data or not data.get('recipient_id') or not data.get('content'):
        logger.warning('Send message failed | reason=missing_fields user_id=%s', current_user.id)
        return jsonify({'error': 'Missing required fields'}), 400

    recipient = User.query.get(data['recipient_id'])
    if not recipient:
        logger.warning('Send message failed | reason=recipient_not_found recipient_id=%s user_id=%s', data['recipient_id'], current_user.id)
        return jsonify({'error': 'Recipient not found'}), 404

    if recipient.id == current_user.id:
        logger.warning('Send message failed | reason=self_message user_id=%s', current_user.id)
        return jsonify({'error': 'Cannot send message to yourself'}), 400

    message = Message(
        sender_id=current_user.id,
        recipient_id=data['recipient_id'],
        subject=data.get('subject'),
        content=data['content']
    )

    try:
        db.session.add(message)
        db.session.commit()
        metrics.messages_sent_total.inc()
        logger.info('Message sent | message_id=%s sender_id=%s recipient_id=%s', message.id, current_user.id, recipient.id)
        return jsonify({
            'success': True,
            'message': message.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error('Send message DB error | sender_id=%s recipient_id=%s error=%s', current_user.id, data.get('recipient_id'), e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)

    if message.recipient_id != current_user.id and message.sender_id != current_user.id:
        logger.warning(
            'Delete message unauthorized | message_id=%s user_id=%s sender_id=%s recipient_id=%s',
            message_id, current_user.id, message.sender_id, message.recipient_id,
        )
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        db.session.delete(message)
        db.session.commit()
        logger.info('Message deleted | message_id=%s user_id=%s', message_id, current_user.id)
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Delete message DB error | message_id=%s user_id=%s error=%s', message_id, current_user.id, e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/<int:message_id>/read', methods=['PUT'])
@login_required
def mark_as_read(message_id):
    message = Message.query.get_or_404(message_id)

    if message.recipient_id != current_user.id:
        logger.warning(
            'Mark-as-read unauthorized | message_id=%s user_id=%s recipient_id=%s',
            message_id, current_user.id, message.recipient_id,
        )
        return jsonify({'error': 'Unauthorized'}), 403

    message.is_read = True

    try:
        db.session.commit()
        metrics.messages_read_total.inc()
        logger.info('Message marked as read | message_id=%s user_id=%s', message_id, current_user.id)
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        logger.error('Mark-as-read DB error | message_id=%s user_id=%s error=%s', message_id, current_user.id, e, exc_info=True)
        return jsonify({'error': str(e)}), 500
