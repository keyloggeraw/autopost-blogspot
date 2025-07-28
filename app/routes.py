from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from .models import User, BlogspotAccount, BlogspotBlog, Post, Account
from . import db, login_manager
import os, requests, json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
import openai

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

bp = Blueprint('routes', __name__)

openai.api_key = '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' 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('routes.dashboard'))
        flash("Username/password salah")
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('routes.login'))

@bp.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    user = current_user
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        file = request.files.get('image')
        user.full_name = full_name
        user.username = username
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[-1].lower()
            new_filename = f"user_{user.id}.{ext}"
            upload_path = os.path.join(current_app.root_path, 'static', 'uploads', new_filename)
            file.save(upload_path)
            user.image_filename = f"uploads/{new_filename}"
        db.session.commit()
        flash('Data berhasil diperbarui.')
        return redirect(url_for('routes.account'))
    return render_template('account.html', user=user)

# --- List Blogspot Accounts ---
@bp.route('/blogspot_accounts')
@login_required
def list_blogspot():
    accounts = BlogspotAccount.query.all()
    return render_template('blogspot_accounts.html', accounts=accounts)

# --- Add Blogspot Account ---
@bp.route('/blogspot_accounts/add', methods=['GET', 'POST'])
@login_required
def add_blogspot():
    if request.method == 'POST':
        name = request.form['name']
        blog_id = request.form['blog_id']
        access_token = request.form['access_token']
        refresh_token = request.form['refresh_token']
        acc = BlogspotAccount(name=name, blog_id=blog_id, access_token=access_token, refresh_token=refresh_token)
        db.session.add(acc)
        db.session.commit()
        flash('Blogspot account added.')
        return redirect(url_for('routes.list_blogspot'))
    return render_template('add_blogspot.html')

# --- Edit Blogspot Account ---
@bp.route('/blogspot_accounts/edit/<int:acc_id>', methods=['GET', 'POST'])
@login_required
def edit_blogspot(acc_id):
    acc = BlogspotAccount.query.get_or_404(acc_id)
    if request.method == 'POST':
        acc.name = request.form['name']
        acc.blog_id = request.form['blog_id']
        acc.access_token = request.form['access_token']
        acc.refresh_token = request.form['refresh_token']
        db.session.commit()
        flash('Blogspot account updated.')
        return redirect(url_for('routes.list_blogspot'))
    return render_template('edit_blogspot.html', acc=acc)

# --- Delete Blogspot Account ---
@bp.route('/blogspot_accounts/delete/<int:acc_id>', methods=['POST'])
@login_required
def delete_blogspot(acc_id):
    acc = BlogspotAccount.query.get_or_404(acc_id)
    db.session.delete(acc)
    db.session.commit()
    flash('Blogspot account deleted.')
    return redirect(url_for('routes.list_blogspot'))

