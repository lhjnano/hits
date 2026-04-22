#!/usr/bin/env node

/**
 * HITS MCP Server - Node.js Wrapper
 *
 * Launches the HITS Python MCP server over stdio transport.
 * Auto-detects Python, creates venv, installs deps — same as `npx hits`.
 *
 * Usage:
 *   npx hits-mcp
 *
 * Or in MCP config:
 *   { "command": ["npx", "hits-mcp"] }
 *
 * Environment:
 *   HITS_PYTHON       Path to python executable (default: auto-detect)
 *   HITS_DATA_PATH    Data storage path (default: ~/.hits/data)
 */

import { spawn, execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { platform } from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const isWin = platform() === 'win32';

// ─── Python Detection (same logic as server.js) ────────────────

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

function runCommand(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    // CRITICAL: Use 'pipe' for stdin to prevent child processes from
    // consuming MCP protocol messages that Claude Code has already written.
    // Only stdout/stderr are inherited for logging visibility.
    const proc = spawn(cmd, args, { stdio: ['pipe', 'inherit', 'inherit'], ...opts });
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Command failed: ${cmd} ${args.join(' ')} (exit ${code})`));
    });
    proc.on('error', reject);
  });
}

async function ensurePython() {
  const pythonCmd = findPython();
  if (!pythonCmd) {
    console.error('[hits-mcp] Error: Python 3.10+ not found.');
    console.error('[hits-mcp] Install: https://www.python.org/downloads/');
    process.exit(1);
  }

  // Create venv if needed
  if (!existsSync(PYTHON_BIN)) {
    console.error(`[hits-mcp] Creating virtual environment... (${pythonCmd})`);
    await runCommand(pythonCmd, ['-m', 'venv', VENV_DIR], { cwd: ROOT });
  }

  // Check if minimal MCP deps are installed (only pydantic is needed for MCP server)
  try {
    execSync(
      `${PYTHON_BIN} -c "import pydantic"`,
      { stdio: 'ignore' }
    );
  } catch {
    console.error('[hits-mcp] Installing MCP dependencies (pydantic)...');
    // Use minimal requirements for MCP server, NOT the full web server deps
    const mcpReqs = join(ROOT, 'requirements-mcp.txt');
    const reqFile = existsSync(mcpReqs) ? mcpReqs : join(ROOT, 'requirements-core.txt');
    await runCommand(PYTHON_BIN, ['-m', 'pip', 'install', '-q', '-r', reqFile], { cwd: ROOT });
    console.error('[hits-mcp] Dependencies installed.');
  }
}

// ─── Launch MCP Server ──────────────────────────────────────────

async function main() {
  await ensurePython();

  // Spawn Python MCP server with stdio transport
  // stdin/stdout MUST be 'inherit' for MCP JSON-RPC communication.
  // stderr is inherited for Python error/logging output.
  const proc = spawn(PYTHON_BIN, ['-m', 'hits_core.mcp.server'], {
    cwd: ROOT,
    stdio: ['inherit', 'inherit', 'inherit'],
    env: {
      ...process.env,
      PYTHONPATH: ROOT,
    },
  });

  proc.on('error', (err) => {
    console.error(`[hits-mcp] Failed to start: ${err.message}`);
    process.exit(1);
  });

  proc.on('exit', (code, signal) => {
    if (signal) {
      console.error(`[hits-mcp] Terminated by signal: ${signal}`);
    }
    process.exit(code || 0);
  });

  // Forward signals
  process.on('SIGINT', () => proc.kill('SIGINT'));
  process.on('SIGTERM', () => proc.kill('SIGTERM'));
}

main().catch((err) => {
  console.error(`[hits-mcp] Fatal: ${err.message}`);
  process.exit(1);
});
