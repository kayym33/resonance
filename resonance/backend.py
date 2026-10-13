from __future__ import annotations

import os
import time
from typing import Any

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyPKCE

from .constants import SPOTIFY_CLIENT_ID, SPOTIFY_REDIRECT_URI
from .paths import DATA_DIR

REFRESH_TIME: int = 1
SPOTIFY_REFRESH_TIME: int = 5
SPOTIFY_TOKEN_PATH = DATA_DIR / "spotify-token.json"


def get_time() -> str:
    return time.strftime("%I:%M %p").lstrip("0")


def clear_console() -> None:
    os.system("cls")


def pause(seconds: float) -> None:
    time.sleep(seconds)


def get_spotify_client() -> spotipy.Spotify:
    scope = (
        "user-read-currently-playing "
        "user-read-playback-state "
        "user-modify-playback-state"
    )
    # PKCE signs in through the browser without a client secret. The
    # environment variables let a developer test against another app.
    auth_manager = SpotifyPKCE(
        client_id=os.environ.get("SPOTIPY_CLIENT_ID", SPOTIFY_CLIENT_ID),
        redirect_uri=os.environ.get(
            "SPOTIPY_REDIRECT_URI",
            SPOTIFY_REDIRECT_URI,
        ),
        scope=scope,
        cache_handler=CacheFileHandler(cache_path=str(SPOTIFY_TOKEN_PATH)),
    )
    return spotipy.Spotify(auth_manager=auth_manager)


spotify: spotipy.Spotify = get_spotify_client()
spotify_username: str | None = None


def get_current_song() -> dict[str, Any]:
    global spotify_username

    if spotify_username is None:
        user: dict[str, Any] = spotify.current_user()
        spotify_username = (
            user.get("display_name")
            or user.get("id")
            or "Spotify user"
        )

    playing = spotify.current_playback()

    if not playing or not playing.get("item"):
        return {
            "username": spotify_username,
            "title": "Nothing playing",
            "artist": "",
            "album": "",
            "device": "",
            "album_art_url": None,
            "is_playing": False,
            "progress_ms": 0,
            "duration_ms": 0,
            "volume_percent": None,
        }

    track: dict[str, Any] = playing["item"]
    artist: str = ", ".join(
        artist["name"] for artist in track["artists"]
    )
    images: list[dict[str, Any]] = track.get("album", {}).get("images", [])
    return {
        "username": spotify_username,
        "title": track["name"],
        "artist": artist,
        "album": track.get("album", {}).get("name", ""),
        "device": playing.get("device", {}).get("name", ""),
        "album_art_url": images[0]["url"] if images else None,
        "is_playing": playing.get("is_playing", False),
        "progress_ms": playing.get("progress_ms") or 0,
        "duration_ms": track.get("duration_ms") or 0,
        "volume_percent": playing.get("device", {}).get("volume_percent"),
    }


def play_music() -> None:
    spotify.start_playback()


def pause_music() -> None:
    spotify.pause_playback()


def toggle_playback() -> None:
    playing = spotify.current_user_playing_track()
    if playing and playing.get("is_playing"):
        pause_music()
    else:
        play_music()


def next_song() -> None:
    spotify.next_track()


def previous_song() -> None:
    spotify.previous_track()


def seek_playback(position_ms: int) -> None:
    spotify.seek_track(max(0, position_ms))


def set_volume(volume_percent: int) -> None:
    spotify.volume(max(0, min(100, volume_percent)))


def play_search(query: str) -> str:
    """Play the top Spotify track for a search and describe what started."""
    results = spotify.search(q=query, type="track", limit=1)
    tracks: list[dict[str, Any]] = results.get("tracks", {}).get("items", [])
    if not tracks:
        raise LookupError(f'no tracks found for "{query}"')
    track = tracks[0]
    spotify.start_playback(uris=[track["uri"]])
    artist = ", ".join(artist["name"] for artist in track["artists"])
    return f"{track['name']} by {artist}"
