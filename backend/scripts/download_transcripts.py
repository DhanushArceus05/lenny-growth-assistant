"""
Real transcript downloader for the assignment's "public Lenny's Podcast transcript
repository": Lenny Rachitsky's own official public starter-pack dataset —
https://github.com/LennysNewsletter/lennys-newsletterpodcastdata

By default this downloads the free starter pack (50 real podcast transcripts,
front-matter with title/guest/date/YouTube video ID, real [HH:MM:SS]-timestamped
speaker turns) directly from GitHub's raw content host.

IMPORTANT — license: the starter dataset's LICENSE.md permits personal,
non-commercial use — including building and publishing projects like this one —
but explicitly PROHIBITS redistributing the raw dataset files. This script
therefore downloads into --dest-dir (default: backend/data/lennys_podcast/, which
is .gitignore'd) at run time; the files are never committed to this repository.
Anyone who clones this repo must run this script themselves before ingesting real
data — see README.md §6.

If you have the paid full archive (lennysdata.com) or your own licensed transcript
export already on disk, use --local-source-dir instead of downloading the free
pack, and this script will just copy those .md files into --dest-dir.

Usage:
    # Download the real public starter pack (all ~50 free episodes)
    python -m scripts.download_transcripts

    # Grab just a handful for a quick smoke test
    python -m scripts.download_transcripts --limit 5

    # Use your own already-downloaded / paid archive instead of the free pack
    python -m scripts.download_transcripts --local-source-dir /path/to/your/archive
"""
import argparse
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

REPO = "LennysNewsletter/lennys-newsletterpodcastdata"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/main/"
INDEX_URL = RAW_BASE + "index.json"
LICENSE_URL = RAW_BASE + "LICENSE.md"

LICENSE_NOTICE = f"""
Downloading Lenny's Podcast Transcripts (free starter pack) from:
  https://github.com/{REPO}

License summary (full text saved to <dest-dir>/LICENSE.md):
  - Personal, non-commercial use is permitted, including building and publishing
    projects (like this one) that use the data.
  - Redistributing the RAW dataset files themselves is NOT permitted.

Files are saved under --dest-dir, which this project's .gitignore excludes —
do not commit that directory or its contents to source control.
"""


def _fetch_text(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "lenny-growth-assistant-ingest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed, known host
        return resp.read().decode("utf-8")


def download_starter_pack(dest_dir: Path, limit: int | None) -> int:
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(LICENSE_NOTICE)

    try:
        (dest_dir / "LICENSE.md").write_text(_fetch_text(LICENSE_URL), encoding="utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Warning: couldn't fetch LICENSE.md ({exc}); continuing anyway.")

    try:
        index = json.loads(_fetch_text(INDEX_URL))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAILED to fetch the dataset index from {INDEX_URL}: {exc}")
        print("Check your network connection, or use --local-source-dir if you have the data locally.")
        return 0

    episodes = index.get("podcasts", [])
    if limit:
        episodes = episodes[:limit]

    count = 0
    for ep in episodes:
        filename = ep.get("filename")  # e.g. "podcasts/stewart-butterfield.md"
        if not filename:
            continue
        url = RAW_BASE + filename
        try:
            content = _fetch_text(url)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"FAILED: {filename}: {exc}")
            continue
        out_path = dest_dir / Path(filename).name
        out_path.write_text(content, encoding="utf-8")
        count += 1
        print(f"Downloaded {filename}  ({ep.get('guest', 'unknown guest')})")

    print(f"\nDownloaded {count}/{len(episodes)} transcripts to {dest_dir}/")
    if count:
        print(f"Next: python -m scripts.ingest --source-dir {dest_dir}")
    return count


def copy_local_source(source_dir: Path, dest_dir: Path) -> int:
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(source_dir.glob("*.md")):
        shutil.copy(f, dest_dir / f.name)
        count += 1
    print(f"Copied {count} transcript file(s) from {source_dir} to {dest_dir}.")
    if count:
        print(f"Next: python -m scripts.ingest --source-dir {dest_dir}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dest-dir", default="data/lennys_podcast", help="Where to save transcripts (gitignored; default: data/lennys_podcast)"
    )
    parser.add_argument("--limit", type=int, default=None, help="Only download the first N episodes (default: all ~50 free ones)")
    parser.add_argument(
        "--local-source-dir",
        default=None,
        help="Copy .md files from this local directory instead of downloading (e.g. your paid lennysdata.com archive)",
    )
    args = parser.parse_args()

    dest = Path(args.dest_dir)
    if args.local_source_dir:
        copy_local_source(Path(args.local_source_dir), dest)
    else:
        download_starter_pack(dest, args.limit)


if __name__ == "__main__":
    main()