# -- Route: Authorize Blogspot Account (Start OAuth) --
@bp.route('/blogspot_accounts/oauth_start', methods=['GET'])
@login_required
def blogspot_oauth_start():
    flow = Flow.from_client_secrets_file(
        os.path.join(current_app.root_path, 'credentials', 'credentials.json'),
        scopes=['https://www.googleapis.com/auth/blogger'],
        redirect_uri=url_for('routes.blogspot_oauth_callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['oauth_state'] = state
    return redirect(authorization_url)

# -- Route: OAuth Callback --
@bp.route('/blogspot_accounts/oauth_callback')
def blogspot_oauth_callback():
    # Step 1: Setup Flow
    state = session.get('oauth_state')
    flow = Flow.from_client_secrets_file(
        os.path.join(current_app.root_path, 'credentials', 'credentials.json'),
        scopes=['https://www.googleapis.com/auth/blogger'],
        state=state,
        redirect_uri=url_for('routes.blogspot_oauth_callback', _external=True)
    )

    # Step 2: Ambil token dari Google
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # Step 3: Pakai access token untuk dapatkan semua blog
    headers = {"Authorization": f"Bearer {creds.token}"}
    resp = requests.get("https://www.googleapis.com/blogger/v3/users/self/blogs", headers=headers)
    data = resp.json()

    # Step 4: Validasi hasil
    if "items" not in data or not data["items"]:
        flash("Tidak ada blog ditemukan di akun Google ini.")
        return redirect(url_for('routes.list_blogspot'))

    # Step 5: Cek/tambah akun Google di BlogspotAccount (satu akun per email)
    # (Optional: Anda bisa mengambil nama email dari creds.id_token jika ingin)
    account = BlogspotAccount.query.first()
    if not account:
        account = BlogspotAccount()
        db.session.add(account)
    account.name = data["items"][0].get("name", "Google Account")
    account.access_token = creds.token
    account.refresh_token = creds.refresh_token
    db.session.commit()

    # Step 6: Simpan/update semua blog ke tabel BlogspotBlog
    for blog in data["items"]:
        existing = BlogspotBlog.query.filter_by(blog_id=blog["id"]).first()
        if not existing:
            new_blog = BlogspotBlog(
                blog_id=blog["id"],
                name=blog["name"],
                blogspot_account_id=account.id
            )
            db.session.add(new_blog)
        else:
            existing.name = blog["name"]
            existing.blogspot_account_id = account.id
    db.session.commit()

    flash("Berhasil terhubung dan sinkron semua blog Blogspot.")
    return redirect(url_for('routes.list_blogspot'))

@bp.route('/blogspot_post/new', methods=['GET', 'POST'])
@login_required
def new_blogspot_post():
    blogs = BlogspotBlog.query.all()
    if request.method == 'POST':
        blog_id = request.form['blogspot_blog_id']
        title = request.form['title']
        content = request.form['content']
        search_description = request.form['search_description']
        scheduled_time = datetime.strptime(request.form['scheduled_time'], '%Y-%m-%dT%H:%M')

        # --- AMBIL DAN PROSES LABEL DARI TAGIFY ---
        import json
        labels_raw = request.form.get('labels', '')  # bisa berupa '["Artikel","Flask"]' atau [{"value":"Artikel"}]
        labels = ''
        try:
            labels_data = json.loads(labels_raw)
            if isinstance(labels_data, list):
                # Format [{"value":"Artikel"}]
                if all(isinstance(x, dict) and "value" in x for x in labels_data):
                    labels = ','.join(x["value"] for x in labels_data)
                # Format ["Artikel", "Flask"]
                elif all(isinstance(x, str) for x in labels_data):
                    labels = ','.join(labels_data)
        except Exception:
            # Kalau input bukan JSON, simpan saja apa adanya (misal: "Artikel,Flask")
            labels = labels_raw

        # --- END PROSES LABEL ---

        post = Post(
            blogspot_blog_id=blog_id,
            title=title,
            content=content,
            labels=labels,
            search_description=search_description,
            scheduled_time=scheduled_time,
            status='pending'
        )
        db.session.add(post)
        db.session.commit()
        flash('Artikel berhasil dijadwalkan!')
        return redirect(url_for('routes.list_posts'))

    return render_template('blogspot_new_post.html', blogs=blogs)


@bp.route('/blogspot_labels/<int:dbid>')
@login_required
def blogspot_labels(dbid):
    blog = BlogspotBlog.query.get(dbid)
    if not blog:
        return jsonify([])
    account = BlogspotAccount.query.get(blog.blogspot_account_id)
    if not account:
        return jsonify([])

    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog.blog_id}/posts?maxResults=500"
    headers = {"Authorization": f"Bearer {account.access_token}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 401:
        # --- Otomatis refresh token ---
        # Load credential.json
        cred_path = os.path.join(os.path.dirname(__file__), "credentials", "credentials.json")
        with open(cred_path) as f:
            info = json.load(f)["installed"]
        payload = {
            "client_id": info["client_id"],
            "client_secret": info["client_secret"],
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token"
        }

        resp = requests.post("https://oauth2.googleapis.com/token", data=payload)
        if resp.ok and "access_token" in resp.json():
            account.access_token = resp.json()["access_token"]
            db.session.commit()
            headers["Authorization"] = f"Bearer {account.access_token}"
            r = requests.get(url, headers=headers)  # retry
        else:
            print("Gagal refresh token:", resp.text)
            return jsonify([])
    if not r.ok:
        print("Status code:", r.status_code)
        print("Response text:", r.text)
        return jsonify([])
    data = r.json()
    labels_set = set()
    for post in data.get("items", []):
        for label in post.get("labels", []):
            labels_set.add(label)
    labels = sorted(list(labels_set))
    # print("LABELS:", labels)
    return jsonify(labels)


@bp.route('/posts')
@login_required
def list_posts():
    # Ambil parameter filter dari query string
    q = request.args.get('q', '').strip()
    blog_id = request.args.get('blog_id', '')
    date = request.args.get('date', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))

    query = Post.query

    # Filter by title
    if q:
        query = query.filter(Post.title.ilike(f'%{q}%'))

    # Filter by website/blog
    if blog_id:
        query = query.filter(Post.blogspot_blog_id == int(blog_id))

    # Filter by date (YYYY-MM-DD)
    if date:
        try:
            from datetime import datetime, timedelta
            d1 = datetime.strptime(date, '%Y-%m-%d')
            d2 = d1 + timedelta(days=1)
            query = query.filter(Post.scheduled_time >= d1, Post.scheduled_time < d2)
        except Exception:
            pass

    query = query.order_by(Post.scheduled_time.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = pagination.items

    blogs = {b.id: b for b in BlogspotBlog.query.all()}

    return render_template(
        'posts_list.html',
        posts=posts,
        blogs=blogs,
        pagination=pagination,
        q=q,
        blog_id=blog_id,
        date=date,
        per_page=per_page
    )

@bp.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    blogs = BlogspotBlog.query.all()

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.search_description = request.form.get('search_description')
        # Parse labels dari Tagify, sama seperti new post
        import json
        labels_raw = request.form.get('labels', '')
        labels = ''
        try:
            labels_data = json.loads(labels_raw)
            if isinstance(labels_data, list):
                if all(isinstance(x, dict) and "value" in x for x in labels_data):
                    labels = ','.join(x["value"] for x in labels_data)
                elif all(isinstance(x, str) for x in labels_data):
                    labels = ','.join(labels_data)
        except Exception:
            labels = labels_raw
        post.labels = labels

        if request.form.get('scheduled_time'):
            post.scheduled_time = datetime.strptime(request.form['scheduled_time'], '%Y-%m-%dT%H:%M')
        db.session.commit()
        flash('Postingan berhasil diupdate.')
        return redirect(url_for('routes.list_posts'))

    # Prepopulate label ke Tagify (format list of string)
    labels = [lbl.strip() for lbl in post.labels.split(',') if lbl.strip()]
    return render_template('edit_post.html', post=post, blogs=blogs, labels=labels)


@bp.route('/posts/cancel/<int:post_id>')
@login_required
def cancel_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.status == 'pending':
        post.status = 'cancelled'
        db.session.commit()
        flash('Postingan dibatalkan.')
    return redirect(url_for('routes.list_posts'))

@bp.route('/posts/delete/<int:post_id>')
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Postingan dihapus.')
    return redirect(url_for('routes.list_posts'))

@bp.route('/post/<int:post_id>')
@login_required
def detail_post(post_id):
    post = Post.query.get_or_404(post_id)
    blog = BlogspotBlog.query.get(post.blogspot_blog_id)
    return render_template('detail_post.html', post=post, blog=blog)

@bp.route('/duplicate_post/<int:post_id>')
@login_required
def duplicate_post(post_id):
    post = Post.query.get_or_404(post_id)
    blogs = BlogspotBlog.query.all()

    # Siapkan data pre-filled, tidak simpan ke DB di sini
    labels = [lbl.strip() for lbl in post.labels.split(',') if lbl.strip()]
    # Render form new_post, isikan data post ke form
    return render_template(
        'blogspot_new_post.html',
        blogs=blogs,
        # Berikut untuk prefill form
        duplicate=True,
        prefill={
            "blogspot_blog_id": post.blogspot_blog_id,
            "title": f"{post.title} (Copy)",
            "content": post.content,
            "labels": labels,
            "search_description": post.search_description,
            "scheduled_time": post.scheduled_time.strftime('%Y-%m-%dT%H:%M') if post.scheduled_time else ""
        }
    )

@bp.route('/upload_image', methods=['POST'])
def upload_image():
    file = request.files['file']
    filename = secure_filename(file.filename)
    path = os.path.join('static', 'uploads', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    file_url = url_for('static', filename='uploads/' + filename)
    # TinyMCE expects: {"location" : "/url/to/file"}
    return jsonify({'location': file_url})

@bp.route('/generate_html_post', methods=['GET'])
@login_required
def generate_html_post():
    return render_template('generate_html_post.html')

# Route untuk generate deskripsi singkat
@bp.route('/generate-description', methods=['POST'])
@login_required
def generate_description():
    data = request.json
    generate = data.get('generate', '')

    if not generate:
        return jsonify({'error': 'Judul tidak boleh kosong'}), 400

    # Prompt untuk OpenAI API
    prompt = (
    f"buatkan deskripsi singkat, tidak duplicate content dan SEO-friendly dengan targeted keyword, "
    f"untuk artikel produk yang menjual produk kaos dengan judul "
    f"'{generate}'. Maksimal 2 kalimat."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # atau gpt-4 jika ada
            messages=[
                {"role": "system", "content": "Kamu adalah asisten deskripsi produk."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=70,
            temperature=0.8,
        )
        hasil = response['choices'][0]['message']['content'].strip()
        return jsonify({'deskripsi': hasil})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

