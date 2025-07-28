from app import db
from app.models import Post, BlogspotBlog, BlogspotAccount
from datetime import datetime
import requests
import os
import json

def run_blogspot_scheduler(app):
    with app.app_context():
        now = datetime.now()
        # Ambil semua post yang waktunya sudah tiba dan status masih pending
        posts = Post.query.filter(Post.status == 'pending', Post.scheduled_time <= now).all()
        for post in posts:
            blog = BlogspotBlog.query.get(post.blogspot_blog_id)
            if not blog:
                post.status = 'failed'
                db.session.commit()
                continue
            account = BlogspotAccount.query.get(blog.blogspot_account_id)
            if not account:
                post.status = 'failed'
                db.session.commit()
                continue

            # Siapkan data untuk Blogger API
            url = f"https://www.googleapis.com/blogger/v3/blogs/{blog.blog_id}/posts/"
            headers = {
                "Authorization": f"Bearer {account.access_token}",
                "Content-Type": "application/json"
            }
            data = {
                "title": post.title,
                "content": post.content,
                "labels": parse_labels(post.labels) if post.labels else []
            }
            if post.search_description:
                data["searchDescription"] = {"value": post.search_description}

            # POST ke Blogger
            try:
                r = requests.post(url, json=data, headers=headers)
                if r.status_code == 401:
                    # Coba refresh access token jika expired
                    new_token = refresh_google_token(account)
                    if new_token:
                        account.access_token = new_token
                        db.session.commit()
                        headers["Authorization"] = f"Bearer {account.access_token}"
                        r = requests.post(url, json=data, headers=headers)
                if r.status_code in [200, 201]:
                    post.status = 'posted'
                else:
                    post.status = f'failed'
                db.session.commit()
            except Exception as e:
                post.status = 'failed'
                db.session.commit()

def refresh_google_token(account):
    import requests
    import os, json
    # Path ke credentials.json
    cred_path = os.path.join(os.path.dirname(__file__), "credentials", "credentials.json")
    with open(cred_path) as f:
        info = json.load(f)["installed"]
    payload = {
        "client_id": info["client_id"],
        "client_secret": info["client_secret"],
        "refresh_token": account.refresh_token,
        "grant_type": "refresh_token"
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload)
    if r.ok:
        return r.json()["access_token"]
    else:
        return None


def parse_labels(label_str):
    label_str = (label_str or '').strip()
    # Jika string-nya seperti JSON list (bug lama)
    if label_str.startswith("[") and label_str.endswith("]"):
        try:
            label_data = json.loads(label_str)
            if isinstance(label_data, list):
                # Kalau format lama [{"value": "Artikel"}]
                if all(isinstance(x, dict) and "value" in x for x in label_data):
                    return [x["value"] for x in label_data]
                # Kalau sudah benar ["Artikel", ...]
                elif all(isinstance(x, str) for x in label_data):
                    return label_data
        except Exception:
            pass
    # Kalau cuma string biasa: "Artikel, Python"
    return [x.strip() for x in label_str.split(",") if x.strip()]

