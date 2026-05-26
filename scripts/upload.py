#!/usr/bin/env python3
"""
upload.py  -  REVIEW-GATE uploader for YouTube Shorts.

SAFETY BY DESIGN
  Every upload defaults to privacyStatus = "private". Nothing goes public until
  YOU review the video in YouTube Studio and flip it to Public (or use
  --privacy public / --publish-at to schedule). This is the human review gate.

WHAT IT DOES
  Reads a render folder's upload.json (made by make_video.py) and uploads
  output.mp4 to YouTube with the title/description/tags/category from that file.

USAGE
  python scripts/upload.py --dir "channels/ai-tadka/renders/<slug>-<stamp>"
  python scripts/upload.py --dir "<...>" --privacy unlisted
  python scripts/upload.py --dir "<...>" --publish-at 2026-05-25T13:00:00+05:30

ONE-TIME GOOGLE SETUP  (do this before first upload)
  1) Google Cloud Console -> create a project.
  2) Enable "YouTube Data API v3".
  3) Configure the OAuth consent screen (External; add yourself as a Test user).
  4) Create credentials -> OAuth client ID -> "Desktop app".
  5) Download the JSON, save it in the project root as  client_secret.json
     (already gitignored - never commit it).
  6) pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
  7) First run opens a browser to authorize; the token is cached in
     youtube_token.json so you won't have to log in again.

NOTE ON MULTIPLE CHANNELS
  YouTube OAuth authorizes the channel of the Google account you log in with.
  Run the first-time auth while logged into the account that owns the target
  channel, or keep a separate token file per channel via --token.
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_CLIENT_SECRETS = os.path.join(PROJECT_ROOT, "client_secret.json")
DEFAULT_TOKEN = os.path.join(PROJECT_ROOT, "youtube_token.json")


def die(msg):
    sys.exit(f"ERROR: {msg}")


def _require_google_libs():
    try:
        from googleapiclient.discovery import build  # noqa
        from googleapiclient.http import MediaFileUpload  # noqa
        from google_auth_oauthlib.flow import InstalledAppFlow  # noqa
        from google.auth.transport.requests import Request  # noqa
        from google.oauth2.credentials import Credentials  # noqa
    except ImportError:
        die(
            "Google API libraries are not installed. Run:\n"
            "  pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        )


def get_service(client_secrets, token_file):
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets):
                die(
                    f"client secrets not found at {client_secrets}.\n"
                    "See the ONE-TIME GOOGLE SETUP steps at the top of this file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(service, meta, video_path, privacy, publish_at):
    from googleapiclient.http import MediaFileUpload

    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        # scheduled publish requires the video to start private
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": meta["title"][:100],          # YouTube hard limit
            "description": meta.get("description", "")[:5000],
            "tags": meta.get("tags", []),
            "categoryId": str(meta.get("categoryId", "27")),
        },
        "status": status,
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    print(f"[upload] uploading '{meta['title']}' as {status['privacyStatus']}...")
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f"  {int(progress.progress() * 100)}%")
    return response


def main():
    ap = argparse.ArgumentParser(description="Review-gate YouTube Shorts uploader.")
    ap.add_argument("--dir", required=True,
                    help="render folder containing output.mp4 + upload.json")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"],
                    default="private", help="default private (review gate)")
    ap.add_argument("--publish-at", default=None,
                    help="ISO 8601 time to auto-publish, e.g. 2026-05-25T13:00:00+05:30")
    ap.add_argument("--client-secrets", default=DEFAULT_CLIENT_SECRETS)
    ap.add_argument("--token", default=DEFAULT_TOKEN,
                    help="OAuth token cache (use a different file per channel)")
    args = ap.parse_args()

    work = os.path.abspath(args.dir)
    meta_path = os.path.join(work, "upload.json")
    if not os.path.exists(meta_path):
        die(f"upload.json not found in {work} (run make_video.py first).")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    video_path = os.path.join(work, meta.get("video", "output.mp4"))
    if not os.path.exists(video_path):
        die(f"video not found: {video_path}")

    _require_google_libs()
    service = get_service(args.client_secrets, args.token)
    response = upload(service, meta, video_path, args.privacy, args.publish_at)

    vid = response.get("id")
    print("\nDONE.")
    print(f"  Video ID: {vid}")
    print(f"  Studio:   https://studio.youtube.com/video/{vid}/edit")
    print(f"  Watch:    https://youtu.be/{vid}")
    if args.privacy == "private" and not args.publish_at:
        print("  It is PRIVATE. Review it, then set it Public in YouTube Studio.")


if __name__ == "__main__":
    main()
