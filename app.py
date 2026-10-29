from flask import Flask, jsonify, request, Response
import os
import time
from itertools import count
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# In-memory store for the demo "items" resource. This resets on every
# restart — fine for demonstrating CRUD patterns, not meant for real data.
_items = {}
_id_counter = count(1)

# --- Prometheus metrics ---------------------------------------------------
# Standard RED-method metrics: Rate (via the counter), Errors (via status
# label), Duration (via the histogram). This is the same pattern used to
# monitor real production services.
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)


@app.before_request
def _start_timer():
    request._start_time = time.time()


@app.after_request
def _record_metrics(response):
    # /metrics itself is excluded so Prometheus scraping it doesn't
    # pollute its own metrics.
    if request.path != '/metrics':
        endpoint = request.endpoint or 'unknown'
        duration = time.time() - getattr(request, '_start_time', time.time())
        REQUEST_LATENCY.labels(request.method, endpoint).observe(duration)
        REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    return response


@app.after_request
def _set_security_headers(response):
    # Security headers added to every response (including errors), so the
    # OWASP ZAP baseline scan in CI can verify them as a gate.
    # Stop browsers from guessing content types (ZAP rule 10021)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Block other origins from loading this API's responses (ZAP rule 90004)
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    # Do not let shared caches keep responses (ZAP rule 10049)
    response.headers['Cache-Control'] = 'no-store'
    # Defense in depth for an API that never serves HTML (rules 10020, 10038, 10063)
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=()'
    return response


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route('/')
def home():
    return jsonify({"message": "Welcome to the DevOps CI/CD Demo App"}), 200


@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200


@app.route('/config-status')
def config_status():
    """
    Demonstrates safe handling of secrets: confirms whether a required
    secret is configured WITHOUT ever exposing its value in a response,
    log, or error message.
    """
    api_key_configured = bool(os.environ.get('API_KEY'))
    return jsonify({
        "api_key_configured": api_key_configured
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


@app.route('/items', methods=['GET'])
def list_items():
    return jsonify(list(_items.values())), 200


@app.route('/items', methods=['POST'])
def create_item():
    data = request.get_json(silent=True)

    if not data or not isinstance(data.get('name'), str) or not data['name'].strip():
        return jsonify({"error": "'name' is required and must be a non-empty string"}), 400

    item_id = next(_id_counter)
    item = {"id": item_id, "name": data['name'].strip()}
    _items[item_id] = item

    return jsonify(item), 201


@app.route('/items/<int:item_id>', methods=['GET'])
def get_item(item_id):
    item = _items.get(item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(item), 200


@app.route('/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    if item_id not in _items:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data.get('name'), str) or not data['name'].strip():
        return jsonify({"error": "'name' is required and must be a non-empty string"}), 400

    _items[item_id]['name'] = data['name'].strip()
    return jsonify(_items[item_id]), 200


@app.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    if item_id not in _items:
        return jsonify({"error": "Item not found"}), 404

    del _items[item_id]
    return '', 204


if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)  # nosec B104 - intentional: must bind all interfaces inside Docker container for port mapping to work
