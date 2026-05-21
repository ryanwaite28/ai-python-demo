---
description: How to develop a Python Flask application
---

# Flask Development Workflow

**Note**: For this workspace, refer to `PROJECT.md` as the source of truth for the demo blog site project, including features, database schema, and application structure.

## Initial Setup

1. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment**
   ```bash
   source venv/bin/activate
   ```

3. **Install Flask and dependencies**
   ```bash
   pip install flask python-dotenv flask-sqlalchemy flask-migrate flask-login flask-wtf
   ```
   For the demo blog project, this includes SQLAlchemy, migrations, authentication, and form handling.

4. **Create requirements.txt**
   ```bash
   pip freeze > requirements.txt
   ```

## Project Structure

5. **Create the Flask app structure**
   See `PROJECT.md` for the complete application structure including:
   - `app.py` - Main application entry point
   - `config.py` - Configuration settings
   - `models/` - Database models (User, Post, Reply, Tag, Message)
   - `routes/` - Route blueprints (auth, posts, users, messages, tags, feed)
   - `forms/` - WTForms for validation
   - `templates/` - Jinja2 HTML templates
   - `static/` - CSS, JS, images
   - `.env` - Environment variables (add to .gitignore)
   - `.flaskenv` - Flask-specific environment variables

## Development

6. **Set up environment variables in .flaskenv**
   ```
   FLASK_APP=app.py
   FLASK_ENV=development
   FLASK_DEBUG=1
   ```

7. **Run the development server**
   ```bash
   flask run
   ```
   Or with custom host/port:
   ```bash
   flask run --host=0.0.0.0 --port=8080
   ```

## Testing

8. **Install testing dependencies**
   ```bash
   pip install pytest pytest-flask
   ```

9. **Create tests directory and test files**
   - `tests/` directory
   - `tests/test_app.py` - Test cases

10. **Run tests**
    ```bash
    pytest
    ```

## Database Setup (if needed)

11. **Install database dependencies**
    ```bash
    pip install flask-sqlalchemy flask-migrate
    ```

12. **Initialize database migrations**
    ```bash
    flask db init
    flask db migrate -m "Initial migration"
    flask db upgrade
    ```

## Production Preparation

13. **Install production server**
    ```bash
    pip install gunicorn
    ```

14. **Update requirements.txt**
    ```bash
    pip freeze > requirements.txt
    ```

15. **Run with Gunicorn**
    ```bash
    gunicorn -w 4 -b 0.0.0.0:8000 app:app
    ```

## Demo Blog Project Development

16. **Follow the feature implementation order from PROJECT.md**
    - User authentication (signup, login)
    - Post management (create, view, edit, delete)
    - Reply system
    - Tag system and search
    - Social features (following, messaging)
    - Personalized feed
    - Saved posts and favorite tags

17. **Refer to PROJECT.md for**
    - Complete database schema
    - All API routes and endpoints
    - Security considerations
    - Feature specifications

## Python Development Best Practices

### Code Quality

18. **Follow PEP 8 Style Guide**
    - Use 4 spaces for indentation
    - Maximum line length of 79 characters for code
    - Use snake_case for functions and variables
    - Use PascalCase for class names
    - Install linter: `pip install flake8 black`
    - Format code: `black .`
    - Check style: `flake8 .`

19. **Type Hints**
    - Use type hints for function parameters and return values
    - Install mypy for type checking: `pip install mypy`
    - Run type checker: `mypy .`
    ```python
    def get_user(user_id: int) -> User:
        return User.query.get(user_id)
    ```

20. **Documentation**
    - Write docstrings for all functions, classes, and modules
    - Use Google or NumPy docstring format
    ```python
    def create_post(title: str, content: str) -> Post:
        """Create a new blog post.
        
        Args:
            title: The post title
            content: The post content
            
        Returns:
            The created Post object
        """
    ```

### Project Organization

21. **Use Blueprints**
    - Organize routes into logical blueprints
    - Keep related functionality together
    - Register blueprints in main app file

22. **Environment Variables**
    - Never commit `.env` files
    - Use `.env.example` as template
    - Store sensitive data (API keys, secrets) in environment variables
    - Access via `os.getenv()` or python-dotenv

23. **Configuration Management**
    - Use separate configs for development, testing, production
    - Create `config.py` with config classes
    ```python
    class Config:
        SECRET_KEY = os.getenv('SECRET_KEY')
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    ```

### Database Best Practices

24. **Migrations**
    - Always create migrations for schema changes
    - Review migration files before applying
    - Never edit migrations after they're committed
    - Use descriptive migration messages

25. **Query Optimization**
    - Use `db.session.query()` efficiently
    - Avoid N+1 queries with `joinedload()` or `selectinload()`
    - Add database indexes for frequently queried fields
    - Use pagination for large result sets

26. **Database Sessions**
    - Always commit or rollback transactions
    - Use context managers or try/except blocks
    ```python
    try:
        db.session.add(new_post)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e
    ```

### Security Best Practices

27. **Input Validation**
    - Validate all user input with Flask-WTF forms
    - Sanitize data before database insertion
    - Use parameterized queries (SQLAlchemy handles this)

28. **Authentication & Authorization**
    - Hash passwords with werkzeug.security
    - Use Flask-Login for session management
    - Implement CSRF protection (Flask-WTF provides this)
    - Use `@login_required` decorator for protected routes

29. **Error Handling**
    - Never expose stack traces in production
    - Log errors appropriately
    - Return user-friendly error messages
    - Use Flask error handlers
    ```python
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    ```

### Testing Best Practices

30. **Write Tests**
    - Aim for high test coverage (>80%)
    - Test all routes and edge cases
    - Use fixtures for test data
    - Separate unit tests from integration tests
    ```bash
    pytest --cov=. --cov-report=html
    ```

31. **Test Database**
    - Use separate test database
    - Reset database state between tests
    - Use factory pattern for test data

### Performance

32. **Caching**
    - Install Flask-Caching: `pip install flask-caching`
    - Cache expensive queries and computations
    - Set appropriate cache timeouts

33. **Static Files**
    - Minify CSS and JavaScript for production
    - Use CDN for AngularJS and other libraries
    - Enable gzip compression

### Version Control

34. **Git Best Practices**
    - Write clear, descriptive commit messages
    - Create `.gitignore` for Python projects
    - Ignore: `venv/`, `__pycache__/`, `*.pyc`, `.env`, `instance/`
    - Use feature branches for new development
    - Review code before merging

### Dependency Management

35. **Keep Dependencies Updated**
    - Regularly update packages: `pip list --outdated`
    - Pin versions in `requirements.txt`
    - Use `pip-tools` for dependency management
    - Check for security vulnerabilities: `pip install safety && safety check`

## Common Commands

- **Deactivate virtual environment**: `deactivate`
- **Install from requirements.txt**: `pip install -r requirements.txt`
- **Create new route**: Add `@app.route('/path')` decorator to function in route blueprints
- **Clear cache**: `find . -type d -name __pycache__ -exec rm -r {} +`
- **View PROJECT.md**: Reference for all project specifications and requirements
- **Format code**: `black . && flake8 .`
- **Run tests with coverage**: `pytest --cov=. --cov-report=html`
- **Check security**: `safety check`
