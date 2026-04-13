/**
 * HITS Node.js Server
 *
 * Serves:
 *   - Static frontend (hits_web/dist/)
 *   - API proxy to Python FastAPI backend (localhost:8765)
 *
 * Manages:
 *   - Python venv creation + dependency installation
 *   - Python backend lifecycle (start/stop/restart)
 *   - Graceful shutdown
 */

import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { spawn, execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { platform } from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
const isWin = platform() === 'win32';

// ─── Python Detection ───────────────────────────────────────────

function findPython() {
  const envPython = process.env.HITS_PYTHON;
  if (envPython && existsSync(envPython)) return envPython;

  const candidates = isWin
    ? ['python', 'python3', 'py']
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const ver = execSync(`${cmd} --version`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] });
      const match = ver.match(/Python (\d+)\.(\d+)/);
      if (match && (parseInt(match[1]) > 3 || (parseInt(match[1]) === 3 && parseInt(match[2]) >= 10))) {
        return cmd;
      }
    } catch {}
  }
  return null;
}

// ─── Venv Management ────────────────────────────────────────────

const VENV_DIR = join(ROOT, 'venv');
const PYTHON_BIN = isWin
  ? join(VENV_DIR, 'Scripts', 'python.exe')
  : join(VENV_DIR, 'bin', 'python');

function venvExists() {
  return existsSync(PYTHON_BIN);
}

function pipPath() {
  return isWin
    ? join(VENV_DIR, 'Scripts', 'pip.exe')
    : join(VENV_DIR, 'bin', 'pip');
}

function runCommand(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, { stdio: 'inherit', ...opts });
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Command failed: ${cmd} ${args.join(' ')} (exit ${code})`));
    });
    proc.on('error', reject);
  });
}

async function setupPython() {
  const pythonCmd = findPython();
  if (!pythonCmd) {
    console.error('Error: Python 3.10+ not found.');
    console.error('Install: https://www.python.org/downloads/');
    process.exit(1);
  }

  if (!venvExists()) {
    console.log(`Creating virtual environment... (${pythonCmd})`);
    await runCommand(pythonCmd, ['-m', 'venv', VENV_DIR], { cwd: ROOT });
  }

  if (!existsSync(pipPath())) {
    console.error('Error: pip not found in venv.');
    process.exit(1);
  }

  // Check if deps are installed
  try {
    execSync(`${PYTHON_BIN} -c "import fastapi, pydantic, argon2, jose"`, { stdio: 'ignore' });
  } catch {
    console.log('Installing Python dependencies...');
    await runCommand(PYTHON_BIN, ['-m', 'pip', 'install', '-q', '--upgrade', 'pip'], { cwd: ROOT });
    await runCommand(PYTHON_BIN, ['-m', 'pip', 'install', '-q', '-r', 'requirements.txt'], { cwd: ROOT });
    console.log('Dependencies installed.');
  }
}

// ─── Python Backend Process ─────────────────────────────────────

let backendProc = null;
const API_PORT = 18765;  // Internal Python backend port (different from user-facing port)

function startBackend(dev) {
  return new Promise((resolve, reject) => {
    const args = ['-m', 'hits_core.main', '--port', String(API_PORT)];
    if (dev) args.push('--dev');

    console.log(`Starting Python backend on port ${API_PORT}...`);
    backendProc = spawn(PYTHON_BIN, args, {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env },
    });

    let started = false;

    backendProc.stdout.on('data', (data) => {
      const msg = data.toString().trim();
      if (dev && msg) console.log(`[api] ${msg}`);
      if (!started && (msg.includes('Uvicorn running') || msg.includes('Application startup complete') || msg.includes('Started server') || msg.includes('HITS Web Server starting'))) {
        started = true;
        resolve();
      }
    });

    backendProc.stderr.on('data', (data) => {
      const msg = data.toString().trim();
      if (dev && msg) console.error(`[api] ${msg}`);
      if (!started && (msg.includes('Uvicorn running') || msg.includes('Application startup complete') || msg.includes('Started server') || msg.includes('HITS Web Server starting'))) {
        started = true;
        resolve();
      }
    });

    backendProc.on('error', (err) => {
      console.error('Backend error:', err.message);
      if (!started) reject(err);
    });

    backendProc.on('close', (code) => {
      if (code && code !== 0 && !started) {
        reject(new Error(`Backend exited with code ${code}`));
      }
    });

    // Fallback: if no startup message within 5s, assume it's running
    setTimeout(() => {
      if (!started) {
        started = true;
        resolve();
      }
    }, 5000);
  });
}

function stopBackend() {
  if (backendProc && !backendProc.killed) {
    console.log('Stopping backend...');
    backendProc.kill('SIGTERM');
    backendProc = null;
  }
}

// ─── Express Server ─────────────────────────────────────────────

export async function startServer({ port, dev = false, setupOnly = false }) {
  // 1. Setup Python
  await setupPython();

  if (setupOnly) {
    console.log('Setup complete. Run "npx hits" to start.');
    return;
  }

  // 2. Check frontend
  const distDir = join(ROOT, 'hits_web', 'dist');
  if (!existsSync(join(distDir, 'index.html'))) {
    console.error('Error: Frontend not built.');
    console.error('Run: cd hits_web && npm install && npm run build');
    process.exit(1);
  }

  // 3. Start Python backend
  await startBackend(dev);

  // 4. Start Express
  const app = express();

  // API proxy → Python FastAPI
  // http-proxy-middleware v3: app.use('/api', ...) strips /api prefix.
  // We need to add it back since FastAPI routes are registered with /api prefix.
  app.use('/api', createProxyMiddleware({
    target: `http://127.0.0.1:${API_PORT}`,
    changeOrigin: true,
    pathRewrite: (path) => '/api' + path,
    logger: dev ? console : undefined,
  }));

  // Static files
  app.use(express.static(distDir));

  // SPA fallback
  app.get('*', (req, res) => {
    const indexPath = join(distDir, 'index.html');
    res.sendFile(indexPath);
  });

  const server = app.listen(port, () => {
    console.log('');
    console.log(`  🌳 HITS Web Server`);
    console.log(`  ${'─'.repeat(30)}`);
    console.log(`  Local:   http://127.0.0.1:${port}`);
    console.log(`  API:     http://127.0.0.1:${API_PORT}`);
    if (dev) console.log(`  Mode:    development`);
    console.log('');
    console.log('  Press Ctrl+C to stop');
    console.log('');
  });

  // Graceful shutdown
  const shutdown = () => {
    console.log('\nShutting down...');
    stopBackend();
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 3000);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}
