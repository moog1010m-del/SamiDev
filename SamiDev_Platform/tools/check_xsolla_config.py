"""Check server checkout configuration without printing secrets or contacting Xsolla."""
import os
from pathlib import Path
from urllib.parse import urlsplit


def main():
    root = Path(__file__).resolve().parents[1]
    config = {}
    env = root / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip().strip('\"\x27')
    config.update(os.environ)
    failures = []
    for key in ('XSOLLA_PROJECT_ID', 'XSOLLA_API_KEY', 'XSOLLA_WEBHOOK_SECRET'):
        ok = bool(config.get(key))
        print(f'{key}: {"configured" if ok else "MISSING"}')
        if not ok:
            failures.append(key)
    url = urlsplit(config.get('XSOLLA_RETURN_URL', ''))
    valid_url = url.scheme == 'https' and bool(url.netloc)
    print('XSOLLA_RETURN_URL: ' + ('valid HTTPS URL' if valid_url else 'MISSING or invalid'))
    if not valid_url:
        failures.append('XSOLLA_RETURN_URL')
    print('Checkout: ' + ('enabled' if config.get('XSOLLA_ENABLED') == '1' else 'disabled'))
    print('Mode: ' + ('sandbox' if config.get('XSOLLA_SANDBOX', '1') == '1' else 'LIVE'))
    print('This checks configuration only; PostgreSQL, catalog and payment delivery still require verification.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
