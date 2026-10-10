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

# Base path where all media libraries reside inside the container
MEDIA_BASE = os.environ.get("MEDIA_BASE", "/media/movies")
SOURCE_POOL = os.path.join(MEDIA_BASE, "all_downloads")

def sanitize_name(name: str) -> str:
    """Sanitize usernames or folder names to prevent directory traversal."""
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")).lower()

def create_hardlinks_recursive(src: str, dst: str):
    """Recursively creates directory structures and hardlinks files."""
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
        logging.warning("Received invalid or non-JSON payload.")
        return jsonify({"error": "Invalid JSON"}), 400

    # Jellyseerr sends 'MEDIA_AVAILABLE' notification type
    notification_type = data.get("notification_type")
    event = data.get("event")
    
    # Check for availability events
    if notification_type != "MEDIA_AVAILABLE" and event != "media_available":
        logging.info(f"Ignoring irrelevant event type: {notification_type or event}")
        return jsonify({"message": "Event ignored"}), 200

    # Extract user and media details
    request_user = data.get("request", {}).get("requestedBy_username")
    if not request_user:
        # Fallback to top-level fields depending on Jellyseerr webhook format
        request_user = data.get("requestedBy_username") or data.get("user", {}).get("username")

    if not request_user:
        logging.error("Could not determine requesting user from payload.")
        return jsonify({"error": "Missing user"}), 400

    user_clean = sanitize_name(request_user)
    target_user_dir = os.path.join(MEDIA_BASE, user_clean)

    # Extract title or folder path
    subject = data.get("subject") or data.get("media", {}).get("title")
    logging.info(f"Processing available media: '{subject}' for user: '{user_clean}'")

    # Locate media in the source pool
    if not os.path.exists(SOURCE_POOL):
        logging.error(f"Source pool directory does not exist: {SOURCE_POOL}")
        return jsonify({"error": "Source pool missing"}), 500

    # Match directory or file matching the title
    matched_entry = None
    for entry in os.listdir(SOURCE_POOL):
        if subject and subject.lower() in entry.lower():
            matched_entry = entry
            break

    if not matched_entry:
        logging.warning(f"No match found in {SOURCE_POOL} for '{subject}'. Scanning subfiles.")
        return jsonify({"warning": "No matching file found in pool"}), 404

    src_path = os.path.join(SOURCE_POOL, matched_entry)
    dst_path = os.path.join(target_user_dir, matched_entry)

    try:
        os.makedirs(target_user_dir, exist_ok=True)
        create_hardlinks_recursive(src_path, dst_path)
        logging.info(f"Successfully processed hardlinks for '{matched_entry}' to '{target_user_dir}'")
        return jsonify({"status": "success", "user": user_clean, "entry": matched_entry}), 200
    except OSError as e:
        logging.error(f"Filesystem error during link creation: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)