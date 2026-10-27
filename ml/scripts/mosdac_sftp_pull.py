"""Phase 2 / Step 5: copy your MOSDAC orders from MOSDAC's SFTP server into
<root>/raw/mosdac/insat3d (or --dest-sub). Meant to run on Colab with --root on
Google Drive, so the big files never touch your laptop.

Before this: place an order in the MOSDAC portal (Order Data). When it is ready it
appears in the /Order folder of the SFTP server (host download.mosdac.gov.in, port 22).
Login = your MOSDAC username/password.

Usage:
    pip install paramiko
    python ml/scripts/mosdac_sftp_pull.py --list-only                 # just show what is there
    python ml/scripts/mosdac_sftp_pull.py --root /content/drive/MyDrive/trinetra_data
Credentials: env MOSDAC_USERNAME / MOSDAC_PASSWORD, otherwise you are prompted
(never put them in a notebook cell or in Git).
Safe to re-run: files already present with the same size are skipped.
"""
import argparse
import os
import stat
from getpass import getpass
from pathlib import Path

HOST = "download.mosdac.gov.in"
PORT = 22


def walk(sftp, remote: str):
    for entry in sftp.listdir_attr(remote):
        path = remote.rstrip("/") + "/" + entry.filename
        if stat.S_ISDIR(entry.st_mode):
            yield from walk(sftp, path)
        else:
            yield path, entry.st_size


def main() -> None:
    default_root = Path(__file__).resolve().parents[1] / "data"
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=default_root)
    ap.add_argument("--remote-dir", default="/Order")
    ap.add_argument("--dest-sub", default="raw/mosdac/insat3d")
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()

    import paramiko

    user = os.environ.get("MOSDAC_USERNAME") or input("MOSDAC username: ")
    pw = os.environ.get("MOSDAC_PASSWORD") or getpass("MOSDAC password: ")

    client = paramiko.SSHClient()
    # First connection to this host: accept its key. (Fine for a data pull; do not reuse for sensitive hosts.)
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=user, password=pw, timeout=60)
    sftp = client.open_sftp()

    files = list(walk(sftp, args.remote_dir))
    total = sum(s for _, s in files)
    print(f"{len(files)} files, {total/1e9:.2f} GB under {args.remote_dir}")
    if args.list_only:
        for p, s in files[:50]:
            print(f"  {s/1e6:9.1f} MB  {p}")
        if len(files) > 50:
            print(f"  ... and {len(files) - 50} more")
        return

    dest_root = args.root / args.dest_sub
    done = skipped = 0
    for i, (remote, size) in enumerate(files, 1):
        local = dest_root / remote[len(args.remote_dir):].lstrip("/")
        if local.exists() and local.stat().st_size == size:
            skipped += 1
            continue
        local.parent.mkdir(parents=True, exist_ok=True)
        part = local.with_name(local.name + ".part")
        sftp.get(remote, str(part))
        part.replace(local)
        done += 1
        if done % 25 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}] downloaded {done}, skipped {skipped}")
    print(f"finished: {done} downloaded, {skipped} already present -> {dest_root}")
    sftp.close()
    client.close()


if __name__ == "__main__":
    main()
