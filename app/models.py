from . import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    full_name = db.Column(db.String(150))
    image_filename = db.Column(db.String(255), default='uploads/default_avatar.png')

# Sementara hanya model User dulu, nanti kita tambahkan model akun Blogspot/Facebook/Instagram & Post.
class BlogspotAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    access_token = db.Column(db.String(255))
    refresh_token = db.Column(db.String(255))
    blogs = db.relationship('BlogspotBlog', backref='account', cascade="all, delete-orphan")

class BlogspotBlog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blog_id = db.Column(db.String(120), unique=True)
    name = db.Column(db.String(255))
    blogspot_account_id = db.Column(db.Integer, db.ForeignKey('blogspot_account.id'))

class FacebookAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    page_id = db.Column(db.String(120))
    access_token = db.Column(db.String(255))

class InstagramAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    ig_user_id = db.Column(db.String(120))
    access_token = db.Column(db.String(255))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    labels = db.Column(db.String(255))
    search_description = db.Column(db.String(255))
    scheduled_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    blogspot_blog_id = db.Column(db.Integer, db.ForeignKey('blogspot_blog.id'))
    blogspot_blog = db.relationship('BlogspotBlog')

class Platform(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Facebook, Instagram, dll
    accounts = db.relationship('Account', backref='platform', lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Nama akun/page
    link = db.Column(db.String(250))                  # Tambahan: link akun
    tasks = db.relationship('TodoTask', backref='account', lazy=True)

class TodoTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    note = db.Column(db.String(250))
    deadline = db.Column(db.Date)
    time = db.Column(db.Time)  # Tambahan: waktu spesifik (opsional)
    priority = db.Column(db.String(20), default="sedang")  # tinggi/sedang/rendah
    is_done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recurring = db.Column(db.String(20))  # daily, weekly, monthly, None


class TodoTemplate(db.Model):
    __tablename__ = 'todo_templates'

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.String(20))  # Senin, Selasa, dst.
    task_title = db.Column(db.String(200))
    task_description = db.Column(db.String(500))
    priority = db.Column(db.String(20), default="sedang")
    platform_id = db.Column(db.Integer, db.ForeignKey('platform.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'))
    add_to_calendar = db.Column(db.String(3), default="no")  # Kolom untuk menentukan apakah ditambahkan ke kalender
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    platform = db.relationship('Platform', backref='templates')
    account = db.relationship('Account', backref='templates')

    def __repr__(self):
        return f"<TodoTemplate {self.day_of_week} - {self.task_title}>"





