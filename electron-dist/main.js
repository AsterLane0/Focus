const { app, BrowserWindow, Tray, Menu, nativeImage, screen, ipcMain } = require('electron');

let mainWindow = null;
let tray = null;
const WINDOW_WIDTH = 273;
const WINDOW_HEIGHT = 390;

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
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    const apiBase = (process.env.FOCUS_API_BASE || '').trim();
    if (apiBase) {
        mainWindow.loadFile('./index.html', {
            query: {
                api_base: apiBase
            }
        });
    } else {
        mainWindow.loadFile('./index.html');
    }
    //mainWindow.setBackgroundMaterial('acrylic');
    mainWindow.setAutoHideMenuBar(true); // 自动隐藏菜单
    mainWindow.setMenuBarVisibility(false); // 禁用菜单栏
}

function createTray() {
    // 创建番茄图标 (32x32 PNG)
    const iconDataUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAA7AAAAOwBeShxvQAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAKBSURBVFiFxZc9aBRBGIafudvbS/wQsLEQIhGBEBELsRCs/AMW/gEKC0GwELQQBAvRwkIsxEKwECz8AxYWYqEQLEQIYeEPsLAQLATBQhAsBDur7Azcu9vd2fE4dzNzd7kEN8Li4jDzzPOZ5zszO0NKKf7P+S1fQKXU+vo6iUQCrK0tlUohpURKiZQSSSkppZRSSiml1P1SSqWUUkqpr1++fPnyBf9bSqkPHz7w7t07APr6+mhpaQGgra2Njo4OANrb22lvb6e9vZ3e3l56enro6emhu7ubUqlEKpXizJkznD9/HoC2tjbC4TChUIhAIEAgEMDv9+N2u3E6nTgcDux2O3a7HavVisViwWw2YzKZMBqNGAwG9Ho9er0etVqNUqlEqVRy48YNbt26xS8B+fnz5/T09ACQzWZZWVkBoFAoUC6XAZhMJsrPzwGYzWbK5TKLi4vMzs4yPT1NKpXi1q1bXLt2DYBIJMK1a9cAiEQilMtl5ubmmJ6eJpVKcfPmTa5evQpAOBzm6tWrAMRiMebn55mensZqtXL9+nWuXLkCQCwW48qVKwBEo1Hm5uaYmpoiEolw7do1Ll26BEA4HObSpUsARCIR5ubmmJqaIhqNcu3aNS5evAhAKBTi4sWLAESjUeLxOJFIBIBIJMKFCxcAiEQiLC0tEQqFAFhYWGB+fh6AmZkZ5ubmAJiZmWFubg6AmZkZ5ufnAZidnWV+fh6A2dlZ5ufnAZidnWV+fh6A2dlZ5ufnAZidnWV+fh6AmZkZ5ubmAJiZmWFubg6AmZkZ5ubmAJiZmWFubg6AmZkZ5ufnAZidnWV+fh6A2dlZ5ufnAZidnWV+fh6AmZkZ5ubmAJiZmWFubg6AmZkZ5ubmAJiZmWF+fh6AmZkZ5ufnAZidnWV+fh6A2dlZ5ufngf8AP1+sN7jXZKoAAAAASUVORK5CYII=';
    
    const trayIcon = nativeImage.createFromDataURL(iconDataUrl);
    
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
