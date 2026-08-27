from flask import Flask, jsonify, request
import os
from itertools import count

app = Flask(__name__)

# In-memory store for the demo "items" resource. This resets on every
# restart — fine for demonstrating CRUD patterns, not meant for real data.
_items = {}
_id_counter = count(1)


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
