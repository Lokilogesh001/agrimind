// scripts/dev.js
// One-command development runner for AgriMind
// Starts FastAPI backend (port 8000) and Next.js frontend (port 3000) concurrently.

const { spawn, execSync } = require('child_process');
const http = require('http');
const net = require('net');
const path = require('path');
const fs = require('fs');
const readline = require('readline');

const root = path.resolve(__dirname, '..');
const webDir = path.join(root, 'web');

// ANSI Colors
const colors = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  dim: '\x1b[2m',
};

function log(prefix, msg, color = colors.reset) {
  const ts = new Date().toLocaleTimeString();
  console.log(`${colors.dim}${ts}${colors.reset} ${color}${prefix}${colors.reset} ${msg}`);
}

function findPython() {
  const isWin = process.platform === 'win32';
  const candidates = [];

  if (process.env.VIRTUAL_ENV) {
    candidates.push(path.join(process.env.VIRTUAL_ENV, isWin ? 'Scripts/python.exe' : 'bin/python'));
  }
  candidates.push(
    path.join(root, isWin ? '.venv/Scripts/python.exe' : '.venv/bin/python'),
    path.join(root, isWin ? 'venv/Scripts/python.exe' : 'venv/bin/python'),
    path.join(root, isWin ? 'env/Scripts/python.exe' : 'env/bin/python'),
    'python',
    'py'
  );

  for (const cand of candidates) {
    try {
      if (cand.includes(path.sep) && !fs.existsSync(cand)) continue;
      const cmd = cand === 'py' ? 'py -3 --version' : `"${cand}" --version`;
      execSync(cmd, { stdio: 'ignore' });
      return cand;
    } catch {}
  }
  return null;
}

function checkPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', (err) => {
      if (err.code === 'EADDRINUSE') resolve(true);
      else resolve(false);
    });
    server.once('listening', () => {
      server.close();
      resolve(false);
    });
    server.listen(port, '127.0.0.1');
  });
}

function killPortProcess(port) {
  if (process.platform === 'win32') {
    try {
      const out = execSync(`netstat -ano -p tcp | findstr :${port} | findstr LISTENING`, { encoding: 'utf-8' });
      const lines = out.trim().split('\n');
      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0' && pid !== String(process.pid)) {
          log('[agrimind]', `Releasing port ${port} held by process PID ${pid}...`, colors.yellow);
          execSync(`taskkill /PID ${pid} /T /F`, { stdio: 'ignore' });
        }
      }
    } catch {}
  }
}

function killProcessTree(proc) {
  if (!proc || !proc.pid) return;
  try {
    if (process.platform === 'win32') {
      execSync(`taskkill /PID ${proc.pid} /T /F`, { stdio: 'ignore' });
    } else {
      proc.kill('SIGTERM');
    }
  } catch {}
}

