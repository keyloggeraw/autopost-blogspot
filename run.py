from app import create_app, db
from app.models import User
import os
from apscheduler.schedulers.background import BackgroundScheduler

app = create_app()

# Buat admin user default jika belum ada
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin', full_name='Administrator', image_filename='uploads/default_avatar.png')
        db.session.add(admin)
        db.session.commit()


def start_scheduler(app):
    from app.tasks import run_blogspot_scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: run_blogspot_scheduler(app), trigger='interval', seconds=30)
    scheduler.start()

    # Agar scheduler mati kalau Flask dimatikan
    import atexit
    atexit.register(lambda: scheduler.shutdown())

# Setelah mendaftarkan blueprint
start_scheduler(app)

#digunakan jika tidak ada run.py
if __name__ == '__main__':
    app.run(debug=True)

# digunakan untuk convert ke exe
# def run_flask():
#     app.run(debug=False, use_reloader=False, port=5000)

# if __name__ == '__main__':
#     run_flask()

