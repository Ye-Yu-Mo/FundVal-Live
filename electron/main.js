const { app, BrowserWindow, Tray, Menu } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const os = require('os');

let mainWindow = null;
let backendProcess = null;
let tray = null;
let backendPort = 21345; // 默认端口

// 配置文件路径
const configDir = path.join(os.homedir(), '.fundval-live');
const configPath = path.join(configDir, 'config.json');

// 日志文件路径
const logDir = path.join(configDir, 'logs');
const backendLogPath = path.join(logDir, 'backend.log');
const electronLogPath = path.join(logDir, 'electron.log');

// 确保配置和日志目录存在
if (!fs.existsSync(configDir)) {
  fs.mkdirSync(configDir, { recursive: true });
}
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

// 读取配置文件
function loadConfig() {
  try {
    if (fs.existsSync(configPath)) {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      backendPort = config.port || 21345;
      log(`📝 Loaded config: port=${backendPort}`);
    } else {
      // 创建默认配置文件
      const defaultConfig = { port: 21345 };
      fs.writeFileSync(configPath, JSON.stringify(defaultConfig, null, 2));
      log(`📝 Created default config at ${configPath}`);
    }
  } catch (error) {
    log(`⚠️ Failed to load config: ${error.message}, using default port 21345`);
    backendPort = 21345;
  }
}

// 日志函数
function log(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(logMessage.trim());
  fs.appendFileSync(electronLogPath, logMessage);
}

// 检查后端是否就绪
function checkBackendHealth(retries = 30) {
  return new Promise((resolve, reject) => {
    const check = (attempt) => {
      http.get(`http://127.0.0.1:${backendPort}/api/health`, (res) => {
        if (res.statusCode === 200) {
          log('✅ Backend is ready');
          resolve();
        } else {
          retry(attempt);
        }
      }).on('error', (err) => {
        if (attempt === 0) {
          log(`Health check error: ${err.message}`);
        }
        retry(attempt);
      });
    };

    const retry = (attempt) => {
      if (attempt < retries) {
        log(`⏳ Waiting for backend... (${attempt + 1}/${retries})`);
        setTimeout(() => check(attempt + 1), 1000);
      } else {
        reject(new Error('Backend failed to start'));
      }
    };

    check(0);
  });
}

// 启动后端
function startBackend() {
  return new Promise((resolve, reject) => {
    const isDev = !app.isPackaged;
    let backendPath;
    let backendArgs = [];

    log('🚀 Starting backend...');

    if (isDev) {
      // 开发模式：使用 uv run python 运行
      backendPath = 'uv';
      backendArgs = ['run', 'python', path.join(__dirname, '..', 'backend', 'run.py')];
      backendProcess = spawn(backendPath, backendArgs, {
        cwd: path.join(__dirname, '..'),
        env: { ...process.env, PORT: backendPort.toString() }
      });
    } else {
      // 生产模式：使用打包的可执行文件
      const platform = process.platform;
      if (platform === 'darwin') {
        backendPath = path.join(process.resourcesPath, 'backend', 'fundval-backend');
      } else if (platform === 'win32') {
        backendPath = path.join(process.resourcesPath, 'backend', 'fundval-backend.exe');
      } else {
        backendPath = path.join(process.resourcesPath, 'backend', 'fundval-backend');
      }

      log(`Backend path: ${backendPath}`);

      backendProcess = spawn(backendPath, [], {
        cwd: path.dirname(backendPath),
        env: { ...process.env, PORT: backendPort.toString() }
      });
    }

    // 捕获后端输出并写入日志
    const backendLogStream = fs.createWriteStream(backendLogPath, { flags: 'a' });

    backendProcess.stdout.on('data', (data) => {
      const message = data.toString();
      backendLogStream.write(`[STDOUT] ${message}`);
      console.log(`[Backend] ${message.trim()}`);
    });

    backendProcess.stderr.on('data', (data) => {
      const message = data.toString();
      backendLogStream.write(`[STDERR] ${message}`);
      console.error(`[Backend Error] ${message.trim()}`);
    });

    backendProcess.on('error', (error) => {
      log(`❌ Failed to start backend: ${error.message}`);
      backendLogStream.write(`[ERROR] ${error.message}\n`);
      reject(error);
    });

    backendProcess.on('close', (code) => {
      log(`⚠️ Backend process exited with code ${code}`);
      backendLogStream.write(`[EXIT] Process exited with code ${code}\n`);
      backendLogStream.end();

      // 如果后端意外退出，显示错误并退出应用
      if (code !== 0 && !app.isQuitting) {
        const { dialog } = require('electron');
        dialog.showErrorBox(
          'Backend Crashed',
          `Backend process exited unexpectedly with code ${code}.\n\nCheck logs at: ${backendLogPath}`
        );
        app.quit();
      }
    });

    // 等待后端就绪
    checkBackendHealth()
      .then(resolve)
      .catch(reject);
  });
}

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'icon.png'),
    title: 'FundVal Live',
  });

  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产模式：加载后端提供的前端
    mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
  }

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 创建系统托盘
function createTray() {
  tray = new Tray(path.join(__dirname, 'icon.png'));

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    {
      label: '退出',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('FundVal Live');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });
}

// 应用启动
app.whenReady().then(async () => {
  try {
    log('🚀 Starting FundVal Live...');

    // 加载配置
    loadConfig();

    // 启动后端
    await startBackend();

    // 创建窗口
    createWindow();

    // 创建托盘
    createTray();

    log('✅ FundVal Live is ready!');
  } catch (error) {
    log(`❌ Failed to start: ${error.message}`);
    const { dialog } = require('electron');
    dialog.showErrorBox(
      'Startup Failed',
      `Failed to start FundVal Live: ${error.message}\n\nCheck logs at: ${electronLogPath}`
    );
    app.quit();
  }
});

// 所有窗口关闭时
app.on('window-all-closed', () => {
  // macOS 上保持应用运行
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  } else {
    mainWindow.show();
  }
});

// 应用退出时清理
app.on('before-quit', () => {
  app.isQuitting = true;
});

app.on('will-quit', () => {
  // 杀掉后端进程
  if (backendProcess) {
    console.log('🛑 Stopping backend...');
    backendProcess.kill();
  }
});

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
  log(`Uncaught exception: ${error.message}`);
  log(error.stack);
});

process.on('unhandledRejection', (reason, promise) => {
  log(`Unhandled rejection at: ${promise}, reason: ${reason}`);
});
