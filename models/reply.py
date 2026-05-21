from app import db
from datetime import datetime

class Reply(db.Model):
    __tablename__ = 'replies'
    __table_args__ = {'schema': 'blog'}
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('blog.users.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blog.posts.id'), nullable=False, index=True)
    parent_reply_id = db.Column(db.Integer, db.ForeignKey('blog.replies.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    child_replies = db.relationship('Reply', backref=db.backref('parent_reply', remote_side=[id]), lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_author=True, include_children=False):
        data = {
            'id': self.id,
            'content': self.content,
            'post_id': self.post_id,
            'parent_reply_id': self.parent_reply_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_author:
            data['author'] = {
                'id': self.author.id,
                'username': self.author.username,
                'avatar_url': self.author.avatar_url
            }
        
        if include_children:
            data['replies'] = [reply.to_dict(include_children=True) for reply in self.child_replies]
        
        return data
    
    def __repr__(self):
        return f'<Reply {self.id} on Post {self.post_id}>'
