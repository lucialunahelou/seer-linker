import os
import sys
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

MOVIES_BASE = os.environ.get("MOVIES_BASE", "/data/media/video/movies")
TV_BASE = os.environ.get("TV_BASE", "/data/media/video/tv_shows")

def sanitize_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")).lower()

def create_hardlinks_recursive(src: str, dst: str):
    if os.path.isfile(src):
        if not os.path.exists(dst):
            os.link(src, dst)
            logging.info(f"Hardlinked file: {src} -> {dst}")
        return

    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for item in os.listdir(src):
            s_item = os.path.join(src, item)
            d_item = os.path.join(dst, item)
            create_hardlinks_recursive(s_item, d_item)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    notification_type = data.get("notification_type")
    event = data.get("event")
    
    if notification_type != "MEDIA_AVAILABLE" and event != "media_available":
        return jsonify({"message": "Event ignored"}), 200

    request_user = data.get("request", {}).get("requestedBy_username") or data.get("requestedBy_username") or data.get("user", {}).get("username")
    if not request_user:
        return jsonify({"error": "Missing user"}), 400

    media_type = data.get("media", {}).get("media_type", "movie").lower()
    
    if media_type == "tv":
        base_dir = TV_BASE
    else:
        base_dir = MOVIES_BASE

    source_pool = os.path.join(base_dir, "all_downloads")
    user_clean = sanitize_name(request_user)
    target_user_dir = os.path.join(base_dir, user_clean)
    subject = data.get("subject") or data.get("media", {}).get("title")

    if not os.path.exists(source_pool):
        return jsonify({"error": f"Source pool missing: {source_pool}"}), 500

    matched_entry = None
    for entry in os.listdir(source_pool):
        if subject and subject.lower() in entry.lower():
            matched_entry = entry
            break

    if not matched_entry:
        return jsonify({"warning": "No matching file found in pool"}), 404

    src_path = os.path.join(source_pool, matched_entry)
    dst_path = os.path.join(target_user_dir, matched_entry)

    try:
        os.makedirs(target_user_dir, exist_ok=True)
        create_hardlinks_recursive(src_path, dst_path)
        return jsonify({"status": "success", "user": user_clean, "entry": matched_entry}), 200
    except OSError as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)