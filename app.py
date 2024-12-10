import os
from flask import Flask, render_template, request, redirect, url_for
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from collections import defaultdict
import plotly.graph_objects as go
import base64
import io

# Load environment variables
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Initialize Flask app
app = Flask(__name__)

# Spotify authentication
sp = Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="user-top-read user-library-read playlist-modify-public"
))

# Function to estimate times played based on Spotify popularity
def calculate_times_played(popularity):
    base_plays = 200
    multiplier = 10
    return base_plays + (popularity * multiplier)

# Function to generate a graph for top genres
def generate_genre_plot(genre_counts):
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    genres = [genre for genre, count in sorted_genres]
    counts = [count for genre, count in sorted_genres]

    fig = go.Figure(
        data=[
            go.Bar(
                x=genres,
                y=counts,
                marker_color="#1db954",
            )
        ]
    )
    fig.update_layout(
        title="Top 10 Genres by Track Count",
        xaxis_title="Genres",
        yaxis_title="Number of Tracks",
        font=dict(family="Arial, sans-serif", size=14, color="#e0e0e0"),
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
    )
    buf = io.BytesIO()
    fig.write_image(buf, format="png")
    buf.seek(0)
    graph_data = base64.b64encode(buf.getvalue()).decode("utf-8")
    buf.close()
    return graph_data

# Route: Home page with a graph of genres
@app.route('/')
def home():
    top_tracks = sp.current_user_top_tracks(limit=50)['items']
    genre_counts = defaultdict(int)

    for track in top_tracks:
        artist_id = track['artists'][0]['id']
        artist_info = sp.artist(artist_id)
        genres = artist_info.get('genres', ['Unknown'])
        for genre in genres:
            genre_counts[genre] += 1

    genre_plot = generate_genre_plot(genre_counts)
    return render_template('home.html', genre_plot=genre_plot)

# Route: Display top 5 genres
@app.route('/genres')
def genres():
    top_tracks = sp.current_user_top_tracks(limit=50)['items']
    genre_to_tracks = defaultdict(list)
    seen_tracks = set()

    for track in top_tracks:
        track_name = track['name']
        artist = track['artists'][0]
        artist_id = artist['id']
        artist_name = artist['name']
        popularity = track['popularity']
        times_played = calculate_times_played(popularity)
        track_uri = track['uri']
        album_images = track['album']['images'] if track['album']['images'] else []

        # Avoid duplicate tracks in genres
        if track_name in seen_tracks:
            continue
        seen_tracks.add(track_name)

        artist_info = sp.artist(artist_id)
        genres = artist_info.get('genres', ['Unknown'])
        for genre in genres:
            genre_to_tracks[genre].append({
                'name': track_name,
                'artist': artist_name,
                'popularity': popularity,
                'times_played': times_played,
                'spotify_uri': track_uri,
                'album_images': album_images
            })

    sorted_genres = sorted(genre_to_tracks.items(), key=lambda x: len(x[1]), reverse=True)
    top_5_genres = sorted_genres[:5]
    limited_genre_to_tracks = {genre: tracks[:3] for genre, tracks in top_5_genres}

    return render_template('genres.html', genres=top_5_genres, limited_genres=limited_genre_to_tracks)


# Route: Display all tracks in a genre
@app.route('/all_tracks')
def all_tracks():
    genre = request.args.get('genre', 'Unknown')
    top_tracks = sp.current_user_top_tracks(limit=50)['items']
    genre_to_tracks = defaultdict(list)

    for track in top_tracks:
        track_name = track['name']
        artist = track['artists'][0]
        artist_id = artist['id']
        artist_name = artist['name']
        popularity = track['popularity']
        times_played = calculate_times_played(popularity)

        artist_info = sp.artist(artist_id)
        genres = artist_info.get('genres', ['Unknown'])
        for g in genres:
            genre_to_tracks[g].append({
                'name': track_name,
                'artist': artist_name,
                'popularity': popularity,
                'times_played': times_played,
                'spotify_uri': track['uri']
            })

    all_tracks_in_genre = genre_to_tracks.get(genre, [])
    return render_template('all_tracks.html', genre=genre, tracks=all_tracks_in_genre)

# Route: Search for genres or vibes
@app.route('/search_genres', methods=['GET', 'POST'])
def search_genres():
    if request.method == 'POST':
        query = request.form['query']
        results = sp.search(q=query, type='playlist', limit=10)
        
        playlists = []
        for playlist in results['playlists']['items']:
            if not playlist or 'id' not in playlist:
                continue  # Skip if playlist is None or missing an ID
            playlists.append({
                'name': playlist.get('name', 'Unknown Playlist'),
                'owner': playlist.get('owner', {}),
                'images': playlist.get('images', []),
                'id': playlist['id'],  # Add ID for embedding
                'external_urls': playlist.get('external_urls', {}).get('spotify', '#')
            })
        
        return render_template('search.html', playlists=playlists, query=query)
    
    return render_template('search.html', playlists=[], query="")




# Route: Create a playlist from search results
@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    playlist_name = request.form.get('playlist_name', 'My Vibe Playlist')
    track_uris = request.form.getlist('track_uris')

    user_id = sp.me()['id']
    new_playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    sp.user_playlist_add_tracks(user_id, new_playlist['id'], track_uris)

    return redirect(url_for('home'))

# Main
if __name__ == '__main__':
    app.run(debug=True)
