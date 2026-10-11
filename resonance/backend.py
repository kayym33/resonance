from __future__ import annotations

import os
import time
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

REFRESH_TIME: int = 1
SPOTIFY_REFRESH_TIME: int = 5


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
    return spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))


spotify: spotipy.Spotify = get_spotify_client()


def get_current_song() -> dict[str, Any]:
    playing = spotify.current_playback()

    if not playing or not playing.get("item"):
        return {
            "title": "Nothing playing",
            "artist": "",
            "album": "",
            "device": "",
            "album_art_url": None,
            "is_playing": False,
            "progress_ms": 0,
            "duration_ms": 0,
        }

    track: dict[str, Any] = playing["item"]
    artist: str = ", ".join(
        artist["name"] for artist in track["artists"]
    )
    images: list[dict[str, Any]] = track.get("album", {}).get("images", [])
    return {
        "title": track["name"],
        "artist": artist,
        "album": track.get("album", {}).get("name", ""),
        "device": playing.get("device", {}).get("name", ""),
        "album_art_url": images[0]["url"] if images else None,
        "is_playing": playing.get("is_playing", False),
        "progress_ms": playing.get("progress_ms") or 0,
        "duration_ms": track.get("duration_ms") or 0,
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