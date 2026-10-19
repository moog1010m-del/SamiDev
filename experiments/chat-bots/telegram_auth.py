"""Telegram authentication helper to initialize the session once."""
import asyncio, json, os, sys
from pathlib import Path
from telethon import TelegramClient

SECRETS_DIR = Path(r"C:\Users\Dev\.samidev\secrets")
CONFIG_PATH = SECRETS_DIR / "telegram.json"
SESSION_PATH = str(SECRETS_DIR / "telegram_listener")

async def main():
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    phone = config.get("phone")

    if not api_id or not api_hash or not phone:
        print("CONFIG_REQUIRED: api_id و api_hash و phone مطلوبة في telegram.json", flush=True)
        return 1

    api_id = int(api_id)
    print(f"Connecting to Telegram MTProto...", flush=True)
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"Requesting verification code for {phone}...", flush=True)
        sent = await client.send_code_request(phone)
        print(">>> WAITING_FOR_TELEGRAM_CODE <<<", flush=True)
        print(f"تم إرسال كود التحقق بنجاح إلى تطبيق تيلجرام على حساب {phone}", flush=True)
        
        # Read code from stdin
        loop = asyncio.get_running_loop()
        code = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        print(f"Received code, signing in...", flush=True)
        
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except Exception as e:
            if "SessionPasswordNeededError" in type(e).__name__:
                print(">>> WAITING_FOR_2FA_PASSWORD <<<", flush=True)
                password = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
                await client.sign_in(password=password)
            else:
                raise

    me = await client.get_me()
    print(f"SUCCESS: تم تسجيل الدخول بنجاح بحساب: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', '')})", flush=True)
    print(f"تم حفظ الجلسة الدائمة في: {SESSION_PATH}.session", flush=True)
    await client.disconnect()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as error:
        print(f"AUTH_ERROR: {type(error).__name__}: {error}", flush=True)
        sys.exit(1)
