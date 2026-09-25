from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import os

from .preprocess import load_datasets

movies_df, ratings_df = load_datasets()

# Build MovieLens movieId -> title mapping via links_small.csv
_current_dir = os.path.dirname(os.path.abspath(__file__))
_links_path = os.path.join(_current_dir, '../data/movies-dataset/links_small.csv')
_links_df = pd.read_csv(_links_path)
_links_df['tmdbId'] = pd.to_numeric(_links_df['tmdbId'], errors='coerce')
_links_df.dropna(subset=['tmdbId'], inplace=True)
_links_df['tmdbId'] = _links_df['tmdbId'].astype(int)
_id_map = _links_df.merge(movies_df[['id', 'title']], left_on='tmdbId', right_on='id', how='left')
movie_id_to_title = dict(zip(_id_map['movieId'], _id_map['title']))

# Prepare collaborative filtering matrix
def prepare_user_item_matrix(ratings_df):
    user_movie_matrix = ratings_df.pivot_table(index='userId', columns='movieId', values='rating').fillna(0)
    return user_movie_matrix

user_movie_matrix = prepare_user_item_matrix(ratings_df)

# Create content profile matrix using TF-IDF
tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(movies_df['content_profile'])

# Collaborative Filtering Recommendations
def get_collaborative_recommendations(user_id, num_recommendations=5):
    if user_id not in user_movie_matrix.index:
        return []
    user_similarity = cosine_similarity(user_movie_matrix)
    user_similarity_df = pd.DataFrame(user_similarity, index=user_movie_matrix.index, columns=user_movie_matrix.index)
    similar_users = user_similarity_df[user_id].sort_values(ascending=False).index.tolist()
    recommended_movies = user_movie_matrix.loc[similar_users[1:num_recommendations + 1]].mean(axis=0)
    recommended_movies = recommended_movies.sort_values(ascending=False).head(num_recommendations)
    return [
        {
            'movie_id': int(idx),
            'title': movie_id_to_title.get(int(idx), f'Movie #{idx}'),
            'predicted_rating': round(float(rating), 2)
        }
        for idx, rating in recommended_movies.items()
    ]

# Content-Based Recommendations
def get_content_recommendations(movie_id, num_recommendations=5):
    matches = movies_df[movies_df['id'] == movie_id]
    if matches.empty:
        return []
    idx = matches.index[0]
    sim_scores = list(enumerate(cosine_similarity(tfidf_matrix[idx], tfidf_matrix)[0]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[1:num_recommendations + 1]
    movie_indices = [i[0] for i in sim_scores]
    return movies_df.iloc[movie_indices][['id', 'title']].to_dict(orient='records')

# Movie Search
def search_movies(query, limit=10):
    mask = movies_df['title'].str.contains(query, case=False, na=False)
    results = movies_df[mask][['id', 'title']].head(limit)
    return results.to_dict(orient='records')
