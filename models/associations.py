from app import db

post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('blog.posts.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('blog.tags.id'), primary_key=True),
    schema='blog'
)

saved_posts = db.Table('saved_posts',
    db.Column('user_id', db.Integer, db.ForeignKey('blog.users.id'), primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('blog.posts.id'), primary_key=True),
    db.Column('saved_at', db.DateTime, nullable=False, default=db.func.now()),
    schema='blog'
)

favorite_tags = db.Table('favorite_tags',
    db.Column('user_id', db.Integer, db.ForeignKey('blog.users.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('blog.tags.id'), primary_key=True),
    db.Column('favorited_at', db.DateTime, nullable=False, default=db.func.now()),
    schema='blog'
)

follows = db.Table('follows',
    db.Column('follower_id', db.Integer, db.ForeignKey('blog.users.id'), primary_key=True),
    db.Column('following_id', db.Integer, db.ForeignKey('blog.users.id'), primary_key=True),
    db.Column('followed_at', db.DateTime, nullable=False, default=db.func.now()),
    schema='blog'
)
