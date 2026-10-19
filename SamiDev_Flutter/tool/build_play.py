"""Reviewable local AAB build. No publishing, signing-key generation or secrets output."""
import argparse,json,subprocess,sys
from pathlib import Path
from play_preflight import ROOT,https_origin

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--server-url',required=True);parser.add_argument('--flutter',default='flutter')
 args=parser.parse_args()
 if not https_origin(args.server_url):parser.error('A stable HTTPS server origin is required')
 release=json.loads((ROOT/'play/release.json').read_text())
 if args.server_url.rstrip('/')!=(release.get('apiOrigin') or '').rstrip('/'):parser.error('Server URL must match the reviewed apiOrigin in play/release.json')
 subprocess.run([sys.executable,str(ROOT/'tool/play_preflight.py'),'--stage','build'],cwd=ROOT,check=True)
 if not (ROOT/'android/key.properties').is_file():raise SystemExit('Missing private android/key.properties upload-key configuration; never commit it')
 # Protect a distribution copy; the backend must serve this same tree via
 # SAMIDEV_GAME_DIR so existing exact engine-hash checks remain enforced.
 platform=ROOT.parent/'SamiDev_Platform'
 protected=platform/'build/protected-game'
 subprocess.run([sys.executable,str(platform/'tools/protect_game_release.py'),'--output',str(protected)],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(platform/'tests/protected_release.py'),str(protected)],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(ROOT/'tool/sync_assets.py'),'--web-root',str(protected)],cwd=ROOT,check=True)
 subprocess.run([args.flutter,'pub','get','--enforce-lockfile'],cwd=ROOT,check=True)
 subprocess.run([args.flutter,'analyze','--no-fatal-infos'],cwd=ROOT,check=True)
 subprocess.run([args.flutter,'test','--no-pub'],cwd=ROOT,check=True)
 symbols=ROOT/'build/private-play-symbols'
 subprocess.run([args.flutter,'build','appbundle','--release','--no-pub','--obfuscate','--split-debug-info='+str(symbols),'--dart-define=SAMIDEV_SERVER_URL='+args.server_url.rstrip('/')],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(ROOT/'tool/play_preflight.py'),'--stage','build','--artifact',str(ROOT/'build/app/outputs/bundle/release/app-release.aab')],cwd=ROOT,check=True)
 print('AAB built locally. Keep symbols private. Upload to internal testing and complete device/pre-launch review; nothing was published.')
if __name__=='__main__':main()
