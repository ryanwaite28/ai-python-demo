from app import db
from datetime import datetime

class Message(db.Model):
    __tablename__ = 'messages'
    __table_args__ = {'schema': 'blog'}
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('blog.users.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('blog.users.id'), nullable=False, index=True)
    subject = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def to_dict(self, include_sender=True, include_recipient=True):
        data = {
            'id': self.id,
            'subject': self.subject,
            'content': self.content,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }
        
        if include_sender:
            data['sender'] = {
                'id': self.sender.id,
                'username': self.sender.username,
                'avatar_url': self.sender.avatar_url
            }
        
        if include_recipient:
            data['recipient'] = {
                'id': self.recipient.id,
                'username': self.recipient.username,
                'avatar_url': self.recipient.avatar_url
            }
        
        return data
    
    def __repr__(self):
        return f'<Message from {self.sender_id} to {self.recipient_id}>'
