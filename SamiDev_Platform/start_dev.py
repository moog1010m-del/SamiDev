from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def public_origin(value: str) -> str:
    """Explicit opt-in for a trusted HTTPS tunnel terminating on loopback."""
    try:
        uri = urlsplit(value.strip())
        if (uri.scheme != 'https' or not uri.hostname or uri.username is not None or
                uri.password is not None or uri.path not in {'', '/'} or uri.query or
                uri.fragment or any(c.isspace() for c in value.strip()) or ',' in value):
            raise ValueError
        host = uri.hostname.encode('idna').decode().lower()
        host = f'[{host}]' if ':' in host else host
        port = uri.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        return f'https://{host}' + (f':{port}' if port and port != 443 else '')
    except (ValueError, UnicodeError):
        raise argparse.ArgumentTypeError('Use an HTTPS origin only, e.g. https://example.trycloudflare.com') from None


def configure_public_proxy(env: dict, origin: str | None, port: int) -> None:
    if not origin:
        return
    # start_dev always binds the backend to 127.0.0.1. Forwarded scheme is
    # trusted only after the operator explicitly supplies their HTTPS origin.
    # This development mode trusts the forwarded scheme, not visitor-supplied
    # IP headers. Rate-limit identity remains the actual loopback peer.
    env['SAMIDEV_TRUST_PROXY'] = '0'
    env['SAMIDEV_TRUST_FORWARDED_HTTPS'] = '1'
    env['SAMIDEV_ALLOWED_ORIGINS'] = ','.join([origin, f'http://127.0.0.1:{port}', f'http://localhost:{port}'])


def local_build() -> dict:
    manifest = json.loads((ROOT / "game/platform/build.json").read_text(encoding="utf-8"))
    if not manifest.get("release") or set(manifest.get("games", [])) != {"carrom", "tablesoccer", "crazy8", "pool"}:
        raise RuntimeError("Wrong project version. Extract the complete SamiDev ZIP into a new folder.")
    for rel, expected in manifest["files"].items():
        actual = hashlib.sha256((ROOT / "game" / rel).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"UI file does not match this build: {rel}. Run tools/refresh_integrity.py in this project.")
    return manifest


def verify_served_ui(base_url: str, manifest: dict) -> None:
    served = wait_json(base_url + "/api/build")
    if served.get("buildId") != manifest["buildId"] or served.get("files") != manifest["files"]:
        raise RuntimeError("The running server is serving a different UI build.")
    for rel, expected in manifest["files"].items():
        route = "platform/" if rel == "platform/index.html" else rel
        request = urllib.request.Request(base_url + "/" + route + "?v=" + expected[:16],
                                         headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=5) as response:
            actual = hashlib.sha256(response.read()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"The server returned an old or different UI file: {rel}")
    catalog = wait_json(base_url + "/api/games")
    if {game["id"] for game in catalog.get("games", [])} != {"carrom", "tablesoccer", "crazy8", "pool"}:
        raise RuntimeError("The running backend does not provide all four games.")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_json(url: str, timeout: float = 30.0) -> dict:
    end = time.time() + timeout
    last: Exception | None = None
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=3.0) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(0.3)
    raise RuntimeError(f"Service did not start: {url} ({last})")


