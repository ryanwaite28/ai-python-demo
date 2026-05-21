from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

views_bp = Blueprint('views', __name__)

# Public Routes
@views_bp.route('/')
def index():
    return render_template('index.html')

@views_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    return render_template('auth/login.html')

@views_bp.route('/signup')
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    return render_template('auth/signup.html')

@views_bp.route('/posts')
def posts():
    return render_template('posts/index.html')

@views_bp.route('/posts/<int:post_id>')
def post_view(post_id):
    return render_template('posts/view.html')

@views_bp.route('/users/<username>')
def user_profile(username):
    return render_template('users/profile.html')

@views_bp.route('/search')
def search():
    return render_template('search/results.html')

@views_bp.route('/tags')
def tags():
    return render_template('tags/index.html')

# Private Routes (require authentication)
@views_bp.route('/home/<int:user_id>')
@login_required
def home(user_id):
    if user_id != current_user.id:
        return redirect(url_for('views.home', user_id=current_user.id))
    return render_template('home/index.html', user_id=user_id)

@views_bp.route('/feed')
@login_required
def feed():
    return render_template('feed/index.html')

@views_bp.route('/posts/create')
@login_required
def post_create():
    return render_template('posts/create.html')

@views_bp.route('/posts/<int:post_id>/edit')
@login_required
def post_edit(post_id):
    return render_template('posts/edit.html')

@views_bp.route('/messages')
@login_required
def messages():
    return render_template('messages/inbox.html')

@views_bp.route('/messages/compose')
@login_required
def compose_message():
    return render_template('messages/compose.html')

@views_bp.route('/settings')
@login_required
def settings():
    return render_template('settings/index.html')
