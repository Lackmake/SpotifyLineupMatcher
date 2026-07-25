import os
import sys
import re
import time
import html
import urllib.request
import urllib.parse
import json
import webbrowser
import unicodedata
from http.server import HTTPServer, BaseHTTPRequestHandler

def clean_artist_name(name):
    if not name:
        return ""
    name = html.unescape(name)
    name = name.strip()
    name = re.sub(r'^[-*•]\s+', '', name)
    name = re.sub(r'^\d+[\.)]\s+', '', name)
    name = re.sub(r'^[\'"\`‘“\s]+|[\'"\`’”\s]+$', '', name)
    return name.strip()

# 1. Configuration & Constants
PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{PORT}/callback"
TOKEN_CACHE_FILE = ".spotify_token_cache.json"
PROFILE_CACHE_FILE = ".spotify_profile_cache.json"

# 2. Environment Loader
def load_env(filepath):
    env = {}
    if not os.path.exists(filepath):
        return env
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip()
    return env

# 3. String Normalization & Fuzzy Matching Logic
def normalize(s):
    # Strip invisible control/formatting characters
    s = "".join(c for c in s if unicodedata.category(c) not in ('Cf', 'Cn', 'Co', 'Cs'))
    # Accent decomposition
    nfkd = unicodedata.normalize('NFKD', s)
    # Keep letters and numbers, lowercase
    only_alphanum = "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()
    # Strip other non-alphanumeric punctuation
    only_alphanum = re.sub(r'[^a-z0-9\s]', '', only_alphanum)
    # Collapse multiple spaces
    return " ".join(only_alphanum.split())

def lev_distance(s1, s2):
    if len(s1) < len(s2):
        return lev_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def is_match(artist1_norm, artist2_norm):
    if not artist1_norm or not artist2_norm:
        return False
    # Exact match
    if artist1_norm == artist2_norm:
        return True
    # Substring match (whole words, length >= 3)
    words1 = artist1_norm.split()
    words2 = artist2_norm.split()
    if len(words1) >= 2 and artist1_norm in artist2_norm:
        return True
    if len(words2) >= 2 and artist2_norm in artist1_norm:
        return True
    # Levenshtein distance check for close spelling
    dist = lev_distance(artist1_norm, artist2_norm)
    min_len = min(len(artist1_norm), len(artist2_norm))
    if min_len > 4 and dist <= 1:
        return True
    if min_len > 8 and dist <= 2:
        return True
    return False

# 4. HTTP Helpers
def post_url(url, data_dict, headers=None):
    if headers is None:
        headers = {}
    data = urllib.parse.urlencode(data_dict).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {err_msg}")
        return {"error": err_msg, "status_code": e.code}

def get_url(url, headers=None):
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {err_msg}")
        return {"error": err_msg, "status_code": e.code}

# 5. Token & Profile Caching Engine
def save_token_cache(token_data):
    # Calculate absolute expiration timestamp
    if "expires_in" in token_data:
        token_data["expires_at"] = int(time.time()) + int(token_data["expires_in"])
    with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)

def load_token_cache():
    if not os.path.exists(TOKEN_CACHE_FILE):
        return None
    try:
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading token cache: {e}")
        return None

def get_valid_access_token():
    tokens = load_token_cache()
    if not tokens:
        return None
    
    expires_at = tokens.get("expires_at", 0)
    # Check if expired or expiring within 60s
    if time.time() > (expires_at - 60):
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return None
        
        env = load_env(".env")
        client_id = env.get("SPOTIFY_CLIENT_ID")
        client_secret = env.get("SPOTIFY_CLIENT_SECRET")
        
        print("Access token expired. Refreshing token with Spotify...")
        refreshed = post_url(
            "https://accounts.spotify.com/api/token",
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret
            }
        )
        if "access_token" in refreshed:
            if "refresh_token" not in refreshed:
                refreshed["refresh_token"] = refresh_token
            save_token_cache(refreshed)
            return refreshed["access_token"]
        else:
            print("Failed to refresh token:", refreshed)
            return None
            
    return tokens.get("access_token")

def save_profile_cache(profile_data):
    with open(PROFILE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)

