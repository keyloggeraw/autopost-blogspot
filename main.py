import threading
import time
import webview
import run  # pastikan run.py sudah tidak menjalankan app.run() langsung

def start_flask():
    run.run_flask()

if __name__ == '__main__':
    print("🚀 Menjalankan Flask di background...")
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Tunggu sebentar agar server Flask siap
    time.sleep(2)

    print("🪟 Menjalankan GUI PyWebview...")
    window = webview.create_window(
        "Aplikasi AutoPost",
        "http://127.0.0.1:5000",
        width=1000,
        height=700
    )

    webview.start(gui='edgechromium')
