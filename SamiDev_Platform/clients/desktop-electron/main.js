const { app, BrowserWindow, shell, session } = require('electron');

const PLATFORM_URL = process.env.SAMIDEV_PLATFORM_URL || 'http://127.0.0.1:8088/platform/';
const allowedOrigin = new URL(PLATFORM_URL).origin;

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
