const { app, BrowserWindow, shell, session } = require('electron');

const configuredUrl = process.env.SAMIDEV_PLATFORM_URL || (!app.isPackaged ? 'http://127.0.0.1:8088/platform/' : '');
if (!configuredUrl) throw new Error('Set SAMIDEV_PLATFORM_URL to your HTTPS platform origin');
const platform = new URL(configuredUrl);
const localDevelopment = !app.isPackaged && ['127.0.0.1','localhost','[::1]'].includes(platform.hostname);
if ((platform.protocol !== 'https:' && !(localDevelopment && platform.protocol === 'http:')) || platform.username || platform.password || platform.search || platform.hash || !['/','/platform/'].includes(platform.pathname) || ['game.example.com','example.com'].includes(platform.hostname)) throw new Error('Invalid platform URL');
platform.pathname = '/platform/';
const PLATFORM_URL = platform.href;
const allowedOrigin = platform.origin;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 920,
    minHeight: 600,
    backgroundColor: '#090d12',
    autoHideMenuBar: true,
    title: 'SamiDev',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    const u = new URL(url);
    if (u.origin === allowedOrigin) return { action: 'allow' };
    shell.openExternal(url);
    return { action: 'deny' };
  });

  win.webContents.on('will-navigate', (event, url) => {
    const u = new URL(url);
    if (u.origin !== allowedOrigin) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  win.loadURL(PLATFORM_URL);
}

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
