from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from .models import User, BlogspotAccount, FacebookAccount, InstagramAccount, BlogspotBlog, Post, Platform, Account, TodoTask,TodoTemplate
from . import db, login_manager
import os, requests, json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
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


@bp.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    blogs = BlogspotBlog.query.all()
    if request.method == 'POST':
        # ... ambil blog_id dari form
        blog_id = request.form['blogspot_blog_id']
        # ... save ke tabel Post dsb
    return render_template('form.html', blogs=blogs)

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

# List & Tambah Platform
@bp.route('/todo_platforms', methods=['GET', 'POST'])
@login_required
def todo_platforms():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if name:
            db.session.add(Platform(name=name))
            db.session.commit()
            flash('Platform berhasil ditambahkan.', 'success')
        return redirect(url_for('routes.todo_platforms'))
    platforms = Platform.query.all()
    return render_template('todo_platforms.html', platforms=platforms)

# Edit Platform
@bp.route('/todo_platform_edit/<int:id>', methods=['POST'])
@login_required
def todo_platform_edit(id):
    platform = Platform.query.get_or_404(id)
    name = request.form['name'].strip()
    if name:
        platform.name = name
        db.session.commit()
        flash('Platform diperbarui.', 'success')
    return redirect(url_for('routes.todo_platforms'))

# Hapus Platform
@bp.route('/todo_platform_delete/<int:id>', methods=['POST'])
@login_required
def todo_platform_delete(id):
    platform = Platform.query.get_or_404(id)
    db.session.delete(platform)
    db.session.commit()
    flash('Platform dihapus.', 'info')
    return redirect(url_for('routes.todo_platforms'))


@bp.route('/todo_accounts/<int:platform_id>', methods=['GET', 'POST'])
@login_required
def todo_accounts(platform_id):
    platform = Platform.query.get_or_404(platform_id)
    if request.method == 'POST':
        name = request.form['name'].strip()
        link = request.form.get('link', '').strip()
        if name:
            db.session.add(Account(platform_id=platform_id, name=name, link=link))
            db.session.commit()
            flash('Akun berhasil ditambahkan.', 'success')
        return redirect(url_for('routes.todo_accounts', platform_id=platform_id))
    accounts = Account.query.filter_by(platform_id=platform_id).all()
    return render_template('todo_accounts.html', platform=platform, accounts=accounts)


# Edit Account
@bp.route('/todo_account_edit/<int:id>', methods=['POST'])
@login_required
def todo_account_edit(id):
    account = Account.query.get_or_404(id)
    name = request.form['name'].strip()
    if name:
        account.name = name
        db.session.commit()
        flash('Akun diperbarui.', 'success')
    return redirect(url_for('routes.todo_accounts', platform_id=account.platform_id))

# Hapus Account
@bp.route('/todo_accounts/delete/<int:account_id>/<int:platform_id>', methods=['POST'])
@login_required
def todo_account_delete(account_id, platform_id):
    account = Account.query.get_or_404(account_id)
    db.session.delete(account)
    db.session.commit()
    flash('Akun dihapus.', 'info')
    return redirect(url_for('routes.todo_accounts', platform_id=platform_id))


