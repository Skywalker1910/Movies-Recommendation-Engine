import pandas as pd
import os
import ast

def load_datasets():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(current_dir, "../data/movies-dataset")

    # Load datasets
    movies_df = pd.read_csv(os.path.join(dataset_dir, "movies_metadata.csv"), low_memory=False)
    ratings_df = pd.read_csv(os.path.join(dataset_dir, "ratings_small.csv"))
    keywords_df = pd.read_csv(os.path.join(dataset_dir, "keywords.csv"))

    # Clean movies dataset
    movies_df.drop(columns=['homepage', 'imdb_id', 'poster_path', 'status', 'spoken_languages'], inplace=True, errors='ignore')
    movies_df.dropna(subset=['title', 'genres'], inplace=True)
    movies_df['release_date'] = pd.to_datetime(movies_df['release_date'], errors='coerce')
    movies_df['genres'] = movies_df['genres'].apply(lambda x: [g['name'] for g in ast.literal_eval(x)] if pd.notna(x) else [])

    # Convert the 'id' column in movies_df to numeric and drop any invalid entries
    movies_df['id'] = pd.to_numeric(movies_df['id'], errors='coerce')
    movies_df.dropna(subset=['id'], inplace=True)
    movies_df['id'] = movies_df['id'].astype(int)

    # Clean ratings dataset
    ratings_df.dropna(subset=['userId', 'movieId', 'rating'], inplace=True)
    ratings_df['userId'] = ratings_df['userId'].astype(int)
    ratings_df['movieId'] = ratings_df['movieId'].astype(int)

    # Convert 'id' in keywords_df to int to match movies_df
    keywords_df['id'] = keywords_df['id'].astype(int)

    # Parse keywords JSON strings into lists of keyword names
    keywords_df['keywords'] = keywords_df['keywords'].apply(
        lambda x: [k['name'] for k in ast.literal_eval(x)] if pd.notna(x) and x != '' else []
    )

    # Merge keywords into movies dataset
    movies_df = movies_df.merge(keywords_df, how='left', left_on='id', right_on='id')

    # Create content profile
    movies_df['content_profile'] = movies_df['overview'].fillna('') + ' ' + movies_df['genres'].apply(lambda x: ' '.join(x)) + ' ' + movies_df['keywords'].apply(lambda x: ' '.join(x) if isinstance(x, list) else '')
    movies_df.dropna(subset=['content_profile'], inplace=True)

    return movies_df, ratings_df

# Load the cleaned datasets
movies_df, ratings_df = load_datasets()