function checkUrl(url, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      resolve(res.statusCode >= 200 && res.statusCode < 400);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function pipeOutput(proc, prefix, color) {
  if (proc.stdout) {
    const rlOut = readline.createInterface({ input: proc.stdout });
    rlOut.on('line', (line) => {
      if (line.trim()) console.log(`${color}${prefix}${colors.reset} ${line}`);
    });
  }
  if (proc.stderr) {
    const rlErr = readline.createInterface({ input: proc.stderr });
    rlErr.on('line', (line) => {
      if (line.trim()) console.log(`${color}${prefix}${colors.reset} ${line}`);
    });
  }
}

async function main() {
  console.log(`\n${colors.green}${colors.bold}==============================================================${colors.reset}`);
  console.log(`${colors.green}${colors.bold}       🌾 AgriMind Platform — Single Command Runner          ${colors.reset}`);
  console.log(`${colors.green}${colors.bold}==============================================================${colors.reset}\n`);

  // 1. Detect Python
  log('[agrimind]', 'Detecting Python runtime...', colors.green);
  const pythonExe = findPython();
  if (!pythonExe) {
    log('[agrimind]', 'ERROR: Python not found. Please install Python 3.10+.', colors.red);
    process.exit(1);
  }

  // Check Python dependencies
  try {
    const checkCmd = pythonExe === 'py' ? 'py -3 -c "import fastapi, uvicorn"' : `"${pythonExe}" -c "import fastapi, uvicorn"`;
    execSync(checkCmd, { stdio: 'ignore' });
    log('[agrimind]', `Python runtime verified: ${pythonExe}`, colors.green);
  } catch {
    log('[agrimind]', 'ERROR: Missing Python dependencies (fastapi, uvicorn).', colors.red);
    log('[agrimind]', 'Run: pip install -r requirements.txt', colors.yellow);
    process.exit(1);
  }

  // 2. Check frontend dependencies
  const webNodeModules = path.join(webDir, 'node_modules');
  if (!fs.existsSync(webNodeModules)) {
    log('[agrimind]', 'Frontend node_modules missing. Installing dependencies...', colors.yellow);
    try {
      execSync('npm install', { cwd: webDir, stdio: 'inherit', shell: true });
      log('[agrimind]', 'Frontend dependencies installed successfully.', colors.green);
    } catch {
      log('[agrimind]', 'ERROR: Failed to install frontend dependencies.', colors.red);
      process.exit(1);
    }
  }

  // 3. Port conflict prevention
  const port8000Used = await checkPortInUse(8000);
  if (port8000Used) {
    log('[agrimind]', 'Port 8000 in use. Attempting clean release...', colors.yellow);
    killPortProcess(8000);
    await new Promise((r) => setTimeout(r, 600));
  }

  const port3000Used = await checkPortInUse(3000);
  if (port3000Used) {
    log('[agrimind]', 'Port 3000 in use. Attempting clean release...', colors.yellow);
    killPortProcess(3000);
    await new Promise((r) => setTimeout(r, 600));
  }

  // 4. Start Backend
  log('[agrimind]', 'Spawning Backend API on http://127.0.0.1:8000...', colors.cyan);
  const backendArgs = pythonExe === 'py'
    ? ['-3', '-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000']
    : ['-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000'];

  const backendProc = spawn(pythonExe, backendArgs, {
    cwd: root,
    shell: false,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pipeOutput(backendProc, '[backend]', colors.cyan);

  // 5. Start Frontend
  log('[agrimind]', 'Spawning Frontend Web on http://localhost:3000...', colors.magenta);
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const frontendProc = spawn(npmCmd, ['run', 'dev'], {
    cwd: webDir,
    shell: true,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pipeOutput(frontendProc, '[frontend]', colors.magenta);

  let shuttingDown = false;
  function shutdown(signal) {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`\n${colors.yellow}[agrimind] Received ${signal || 'shutdown signal'}. Terminating all services...${colors.reset}`);
    killProcessTree(backendProc);
    killProcessTree(frontendProc);
    killPortProcess(8000);
    killPortProcess(3000);
    log('[agrimind]', 'All services stopped cleanly.', colors.green);
    process.exit(0);
  }

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGHUP', () => shutdown('SIGHUP'));
  process.on('exit', () => {
    if (!shuttingDown) shutdown('exit');
  });

  backendProc.on('exit', (code) => {
    if (!shuttingDown) {
      log('[agrimind]', `Backend process exited with code ${code}. Stopping frontend...`, colors.red);
      shutdown('backend exit');
    }
  });

  frontendProc.on('exit', (code) => {
    if (!shuttingDown) {
      log('[agrimind]', `Frontend process exited with code ${code}. Stopping backend...`, colors.red);
      shutdown('frontend exit');
    }
  });

  // 6. Monitor readiness
  let backendReady = false;
  let frontendReady = false;
  const startTime = Date.now();
  const timeoutMs = process.env.AGRIMIND_STARTUP_TIMEOUT
    ? Number(process.env.AGRIMIND_STARTUP_TIMEOUT) * 1000
    : 60000;

  const readyInterval = setInterval(async () => {
    if (!backendReady) {
      backendReady = await checkUrl('http://127.0.0.1:8000/health');
    }
    if (!frontendReady) {
      frontendReady = (await checkPortInUse(3000)) || (await checkUrl('http://127.0.0.1:3000'));
    }

    if (backendReady && frontendReady) {
      clearInterval(readyInterval);
      console.log(`\n${colors.green}${colors.bold}==============================================================${colors.reset}`);
      console.log(`${colors.green}${colors.bold}   🌾 AgriMind Platform is Live!                              ${colors.reset}`);
      console.log(`${colors.green}${colors.bold}   📡 Backend API:   ${colors.cyan}http://127.0.0.1:8000${colors.green}  (Swagger Docs: /docs)    ${colors.reset}`);
      console.log(`${colors.green}${colors.bold}   💻 Frontend Web:  ${colors.magenta}http://localhost:3000${colors.green}                           ${colors.reset}`);
      console.log(`${colors.dim}   Press Ctrl+C anytime to stop both services gracefully.     ${colors.reset}`);
      console.log(`${colors.green}${colors.bold}==============================================================${colors.reset}\n`);
    } else if (Date.now() - startTime > timeoutMs) {
      clearInterval(readyInterval);
      if (!backendReady) log('[agrimind]', 'Warning: Backend /health check timed out.', colors.yellow);
      if (!frontendReady) log('[agrimind]', 'Warning: Frontend port 3000 readiness timed out.', colors.yellow);
    }
  }, 1000);
}

main().catch((err) => {
  console.error('[agrimind] Fatal error in launcher:', err);
  process.exit(1);
});