@bp.route('/todo_tasks', methods=['GET', 'POST'])
@login_required
def todo_tasks():
    # Filter
    platform_id = request.args.get('platform_id', type=int)
    account_id = request.args.get('account_id', type=int)
    hari = request.args.get('date')  # Menghilangkan default hari ini
    status = request.args.get('status')
    priority = request.args.get('priority')
    search = request.args.get('search', '').strip()

    # Pagination settings (default 25 items per page)
    page_size = request.args.get('page_size', 25, type=int)
    page = request.args.get('page', 1, type=int)

    # Handle form submission (tambah tugas)
    if request.method == 'POST':
        account = Account.query.get(request.form['account_id'])
        title = request.form['title'].strip()
        note = request.form.get('note', '').strip()
        deadline = request.form.get('deadline')
        waktu = request.form.get('time')
        priority_ = request.form.get('priority')
        recurring = request.form.get('recurring')
        deadline = date.fromisoformat(deadline) if deadline else None
        time = None
        if waktu:  # "HH:MM"
            from datetime import time as dt_time
            h, m = map(int, waktu.split(":"))
            time = dt_time(h, m)
        if account and title:
            db.session.add(TodoTask(
                account_id=account.id,
                title=title,
                note=note,
                deadline=deadline,
                time=time,
                priority=priority_ or "sedang",
                recurring=recurring if recurring != 'none' else None
            ))
            db.session.commit()
            flash('Tugas berhasil ditambahkan.', 'success')
        return redirect(url_for('routes.todo_tasks', platform_id=platform_id, account_id=account_id, date=hari))

    # Query platform & akun
    platforms = Platform.query.all()
    accounts = Account.query.filter_by(platform_id=platform_id).all() if platform_id else []
    tasks_query = TodoTask.query

    if account_id:
        tasks_query = tasks_query.filter(TodoTask.account_id == account_id)
    elif platform_id:
        account_ids = [a.id for a in accounts]
        tasks_query = tasks_query.filter(TodoTask.account_id.in_(account_ids))
    if hari:
        tasks_query = tasks_query.filter(TodoTask.deadline == date.fromisoformat(hari))
    if status == "done":
        tasks_query = tasks_query.filter(TodoTask.is_done == True)
    elif status == "pending":
        tasks_query = tasks_query.filter(TodoTask.is_done == False)
    if priority:
        tasks_query = tasks_query.filter(TodoTask.priority == priority)
    if search:
        tasks_query = tasks_query.filter(TodoTask.title.ilike(f"%{search}%"))

    # Pagination
    tasks = tasks_query.order_by(TodoTask.deadline, TodoTask.time, TodoTask.priority.desc()).paginate(page=page, per_page=page_size, error_out=False)

    return render_template('todo_tasks.html', platforms=platforms, accounts=accounts, tasks=tasks,
                           platform_id=platform_id, account_id=account_id, hari=hari, status=status, priority=priority, search=search, page_size=page_size)


@bp.route('/todo_task_done/<int:task_id>', methods=['POST'])
@login_required
def todo_task_done(task_id):
    task = TodoTask.query.get_or_404(task_id)
    task.is_done = True
    db.session.commit()
    flash('Tugas sudah dichecklist.', 'success')
    return redirect(request.referrer or url_for('routes.todo_tasks'))

@bp.route('/todo_task_delete/<int:task_id>', methods=['POST'])
@login_required
def todo_task_delete(task_id):
    task = TodoTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Tugas dihapus.', 'info')
    return redirect(request.referrer or url_for('routes.todo_tasks'))

