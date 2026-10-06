// scripts/start.js
// Production runner for AgriMind
// Starts FastAPI backend (port 8000) and Next.js production server (port 3000).

const { spawn, execSync } = require('child_process');
const http = require('http');
const net = require('net');
const path = require('path');
const fs = require('fs');
const readline = require('readline');

const root = path.resolve(__dirname, '..');
const webDir = path.join(root, 'web');

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
  console.log(`${colors.green}${colors.bold}       🌾 AgriMind Platform — Production Server Runner       ${colors.reset}`);
  console.log(`${colors.green}${colors.bold}==============================================================${colors.reset}\n`);

  const pythonExe = findPython();
  if (!pythonExe) {
    log('[agrimind]', 'ERROR: Python 3.10+ runtime required.', colors.red);
    process.exit(1);
  }

  // Ensure production build exists
  const nextBuildDir = path.join(webDir, '.next');
  if (!fs.existsSync(nextBuildDir)) {
    log('[agrimind]', 'Next.js build not found. Running production build...', colors.yellow);
    try {
      execSync('npm run build', { cwd: webDir, stdio: 'inherit', shell: true });
      log('[agrimind]', 'Build completed successfully.', colors.green);
    } catch {
      log('[agrimind]', 'ERROR: Build failed.', colors.red);
      process.exit(1);
    }
  }

  killPortProcess(8000);
  killPortProcess(3000);

  // Backend
  log('[agrimind]', 'Starting Production Backend API on port 8000...', colors.cyan);
  const backendArgs = pythonExe === 'py'
    ? ['-3', '-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000']
    : ['-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8000'];

  const backendProc = spawn(pythonExe, backendArgs, {
    cwd: root,
    shell: false,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  pipeOutput(backendProc, '[backend]', colors.cyan);

  // Frontend
  log('[agrimind]', 'Starting Next.js Production Server on port 3000...', colors.magenta);
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const frontendProc = spawn(npmCmd, ['run', 'start'], {
    cwd: webDir,
    shell: true,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  pipeOutput(frontendProc, '[frontend]', colors.magenta);

  let shuttingDown = false;
  function shutdown(signal) {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`\n${colors.yellow}[agrimind] Terminating production services...${colors.reset}`);
    killProcessTree(backendProc);
    killProcessTree(frontendProc);
    killPortProcess(8000);
    killPortProcess(3000);
    log('[agrimind]', 'All services stopped.', colors.green);
    process.exit(0);
  }

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));

  backendProc.on('exit', (code) => {
    if (!shuttingDown) shutdown('backend exit');
  });
  frontendProc.on('exit', (code) => {
    if (!shuttingDown) shutdown('frontend exit');
  });

  // Wait for health
  let backendReady = false;
  let frontendReady = false;
  const readyInterval = setInterval(async () => {
    if (!backendReady) backendReady = await checkUrl('http://127.0.0.1:8000/health');
    if (!frontendReady) frontendReady = (await checkPortInUse(3000)) || (await checkUrl('http://127.0.0.1:3000'));

    if (backendReady && frontendReady) {
      clearInterval(readyInterval);
      console.log(`\n${colors.green}${colors.bold}==============================================================${colors.reset}`);
      console.log(`${colors.green}${colors.bold}   🌾 AgriMind Production Services Ready!                     ${colors.reset}`);
      console.log(`${colors.green}${colors.bold}   📡 Backend API:   ${colors.cyan}http://127.0.0.1:8000${colors.green}                           ${colors.reset}`);
      console.log(`${colors.green}${colors.bold}   💻 Frontend Web:  ${colors.magenta}http://localhost:3000${colors.green}                           ${colors.reset}`);
      console.log(`${colors.green}${colors.bold}==============================================================${colors.reset}\n`);
    }
  }, 1000);
}

main().catch((err) => {
  console.error('[agrimind] Production launcher error:', err);
  process.exit(1);
});
