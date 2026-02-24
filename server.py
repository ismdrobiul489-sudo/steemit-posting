"""
Steemit Posting API Server
===========================
Lightweight Flask API server for posting to Steemit
via n8n or any HTTP client.

Usage:
    python server.py          # Development
    gunicorn server:app        # Production (Docker)
"""

import os
import re
import uuid
import time
import logging
from functools import wraps

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from beem import Steem
from beem.exceptions import AccountDoesNotExistsException

# ─── Config ───────────────────────────────────────────────────────
load_dotenv()

STEEM_POSTING_KEY = os.getenv("STEEM_POSTING_KEY")
STEEM_AUTHOR = os.getenv("STEEM_AUTHOR")
PORT = int(os.getenv("PORT", 5000))

# Steem API nodes with fallback
STEEM_NODES = [
    "https://api.steemit.com",
    "https://api.steemyy.com",
    "https://api.justyy.com",
    "https://steem.justyy.com",
]

# ─── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ─── Flask App ────────────────────────────────────────────────────
app = Flask(__name__)


# ─── Helpers ──────────────────────────────────────────────────────

def generate_permlink(title: str) -> str:
    """
    Generate a unique permlink from the post title.
    Handles Unicode/non-Latin titles gracefully.
    Steem permlink: max 256 chars, lowercase, alphanumeric + hyphens
    """
    # Keep only alphanumeric and hyphens
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
    slug = re.sub(r'[\s]+', '-', slug).strip('-')

    # If empty (e.g. non-Latin title), use a default slug
    if not slug:
        slug = "post"

    # Make unique: timestamp + short UUID
    timestamp = int(time.time())
    short_id = uuid.uuid4().hex[:6]

    permlink = f"{slug}-{timestamp}-{short_id}"

    # Steem permlink max 256 characters
    if len(permlink) > 256:
        permlink = permlink[:256]

    return permlink


def require_api_key(f):
    """API Key authentication — uses STEEM_POSTING_KEY as the API key"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not STEEM_POSTING_KEY:
            return jsonify({
                "success": False,
                "error": "Server not configured — STEEM_POSTING_KEY missing"
            }), 500

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != STEEM_POSTING_KEY:
            logger.warning("Unauthorized request — invalid API key")
            return jsonify({
                "success": False,
                "error": "Unauthorized — invalid API key"
            }), 401

        return f(*args, **kwargs)
    return decorated


def get_steem_instance():
    """Create a Steem instance with specified nodes."""
    if not STEEM_POSTING_KEY:
        raise ValueError("STEEM_POSTING_KEY is not set in .env")
    if not STEEM_AUTHOR:
        raise ValueError("STEEM_AUTHOR is not set in .env")

    return Steem(
        node=STEEM_NODES,
        keys=[STEEM_POSTING_KEY],
        num_retries=3,
        num_retries_call=3,
        timeout=30
    )


# ─── Routes ───────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Server health check"""
    return jsonify({
        "status": "ok",
        "author": STEEM_AUTHOR or "NOT SET",
        "key_configured": bool(STEEM_POSTING_KEY)
    })


@app.route("/post", methods=["POST"])
@require_api_key
def create_post():
    """
    Create a new post on Steemit.

    Request JSON:
    {
        "title": "Post title",
        "body": "Post content (Markdown supported)",
        "tags": ["tag1", "tag2"],       // optional, default: ["steemit"]
        "community": "hive-000000",     // optional
        "self_vote": false,             // optional, default: false
        "beneficiaries": [              // optional
            {"account": "user1", "weight": 5000}
        ]
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "JSON body required"
        }), 400

    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    tags = data.get("tags", ["steemit"])
    community = data.get("community", None)
    self_vote = data.get("self_vote", False)
    beneficiaries = data.get("beneficiaries", None)

    # ─── Validation ───
    if not title:
        return jsonify({
            "success": False,
            "error": "title is required"
        }), 400

    if not body:
        return jsonify({
            "success": False,
            "error": "body is required"
        }), 400

    if not isinstance(tags, list) or len(tags) == 0:
        tags = ["steemit"]

    # Clean tags — lowercase, no spaces, max 5 tags (Steem limit)
    tags = [re.sub(r'[^a-z0-9-]', '', t.lower()) for t in tags]
    tags = [t for t in tags if t]  # Remove empty tags
    if not tags:
        tags = ["steemit"]
    tags = tags[:5]  # Steem allows max 5 tags

    # ─── Permlink ───
    permlink = generate_permlink(title)

    # ─── json_metadata ───
    json_metadata = {
        "tags": tags,
        "app": "steemit-api/1.0",
        "format": "markdown",
    }

    # ─── Post to Steemit ───
    try:
        steem = get_steem_instance()

        logger.info(f"Posting: '{title}' by @{STEEM_AUTHOR}")
        logger.info(f"Permlink: {permlink}")
        logger.info(f"Tags: {tags}")

        post_params = {
            "title": title,
            "body": body,
            "author": STEEM_AUTHOR,
            "tags": tags,
            "permlink": permlink,
            "json_metadata": json_metadata,
            "parse_body": True,   # Auto-extract images/links/users from body into metadata
            "self_vote": bool(self_vote),
        }

        # Community support
        if community:
            post_params["community"] = community
            logger.info(f"Community: {community}")

        # Beneficiaries support
        if beneficiaries and isinstance(beneficiaries, list):
            post_params["beneficiaries"] = beneficiaries
            logger.info(f"Beneficiaries: {beneficiaries}")

        steem.post(**post_params)

        post_url = f"https://steemit.com/@{STEEM_AUTHOR}/{permlink}"
        logger.info(f"✅ Success! Post URL: {post_url}")

        return jsonify({
            "success": True,
            "author": STEEM_AUTHOR,
            "permlink": permlink,
            "url": post_url,
            "tags": tags
        }), 201

    except AccountDoesNotExistsException:
        logger.error(f"Account @{STEEM_AUTHOR} does not exist")
        return jsonify({
            "success": False,
            "error": f"Account @{STEEM_AUTHOR} does not exist on Steemit"
        }), 400

    except Exception as e:
        logger.error(f"❌ Posting failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ─── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 Steemit Posting API Server")
    logger.info(f"   Author: @{STEEM_AUTHOR or 'NOT SET'}")
    logger.info(f"   Port: {PORT}")
    logger.info(f"   Key: {'✅ Set' if STEEM_POSTING_KEY else '❌ Not set'}")
    logger.info(f"   Nodes: {len(STEEM_NODES)} configured")
    logger.info("=" * 50)

    app.run(host="0.0.0.0", port=PORT, debug=False)
