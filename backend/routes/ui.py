"""
backend/routes/ui.py
---------------------
Serves the kiosk frontend HTML page.
"""

from flask import Blueprint, render_template

ui_bp = Blueprint("ui", __name__)


@ui_bp.route("/")
def index():
    return render_template("index.html")


@ui_bp.route("/nexus")
def nexus_clone():
    """Serves the Nexus Bank landing page clone."""
    return render_template("nexus.html")


@ui_bp.route("/widget")
def widget():
    """Serves the minimalist chatbot widget (used by iframe)."""
    return render_template("widget.html")