# Edit task
@bp.route('/todo_task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def todo_task_edit(task_id):
    task = TodoTask.query.get_or_404(task_id)
    platforms = Platform.query.all()
    if request.method == 'POST':
        task.account_id = request.form['account_id']
        task.title = request.form['title'].strip()
        task.note = request.form.get('note', '').strip()
        task.deadline = request.form.get('deadline') or None
        task.time = request.form.get('time') or None
        task.priority = request.form.get('priority')
        task.recurring = request.form.get('recurring') if request.form.get('recurring') != 'none' else None
        db.session.commit()
        flash('Tugas berhasil diupdate.', 'success')
        return redirect(url_for('routes.todo_tasks'))
    return render_template('todo_task_edit.html', task=task, platforms=platforms)

# Duplicate task (prefill form add)
@bp.route('/todo_task/duplicate/<int:task_id>', methods=['GET', 'POST'])
@login_required
def todo_task_duplicate(task_id):
    from datetime import date
    task = TodoTask.query.get_or_404(task_id)
    platforms = Platform.query.all()
    if request.method == 'POST':
        account_id = request.form['account_id']
        title = request.form['title'].strip()
        note = request.form.get('note', '').strip()
        deadline = request.form.get('deadline') or None
        waktu = request.form.get('time')
        priority = request.form.get('priority')
        recurring = request.form.get('recurring')
        # Convert deadline
        deadline = date.fromisoformat(deadline) if deadline else None
        time = None
        if waktu:
            from datetime import time as dt_time
            h, m = map(int, waktu.split(":"))
            time = dt_time(h, m)
        db.session.add(TodoTask(
            account_id=account_id,
            title=title,
            note=note,
            deadline=deadline,
            time=time,
            priority=priority or "sedang",
            recurring=recurring if recurring != 'none' else None
        ))
        db.session.commit()
        flash('Tugas baru hasil duplicate berhasil dibuat!', 'success')
        return redirect(url_for('routes.todo_tasks'))
    # Prefill: deadline default ke hari ini
    return render_template('todo_task_duplicate.html', task=task, platforms=platforms)

@bp.route('/todo_tasks/events')
@login_required
def todo_tasks_events():
    platform_id = request.args.get('platform_id', type=int)
    account_id = request.args.get('account_id', type=int)
    tasks_query = TodoTask.query
    if account_id:
        tasks_query = tasks_query.filter(TodoTask.account_id == account_id)
    elif platform_id:
        accounts = Account.query.filter_by(platform_id=platform_id).all()
        account_ids = [a.id for a in accounts]
        tasks_query = tasks_query.filter(TodoTask.account_id.in_(account_ids))
    tasks = tasks_query.all()
    events = []
    for t in tasks:
        # Badge color logic:
        if t.is_done:
            color = "#2ecc71"  # hijau, selesai
            textColor = "white"
        elif t.priority == "tinggi":
            color = "#e74c3c"  # merah
            textColor = "white"
        elif t.priority == "rendah":
            color = "#95a5a6"  # abu
            textColor = "white"
        else:
            color = "#f1c40f"  # kuning
            textColor = "black"
        events.append({
            "id": t.id,
            "title": t.title,
            "start": t.deadline.isoformat() + (f"T{t.time.strftime('%H:%M:%S')}" if t.time else ""),
            "color": color,
            "textColor": textColor,
            "extendedProps": {
                "note": t.note or "",
                "is_done": t.is_done,
                "platform": t.account.platform.name,
                "account": t.account.name,
            }
        })
    return jsonify(events)



@bp.route('/todo_tasks/calendar')
@login_required
def todo_tasks_calendar():
    templates = TodoTemplate.query.filter_by(add_to_calendar='yes').all()
    platforms = Platform.query.all()
    accounts = Account.query.all()
    return render_template('todo_tasks_calendar.html', platforms=platforms, accounts=accounts, templates=templates)


@bp.route('/todo_tasks/update_deadline', methods=['POST'])
@login_required
def todo_tasks_update_deadline():
    from dateutil import parser
    data = request.get_json()
    task = TodoTask.query.get_or_404(data['task_id'])
    dt = parser.isoparse(data['deadline'])
    task.deadline = dt.date()
    task.time = dt.time() if dt.time() else None
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/todo_tasks/add_from_calendar', methods=['POST'])
@login_required
def todo_tasks_add_from_calendar():
    from datetime import date, time as dt_time
    account_id = int(request.form['account_id'])
    title = request.form['title'].strip()
    note = request.form.get('note', '').strip()
    deadline = request.form.get('deadline')
    waktu = request.form.get('time')
    priority = request.form.get('priority')
    recurring = request.form.get('recurring')
    deadline = date.fromisoformat(deadline) if deadline else None
    t = None
    if waktu:
        h, m = map(int, waktu.split(":"))
        t = dt_time(h, m)
    db.session.add(TodoTask(
        account_id=account_id,
        title=title,
        note=note,
        deadline=deadline,
        time=t,
        priority=priority or "sedang",
        recurring=recurring if recurring != 'none' else None
    ))
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/todo_tasks/get/<int:task_id>')
@login_required
def todo_tasks_get(task_id):
    task = TodoTask.query.get_or_404(task_id)
    return jsonify({
        "id": task.id,
        "account_id": task.account_id,
        "title": task.title,
        "note": task.note,
        "deadline": task.deadline.isoformat() if task.deadline else "",
        "time": task.time.strftime("%H:%M") if task.time else "",
        "priority": task.priority or "sedang",
        "recurring": task.recurring or "none",
        "is_done": task.is_done
    })


@bp.route('/todo_tasks/update/<int:task_id>', methods=['POST'])
@login_required
def todo_tasks_update(task_id):
    from datetime import date, time as dt_time
    task = TodoTask.query.get_or_404(task_id)
    task.account_id = int(request.form['account_id'])
    task.title = request.form['title'].strip()
    task.note = request.form.get('note', '').strip()
    deadline = request.form.get('deadline')
    waktu = request.form.get('time')
    task.deadline = date.fromisoformat(deadline) if deadline else None
    task.time = dt_time(*map(int, waktu.split(":"))) if waktu else None
    task.priority = request.form.get('priority')
    task.recurring = request.form.get('recurring') if request.form.get('recurring') != 'none' else None
    task.is_done = bool(int(request.form.get('is_done', 0)))
    db.session.commit()
    return jsonify({"success": True})


@bp.route('/todo_tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def todo_tasks_delete(task_id):
    task = TodoTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/todo_tasks/update_status/<int:task_id>', methods=['POST'])
@login_required
def todo_tasks_update_status(task_id):
    task = TodoTask.query.get_or_404(task_id)
    status = request.json.get('is_done', False)
    task.is_done = status
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/todo_templates', methods=['GET', 'POST'])
@login_required
def todo_templates():
    if request.method == 'POST':
        day_of_week = request.form['day_of_week']
        task_title = request.form['task_title']
        task_description = request.form['task_description']
        priority = request.form['priority']
        platform_id = request.form['platform_id']
        account_id = request.form['account_id']

        new_template = TodoTemplate(
            day_of_week=day_of_week,
            task_title=task_title,
            task_description=task_description,
            priority=priority,
            platform_id=platform_id,
            account_id=account_id
        )
        db.session.add(new_template)
        db.session.commit()
        flash('Template tugas berhasil ditambahkan!', 'success')
        return redirect(url_for('routes.todo_templates'))

    templates = TodoTemplate.query.options(db.joinedload(TodoTemplate.platform), db.joinedload(TodoTemplate.account)).all()


    platforms = Platform.query.all()
    accounts = Account.query.all()  # Ambil semua akun
    return render_template('todo_templates.html', platforms=platforms, accounts=accounts, templates=templates)


@bp.route('/todo_templates/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_todo_template(id):
    template = TodoTemplate.query.get_or_404(id)

    if request.method == 'POST':
        template.day_of_week = request.form['day_of_week']
        template.task_title = request.form['task_title']
        template.task_description = request.form['task_description']
        template.priority = request.form['priority']
        template.platform_id = request.form['platform_id']
        template.account_id = request.form['account_id']
        template.add_to_calendar = request.form['add_to_calendar']  # Menyimpan pilihan radio button

        db.session.commit()
        flash('Template tugas berhasil diperbarui!', 'success')
        return redirect(url_for('routes.todo_templates'))

    platforms = Platform.query.all()
    accounts = Account.query.all()

    return render_template('edit_todo_template.html', template=template, platforms=platforms, accounts=accounts)


@bp.route('/todo_templates/delete/<int:id>', methods=['POST'])
@login_required
def delete_todo_template(id):
    template = TodoTemplate.query.get_or_404(id)
    db.session.delete(template)
    db.session.commit()
    flash('Template tugas berhasil dihapus!', 'danger')
    return redirect(url_for('routes.todo_templates'))


def add_weekly_template():
    today = datetime.today()
    if today.weekday() == 5:  # 5 = Sabtu
        templates = TodoTemplate.query.all()

        for template in templates:
            task_date = today + timedelta(days=(7 - today.weekday()))  # Set tanggal mulai hari minggu depan
            db.session.add(TodoTask(
                account_id=template.account_id,
                title=template.task_title,
                note=template.task_description,
                deadline=task_date,
                priority=template.priority,
                recurring="weekly"
            ))

        db.session.commit()

def add_to_calendar_task():
    today = datetime.today()
    if today.weekday() == 5:  # 5 = Sabtu, setiap minggu
        templates = TodoTemplate.query.filter_by(add_to_calendar='yes').all()

        for template in templates:
            # Menambahkan tugas ke kalender untuk minggu depan
            task_date = today + timedelta(days=(7 - today.weekday()))  # Hari Minggu depan
            db.session.add(TodoTask(
                account_id=template.account_id,
                title=template.task_title,
                note=template.task_description,
                deadline=task_date,
                priority=template.priority,
                recurring="weekly"
            ))
        db.session.commit()

# Menjalankan scheduler setiap Sabtu untuk menambahkan tugas ke kalender
scheduler = BackgroundScheduler()
scheduler.add_job(func=add_to_calendar_task, trigger='cron', day_of_week='sat', hour=0, minute=0)
scheduler.start()
