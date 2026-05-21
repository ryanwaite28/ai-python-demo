from app import db
from datetime import datetime

class Tag(db.Model):
    __tablename__ = 'tags'
    __table_args__ = {'schema': 'blog'}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }
        
        if include_stats:
            data['post_count'] = self.posts.count()
            data['favorited_count'] = self.favorited_by.count()
        
        return data
    
    @staticmethod
    def normalize_name(name):
        return name.lower().strip()
    
    def __repr__(self):
        return f'<Tag {self.name}>'
