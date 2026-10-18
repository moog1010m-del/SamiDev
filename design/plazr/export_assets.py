from pathlib import Path
import json,subprocess
r=Path(__file__).resolve().parents[2];source=r/'design/plazr/app-icon.svg'
def export(path,size):
 subprocess.run(['inkscape',str(source),'--export-width='+str(size),'--export-filename='+str(path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for density,size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:export(r/f'SamiDev_Flutter/android/app/src/main/res/mipmap-{density}/ic_launcher.png',size)
base=r/'SamiDev_Flutter/ios/Runner/Assets.xcassets/AppIcon.appiconset'
for entry in json.loads((base/'Contents.json').read_text())['images']:
 if entry.get('filename'):export(base/entry['filename'],round(float(entry['size'].split('x')[0])*float(entry['scale'].rstrip('x'))))
export(r/'SamiDev_Platform/game/platform/assets/brand/apple-touch-icon.png',180)
