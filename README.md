# Spotify Event Lineup Matcher (Standalone Web App)

A 100% client-side, standalone web application to match any festival or event artist lineup against your personal Spotify listening history (Liked Songs, Top Artists, Top Tracks, and Recently Played).

---

## 🌟 Features

- **100% Client-Side & Standalone**: Runs entirely in the browser using Spotify PKCE OAuth flow. No Python or backend server required!
- **GitHub Pages Ready**: Can be deployed for free directly to GitHub Pages, Vercel, Netlify, or run locally.
- **Smart Automatic Delimiter Detection**:
  - Automatically identifies whether your input is separated by commas (`,`), line breaks (`\n`), semicolons (`;`), or tabs (`\t`).
  - Decodes HTML entities (e.g. `&amp;` -> `&`) before scoring delimiters.
  - Automatically strips surrounding single/double/curly quotes (`'...'`, `"..."`, `‘...’`) while preserving internal apostrophes.
  - Automatically separates back-to-back (`b2b`) entries.
- **Robust In-Browser Fuzzy Matching**:
  - NFKD accent decomposition & diacritic stripping (e.g. `Möbius` -> `mobius`, `ÉTIENNE` -> `etienne`).
  - Levenshtein distance string similarity check for close spelling variations.
- **Synced Spotify Library Viewer**:
  - View, search, and filter your entire imported Spotify music library right inside the app!

---

## 🚀 How to Host on GitHub Pages

1. **Push this repository to GitHub**.
2. **Configure Spotify Developer App**:
   - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
   - Edit your app settings and add your GitHub Pages URL to **Redirect URIs**:
     ```
     https://<your-username>.github.io/<your-repo-name>/
     ```
3. **Enable GitHub Pages**:
   - Go to your repository **Settings** -> **Pages**.
   - Under **Source**, select `main` branch and `/ (root)` folder.
   - Click **Save**.
4. Open your live GitHub Pages link, click **Connect Spotify**, and start matching lineups instantly!

---

## 💻 Local Usage

You can also run it locally:
- Simply open `index.html` in your browser!
- Or start a quick local HTTP server:
  ```bash
  python -m http.server 8000
  ```
  Then navigate to `http://localhost:8000`.
