from app import db
from datetime import datetime

class Post(db.Model):
    __tablename__ = 'posts'
    __table_args__ = {'schema': 'blog'}
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='published')
    author_id = db.Column(db.Integer, db.ForeignKey('blog.users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    replies = db.relationship('Reply', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    tags = db.relationship('Tag', secondary='blog.post_tags', backref=db.backref('posts', lazy='dynamic'))
    
    def to_dict(self, include_author=True, include_tags=True, include_stats=True):
        data = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_author:
            data['author'] = {
                'id': self.author.id,
                'username': self.author.username,
                'avatar_url': self.author.avatar_url
            }
        
        if include_tags:
            data['tags'] = [tag.to_dict() for tag in self.tags]
        
        if include_stats:
            data['reply_count'] = self.replies.count()
            data['saved_count'] = self.saved_by.count()
        
        return data
    
    def __repr__(self):
        return f'<Post {self.title}>'
