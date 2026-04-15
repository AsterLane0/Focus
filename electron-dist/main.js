const path = require('path');
const fs = require('fs');
const { app, BrowserWindow, Tray, Menu, nativeImage, screen, ipcMain } = require('electron');

let mainWindow = null;
let tray = null;
const WINDOW_WIDTH = 273;
const WINDOW_HEIGHT = 390;
const APP_ID = 'com.asterlane.focus';
const DEFAULT_API_BASE = 'http://120.77.145.202:9000';

function getConfigSearchPaths() {
    const candidates = [];

    if (app.isPackaged) {
        candidates.push(path.join(path.dirname(process.execPath), 'focus.config.json'));
        candidates.push(path.join(process.resourcesPath, 'focus.config.json'));
    }

    candidates.push(path.join(__dirname, 'focus.config.json'));
    return candidates;
}

function readExternalApiBase() {
    for (const configPath of getConfigSearchPaths()) {
        try {
            if (!fs.existsSync(configPath)) {
                continue;
            }

            const raw = fs.readFileSync(configPath, 'utf8');
            const parsed = JSON.parse(raw);
            const apiBase = String(parsed.apiBase || '').trim();
            if (apiBase) {
                return apiBase;
            }
        } catch (error) {
            console.warn(`Failed to read config from ${configPath}:`, error);
        }
    }

    return '';
}

function getAppIconPath() {
    return process.platform === 'win32'
        ? path.join(__dirname, 'build', 'icon.ico')
        : path.join(__dirname, 'build', 'icon.png');
}

function createWindow() {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;

    mainWindow = new BrowserWindow({
        width: WINDOW_WIDTH,
        height: WINDOW_HEIGHT,
        x: width - WINDOW_WIDTH - 20,
        y: Math.round((height - WINDOW_HEIGHT) / 2),
        frame: false,
        titleBarStyle: 'hidden',
        titleBarOverlay: false,
        transparent: true,
        backgroundColor: '#00000000',
        border: '0px',
        windowShadow: false,
        title: '',
        alwaysOnTop: false,
        resizable: false,
        thickFrame: false,
        skipTaskbar: false,
        icon: getAppIconPath(),
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    const apiBase = (
        process.env.FOCUS_API_BASE ||
        readExternalApiBase() ||
        DEFAULT_API_BASE
    ).trim();
    mainWindow.loadFile('./index.html', {
        query: {
            api_base: apiBase
        }
    });
    //mainWindow.setBackgroundMaterial('acrylic');
    mainWindow.setAutoHideMenuBar(true); // 自动隐藏菜单
    mainWindow.setMenuBarVisibility(false); // 禁用菜单栏
}

function createTray() {
    const trayIcon = nativeImage.createFromPath(getAppIconPath());
    
    tray = new Tray(trayIcon);
    tray.setToolTip('番茄钟 - 点击显示/隐藏');
    
    const contextMenu = Menu.buildFromTemplate([
        {
            label: '🍅 显示/隐藏',
            click: () => {
                if (mainWindow.isVisible()) {
                    mainWindow.hide();
                } else {
                    mainWindow.show();
                }
            }
        },
        {
            label: '🔄 重置',
            click: () => {
                mainWindow.webContents.send('reset-timer');
            }
        },
        { type: 'separator' },
        {
            label: '❌ 退出',
            click: () => {
                app.quit();
            }
        }
    ]);
    
    tray.setContextMenu(contextMenu);
    
    tray.on('click', () => {
        if (mainWindow.isVisible()) {
            mainWindow.hide();
        } else {
            mainWindow.show();
        }
    });
}

app.whenReady().then(() => {
    app.setAppUserModelId(APP_ID);
    createWindow();
    createTray();
    
    ipcMain.on('quit-app', () => {
        app.quit();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
