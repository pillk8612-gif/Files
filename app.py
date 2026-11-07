import os
import random
import string
import secrets
from datetime import datetime, timedelta

from flask import (
    Flask, request, redirect, url_for,
    render_template, send_from_directory, abort, flash
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # для flash-сообщений

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Хранилище кодов: code -> {filename, original_name, created_at}
# В проде это должна быть БД (SQLite/Postgres) и/или Redis.
CODES = {}

# Время жизни кода/файла
TTL = timedelta(hours=24)

# Ограничение размера файла: 100 МБ
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024


def generate_code() -> str:
    """Генерирует уникальный 16-значный цифровой код."""
    while True:
        code = "".join(random.choices(string.digits, k=16))
        if code not in CODES:
            return code


def cleanup_expired():
    """Удаляет истёкшие коды и файлы."""
    now = datetime.utcnow()
    expired = [c for c, m in CODES.items() if now - m["created_at"] > TTL]
    for code in expired:
        meta = CODES.pop(code, None)
        if meta:
            path = os.path.join(UPLOAD_DIR, meta["stored_name"])
            if os.path.exists(path):
                os.remove(path)


@app.route("/", methods=["GET", "POST"])
def index():
    cleanup_expired()

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Выберите файл")
            return redirect(url_for("index"))

        code = generate_code()
        stored_name = f"{code}_{secrets.token_hex(8)}"
        save_path = os.path.join(UPLOAD_DIR, stored_name)
        file.save(save_path)

        CODES[code] = {
            "stored_name": stored_name,
            "original_name": file.filename,
            "created_at": datetime.utcnow(),
        }

        return render_template("index.html", new_code=code)

    return render_template("index.html")


@app.route("/d/<code>", methods=["GET"])
def download_page(code):
    cleanup_expired()
    meta = CODES.get(code)
    return render_template(
        "download.html",
        code=code,
        found=bool(meta),
        filename=meta["original_name"] if meta else None,
    )


@app.route("/d/<code>/file", methods=["GET"])
def download_file(code):
    cleanup_expired()
    meta = CODES.get(code)
    if not meta:
        abort(404)
    return send_from_directory(
        UPLOAD_DIR,
        meta["stored_name"],
        as_attachment=True,
        download_name=meta["original_name"],
    )


@app.route("/check", methods=["POST"])
def check_code():
    code = request.form.get("code", "").strip()
    if len(code) != 16 or not code.isdigit():
        flash("Код должен состоять из 16 цифр")
        return redirect(url_for("index"))
    return redirect(url_for("download_page", code=code))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)