def terminate(p: subprocess.Popen | None) -> None:
    if not p or p.poll() is not None:
        return
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Start and verify the local SamiDev platform.")
    parser.add_argument("--check", action="store_true", help="Verify both services and UI, then stop without opening a browser.")
    parser.add_argument("--port", type=int, default=0, help="Fixed loopback backend port for a tunnel (default: choose a free port).")
    parser.add_argument("--public-origin", type=public_origin, help="HTTPS origin of a trusted tunnel to this loopback server; enables forwarded HTTPS and restricts Origin.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the local browser.")
    parser.add_argument('--storage', choices=('persistent', 'memory'), default='persistent',
        help='Persistent Redis/PostgreSQL by default; memory is an explicit disposable demo.')
    args = parser.parse_args()
    if args.storage == 'persistent' and (not os.environ.get('SAMIDEV_DATABASE_URL') or not os.environ.get('SAMIDEV_REDIS_URL')):
        parser.error('Persistent mode requires SAMIDEV_DATABASE_URL and SAMIDEV_REDIS_URL. For a disposable demo only, use --storage memory.')
    if not 0 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535, or 0 for automatic selection')
    try:
        manifest = local_build()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"SamiDev startup failed: {error}", file=sys.stderr)
        return 1
    if not shutil.which("node"):
        print("Node.js 22+ is required.")
        return 1

    gamehost_port = free_port()
    web_port = args.port or free_port()
    while web_port == gamehost_port:
        gamehost_port = free_port()

    service_key = os.environ.get("SAMIDEV_GAMEHOST_SERVICE_KEY") or secrets.token_urlsafe(32)
    gh_env = os.environ.copy()
    gh_env.pop("SAMIDEV_MAINJS_SHA256", None)
    gh_env.update({
        "SAMIDEV_PRODUCTION": "0",
        "SAMIDEV_GAMEHOST_HOST": "127.0.0.1",
        "SAMIDEV_GAMEHOST_PORT": str(gamehost_port),
        "SAMIDEV_GAME_DIR": str(ROOT / "game"),
        "SAMIDEV_GAMEHOST_SERVICE_KEY": service_key,
    })
    be_env = os.environ.copy()
    be_env.pop("SAMIDEV_GAMEHOST_URLS", None)
    be_env.pop("SAMIDEV_MAINJS_SHA256", None)
    be_env.update({
        "SAMIDEV_PRODUCTION": "0",
        "SAMIDEV_STORE": "redis" if args.storage == 'persistent' else 'memory',
        "SAMIDEV_PLATFORM_STORE": "postgres" if args.storage == 'persistent' else 'memory',
        "SAMIDEV_REQUIRE_GAME_AUTH": "1",
        "SAMIDEV_HOST": "127.0.0.1",
        "SAMIDEV_PORT": str(web_port),
        "SAMIDEV_GAMEHOST_URL": f"http://127.0.0.1:{gamehost_port}",
        "SAMIDEV_GAMEHOST_SERVICE_KEY": service_key,
        "SAMIDEV_ALLOWED_ORIGINS": "*",  # local development only
    })
    configure_public_proxy(be_env, args.public_origin, web_port)

    gamehost = backend = None
    try:
        gamehost = subprocess.Popen(["node", str(ROOT / "gamehost" / "server.js")], cwd=ROOT, env=gh_env)
        gh = wait_json(f"http://127.0.0.1:{gamehost_port}/health")
        backend = subprocess.Popen([sys.executable, str(ROOT / "backend" / "app.py")], cwd=ROOT, env=be_env)
        wait_json(f"http://127.0.0.1:{web_port}/health")

        base_url = f"http://127.0.0.1:{web_port}"
        verify_served_ui(base_url, manifest)
        if set(gh.get("games", {})) != {"carrom", "tablesoccer", "crazy8", "pool"}:
            raise RuntimeError("GameHost did not load all four games.")
        url = base_url + "/platform/?build=" + manifest["buildId"]
        print(f"\nSamiDev {manifest['release']}: served UI verified - Carrom, Table Soccer, Crazy 8 and Pool")
        print(f"Project:  {ROOT}")
        print(f"Build:    {manifest['buildId']}")
        print('Storage: Redis + PostgreSQL (persistent)' if args.storage == 'persistent' else 'WARNING: disposable MEMORY demo. Accounts and rooms are lost when stopped.')
        print(f"GameHost: http://127.0.0.1:{gamehost_port}  games={','.join(gh.get('games', {}))}")
        print(f"Game:     {url}")
        if args.public_origin:
            print(f"Public:   {args.public_origin}/platform/")
            print(f"Tunnel target: http://127.0.0.1:{web_port} (trusted forwarded HTTPS enabled)")
        if args.check:
            print("CHECK PASSED: all four games and all platform files are served by this project.")
            return 0
        print("Press Ctrl+C to stop both services.\n")
        try:
            if not args.no_browser:
                webbrowser.open(url)
        except Exception:
            pass
        return backend.wait()
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        print(f"SamiDev startup failed: {error}", file=sys.stderr)
        return 1
    finally:
        terminate(backend)
        terminate(gamehost)


if __name__ == "__main__":
    raise SystemExit(main())