def load_profile_cache():
    if not os.path.exists(PROFILE_CACHE_FILE):
        return None
    try:
        with open(PROFILE_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading profile cache: {e}")
        return None

# 6. Fetch Spotify User Listening Profile
def fetch_spotify_profile_data(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    spotify_data = {} # normalized_name -> details dict

    def add_artist_info(artist_name, liked_song=None, top_artist_term=None, top_track_song=None, recent_song=None):
        norm = normalize(artist_name)
        if norm not in spotify_data:
            spotify_data[norm] = {
                "original_artist": artist_name,
                "liked_songs": [],
                "top_artist_terms": [],
                "top_track_songs": [],
                "recently_played_songs": []
            }
        
        current_orig = spotify_data[norm]["original_artist"]
        if artist_name != current_orig and sum(1 for c in artist_name if c.isupper()) < sum(1 for c in current_orig if c.isupper()):
            if not artist_name.isupper():
                spotify_data[norm]["original_artist"] = artist_name

        if liked_song and liked_song not in spotify_data[norm]["liked_songs"]:
            spotify_data[norm]["liked_songs"].append(liked_song)
        if top_artist_term and top_artist_term not in spotify_data[norm]["top_artist_terms"]:
            spotify_data[norm]["top_artist_terms"].append(top_artist_term)
        if top_track_song and top_track_song not in spotify_data[norm]["top_track_songs"]:
            spotify_data[norm]["top_track_songs"].append(top_track_song)
        if recent_song and recent_song not in spotify_data[norm]["recently_played_songs"]:
            spotify_data[norm]["recently_played_songs"].append(recent_song)

    # 1. Fetch Liked Songs
    liked_url = "https://api.spotify.com/v1/me/tracks?limit=50"
    print("Fetching Spotify Liked Songs...")
    track_count = 0
    while liked_url:
        res = get_url(liked_url, headers)
        if isinstance(res, dict) and "error" in res:
            break
        items = res.get("items", [])
        if not items:
            break
            
        for item in items:
            track = item.get("track")
            if not track:
                continue
            track_name = track.get("name")
            track_count += 1
            for artist in track.get("artists", []):
                artist_name = artist.get("name")
                if artist_name:
                    add_artist_info(artist_name, liked_song=track_name)
        
        liked_url = res.get("next")

    # 2. Fetch Top Artists
    time_ranges = ["short_term", "medium_term", "long_term"]
    range_names = {
        "short_term": "recent (4 weeks)",
        "medium_term": "medium (6 months)",
        "long_term": "all-time"
    }
    
    print("Fetching Spotify Top Artists...")
    for tr in time_ranges:
        top_url = f"https://api.spotify.com/v1/me/top/artists?limit=50&time_range={tr}"
        res = get_url(top_url, headers)
        if isinstance(res, dict) and "items" in res:
            for artist in res.get("items", []):
                artist_name = artist.get("name")
                if artist_name:
                    add_artist_info(artist_name, top_artist_term=range_names[tr])

    # 3. Fetch Top Tracks
    print("Fetching Spotify Top Tracks...")
    for tr in time_ranges:
        top_url = f"https://api.spotify.com/v1/me/top/tracks?limit=50&time_range={tr}"
        res = get_url(top_url, headers)
        if isinstance(res, dict) and "items" in res:
            for item in res.get("items", []):
                track_name = item.get("name")
                for artist in item.get("artists", []):
                    artist_name = artist.get("name")
                    if artist_name:
                        add_artist_info(artist_name, top_track_song=f"'{track_name}' ({range_names[tr]})")

    # 4. Fetch Recently Played
    print("Fetching Spotify Recently Played...")
    recent_url = "https://api.spotify.com/v1/me/player/recently-played?limit=50"
    res = get_url(recent_url, headers)
    if isinstance(res, dict) and "items" in res:
        for item in res.get("items", []):
            track = item.get("track")
            if track:
                track_name = track.get("name")
                for artist in track.get("artists", []):
                    artist_name = artist.get("name")
                    if artist_name:
                        add_artist_info(artist_name, recent_song=track_name)

    print(f"Successfully processed profile. Unique artists found: {len(spotify_data)}")
    save_profile_cache(spotify_data)
    return spotify_data

# 7. Persistent Local Web Server Request Handler
class WebServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noise in terminal
        return

    def send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def send_html(self, content, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query = urllib.parse.parse_qs(parsed_path.query)

        if path == "/" or path == "/index.html":
            if os.path.exists("index.html"):
                with open("index.html", "r", encoding="utf-8") as f:
                    self.send_html(f.read())
            else:
                self.send_html("<h1>index.html not found</h1>", status_code=404)

        elif path == "/callback":
            if "code" in query:
                code = query["code"][0]
                env = load_env(".env")
                client_id = env.get("SPOTIFY_CLIENT_ID")
                client_secret = env.get("SPOTIFY_CLIENT_SECRET")
                
                token_response = post_url(
                    "https://accounts.spotify.com/api/token",
                    {
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": REDIRECT_URI,
                        "client_id": client_id,
                        "client_secret": client_secret
                    }
                )
                if "access_token" in token_response:
                    save_token_cache(token_response)
                    # Automatically fetch profile right after auth
                    fetch_spotify_profile_data(token_response["access_token"])
                    # Redirect to main SPA
                    self.send_response(302)
                    self.send_header("Location", "/")
                    self.end_headers()
                else:
                    self.send_html(f"<h1>Auth Error</h1><pre>{json.dumps(token_response)}</pre>", status_code=400)
            else:
                self.send_html("<h1>Authorization failed: no code provided</h1>", status_code=400)

        elif path == "/api/status":
            token = get_valid_access_token()
            profile_cache = load_profile_cache()
            artist_count = len(profile_cache) if profile_cache else 0
            self.send_json({
                "authenticated": token is not None,
                "cached_artists_count": artist_count
            })

        elif path == "/api/profile":
            profile_cache = load_profile_cache()
            if not profile_cache:
                self.send_json({
                    "total_artists": 0,
                    "artists_with_liked": 0,
                    "top_artists_count": 0,
                    "recently_played_count": 0,
                    "artists": []
                })
                return
            
            artist_list = []
            for norm, info in profile_cache.items():
                artist_list.append({
                    "artist_name": info["original_artist"],
                    "liked_songs": info.get("liked_songs", []),
                    "top_artist_terms": info.get("top_artist_terms", []),
                    "top_track_songs": info.get("top_track_songs", []),
                    "recently_played_songs": info.get("recently_played_songs", [])
                })
            
            artist_list.sort(key=lambda x: x["artist_name"].lower())
            
            total_artists = len(artist_list)
            artists_with_liked = sum(1 for a in artist_list if a["liked_songs"])
            top_artists_count = sum(1 for a in artist_list if a["top_artist_terms"])
            recently_played_count = sum(1 for a in artist_list if a["recently_played_songs"])
            
            self.send_json({
                "total_artists": total_artists,
                "artists_with_liked": artists_with_liked,
                "top_artists_count": top_artists_count,
                "recently_played_count": recently_played_count,
                "artists": artist_list
            })

        elif path == "/api/login":
            env = load_env(".env")
            client_id = env.get("SPOTIFY_CLIENT_ID")
            scope = "user-library-read user-top-read user-read-recently-played"
            auth_params = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": scope
            }
            auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(auth_params)
            self.send_response(302)
            self.send_header("Location", auth_url)
            self.end_headers()

        else:
            self.send_html("<h1>404 Not Found</h1>", status_code=404)

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len).decode('utf-8') if content_len > 0 else ""

        if path == "/api/fetch-profile":
            token = get_valid_access_token()
            if not token:
                self.send_json({"error": "Not authenticated"}, status_code=401)
                return
            data = fetch_spotify_profile_data(token)
            self.send_json({"status": "success", "total_artists": len(data)})

        elif path == "/api/match":
            try:
                body = json.loads(post_body)
                lineup_input_list = body.get("artists", [])
            except Exception as e:
                self.send_json({"error": "Invalid JSON"}, status_code=400)
                return

            profile_cache = load_profile_cache()
            if not profile_cache:
                token = get_valid_access_token()
                if token:
                    profile_cache = fetch_spotify_profile_data(token)
                else:
                    self.send_json({"error": "Spotify profile not loaded. Please connect to Spotify first."}, status_code=401)
                    return

            matches = []
            unmatched = []

            for raw_artist in lineup_input_list:
                cleaned_artist = clean_artist_name(raw_artist)
                if not cleaned_artist:
                    continue
                lineup_norm = normalize(cleaned_artist)
                matched_entry = None

                for spotify_norm, info in profile_cache.items():
                    if is_match(lineup_norm, spotify_norm):
                        matched_entry = {
                            "lineup_artist": cleaned_artist,
                            "matched_spotify_artist": info["original_artist"],
                            "liked_songs": info["liked_songs"],
                            "top_artist_terms": info["top_artist_terms"],
                            "top_track_songs": info["top_track_songs"],
                            "recently_played_songs": info["recently_played_songs"]
                        }
                        break

                if matched_entry:
                    matches.append(matched_entry)
                else:
                    unmatched.append(cleaned_artist)

            self.send_json({
                "matches": matches,
                "unmatched": unmatched
            })

        elif path == "/api/logout":
            if os.path.exists(TOKEN_CACHE_FILE):
                os.remove(TOKEN_CACHE_FILE)
            if os.path.exists(PROFILE_CACHE_FILE):
                os.remove(PROFILE_CACHE_FILE)
            self.send_json({"status": "logged_out"})

        else:
            self.send_json({"error": "Endpoint not found"}, status_code=404)

# 8. Main Entrypoint
def main():
    env = load_env(".env")
    client_id = env.get("SPOTIFY_CLIENT_ID")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret or "your_" in client_id or "your_" in client_secret:
        print("ERROR: Please configure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env.")
        sys.exit(1)

    url = f"http://127.0.0.1:{PORT}"
    print(f"==================================================")
    print(f" Spotify Event Lineup Matcher Server Running!")
    print(f" Server Address: {url}")
    print(f" Press Ctrl+C in terminal to stop.")
    print(f"==================================================")

    server = HTTPServer(("127.0.0.1", PORT), WebServerHandler)
    webbrowser.open(url)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        server.server_close()

if __name__ == "__main__":
    main()
