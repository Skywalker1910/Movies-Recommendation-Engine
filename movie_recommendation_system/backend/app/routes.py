from flask import Blueprint, jsonify, request
from .recommender import get_collaborative_recommendations, get_content_recommendations, search_movies

# Create a blueprint for routes
app = Blueprint('app', __name__)

# Collaborative Recommendations Endpoint
@app.route('/recommendations/collaborative/<int:user_id>', methods=['GET'])
def get_collaborative_recommendations_route(user_id):
    recommendations = get_collaborative_recommendations(user_id)
    if recommendations:
        return jsonify(recommendations), 200
    else:
        return jsonify({"error": "No recommendations found"}), 404

# Content-Based Recommendations Endpoint
@app.route('/recommendations/content/<int:movie_id>', methods=['GET'])
def get_content_recommendations_route(movie_id):
    recommendations = get_content_recommendations(movie_id)
    if recommendations:
        return jsonify(recommendations), 200
    else:
        return jsonify({"error": "No recommendations found"}), 404

# Movie Search Endpoint
@app.route('/movies/search', methods=['GET'])
def search_movies_route():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([]), 200
    results = search_movies(query)
    return jsonify(results), 200
