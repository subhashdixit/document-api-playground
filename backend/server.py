"""Protected single-owner MongoDB demonstration API; no embedded credentials."""

import hmac
import json
import math
import os
import re
from threading import Lock
import uuid

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

FORBIDDEN = {"__proto__", "constructor", "prototype", "_id"}


def document_value(value):
    """Validate a deliberately constrained, bounded plain-JSON document."""
    if not isinstance(value, dict):
        raise ValueError("Document must be a JSON object.")
    count = 0

    def walk(item, depth=0):
        nonlocal count
        count += 1
        if depth > 10 or count > 2000:
            raise ValueError("Document is too complex.")
        if item is None or isinstance(item, (str, bool)):
            return
        if isinstance(item, (int, float)):
            if not math.isfinite(item):
                raise ValueError("Use finite JSON numbers.")
            return
        if isinstance(item, list):
            for child in item:
                walk(child, depth + 1)
            return
        if not isinstance(item, dict):
            raise ValueError("Unsupported JSON value.")
        for key, child in item.items():
            if key in FORBIDDEN or key.startswith("$") or "." in key or len(key) > 120:
                raise ValueError("Unsupported document key.")
            walk(child, depth + 1)

    walk(value)
    if len(json.dumps(value, ensure_ascii=False)) > 30000:
        raise ValueError("Document exceeds 30,000 characters.")
    return value


class MongoStore:
    """Use exact application UUIDs; never accept a client-supplied query filter."""

    def __init__(self, uri, database, collection):
        from pymongo import MongoClient  # pylint: disable=import-outside-toplevel

        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.collection = self.client[database][collection]

    def ready(self):
        """Verify the configured MongoDB server is reachable."""
        self.client.admin.command("ping")

    def list(self):
        """Return bounded records in the frontend contract."""
        return [
            {"id": row["_id"], "document": row["document"]}
            for row in self.collection.find({}, {"document": 1}).limit(500)
        ]

    def create(self, identifier, document):
        """Create in the dedicated collection after checking its demo capacity."""
        if self.collection.count_documents({}) >= 500:
            raise ValueError("Collection demo limit reached (500 documents).")
        self.collection.insert_one({"_id": identifier, "document": document})

    def update(self, identifier, document):
        """Replace the selected record's content and report existence."""
        return bool(
            self.collection.update_one(
                {"_id": identifier}, {"$set": {"document": document}}
            ).matched_count
        )

    def delete(self, identifier):
        """Delete only the exact selected UUID."""
        return bool(self.collection.delete_one({"_id": identifier}).deleted_count)


def create_app(config=None, store=None):
    """Create an owner-token-protected API; fail closed when unconfigured."""
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=64000,
        API_ADMIN_TOKEN=os.environ.get("API_ADMIN_TOKEN", ""),
        MONGODB_URI=os.environ.get("MONGODB_URI", ""),
        MONGODB_DATABASE=os.environ.get("MONGODB_DATABASE", "portfolio_demo"),
        MONGODB_COLLECTION=os.environ.get("MONGODB_COLLECTION", "documents"),
        ALLOWED_ORIGIN=os.environ.get(
            "ALLOWED_ORIGIN", "https://subhashdixit.github.io"
        ),
    )
    app.config.update(config or {})
    if store is None and app.config["MONGODB_URI"]:
        store = MongoStore(
            app.config["MONGODB_URI"],
            app.config["MONGODB_DATABASE"],
            app.config["MONGODB_COLLECTION"],
        )
    app.extensions["document_store"] = store
    lock = Lock()

    @app.before_request
    def authorize():
        origin = request.headers.get("Origin")
        if origin and origin != app.config["ALLOWED_ORIGIN"]:
            return jsonify(error="Origin not allowed."), 403
        if request.method == "OPTIONS":
            return "", 204
        if request.path.startswith("/api/"):
            token = app.config["API_ADMIN_TOKEN"]
            if len(token) < 32 or store is None:
                return jsonify(error="Backend credentials/storage not configured."), 503
            supplied = request.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + token):
                return jsonify(error="A valid owner access token is required."), 401
        return None

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.headers.get("Origin") == app.config["ALLOWED_ORIGIN"]:
            response.headers["Access-Control-Allow-Origin"] = app.config[
                "ALLOWED_ORIGIN"
            ]
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/health/ready")
    def ready():
        configured = bool(
            store is not None and len(app.config["API_ADMIN_TOKEN"]) >= 32
        )
        if configured:
            store.ready()
        return jsonify(status="ready", mongo_configured=configured)

    @app.route("/api/documents", methods=["GET", "POST", "OPTIONS"])
    def documents():
        if request.method == "GET":
            return jsonify(documents=store.list())
        payload = request.get_json(silent=True)
        document = document_value(
            payload.get("document") if isinstance(payload, dict) else None
        )
        identifier = str(uuid.uuid4())
        with lock:
            store.create(identifier, document)
        return jsonify(id=identifier, document=document), 201

    @app.route("/api/documents/<identifier>", methods=["PUT", "DELETE", "OPTIONS"])
    def selected(identifier):
        if not re.fullmatch(r"[a-f0-9-]{36}", identifier):
            raise ValueError("Invalid application UUID.")
        if request.method == "DELETE":
            exists = store.delete(identifier)
        else:
            payload = request.get_json(silent=True)
            value = document_value(
                payload.get("document") if isinstance(payload, dict) else None
            )
            exists = store.update(identifier, value)
        if not exists:
            return jsonify(error="Document not found."), 404
        return jsonify(id=identifier, saved=True)

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def failed(_error):
        return (
            jsonify(error="Backend unavailable; review its server configuration."),
            503,
        )

    return app
