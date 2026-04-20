#!/usr/bin/env node

/**
 * HITS CLI - starts the web server or resumes work.
 *
 * Usage:
 *   npx hits            → start production server
 *   npx hits --dev       → start in development mode
 *   npx hits --setup     → install Python deps + build frontend
 *   npx hits resume      → resume work on current project
 *   npx hits resume -l   → list all projects with checkpoints
 *   npx hits resume -p /path --token-budget 1000
 *   npx hits --port 9000 → use custom port
 *   npx hits --help
 */

import { parseArgs } from 'node:util';
import { startServer } from '../server.js';
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { platform } from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const isWin = platform() === 'win32';

// Detect Python
function findPython() {
  const envPython = process.env.HITS_PYTHON;
  if (envPython && existsSync(envPython)) return envPython;
  const candidates = isWin ? ['python', 'python3', 'py'] : ['python3', 'python'];
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

const PYTHON_BIN = isWin
  ? join(ROOT, 'venv', 'Scripts', 'python.exe')
  : join(ROOT, 'venv', 'bin', 'python');

// Check if first arg is 'resume' or 'connect' subcommand
const firstArg = process.argv[2];

// ── connect subcommand ──────────────────────────────────────
if (firstArg === 'connect') {
  const connectArgs = process.argv.slice(3);
  if (connectArgs.length === 0 || connectArgs.includes('--help') || connectArgs.includes('-h')) {
    console.log(`
HITS Connect — Connect HITS to your AI tools

Usage:
  npx @purpleraven/hits connect <tool>     Connect to a specific tool
  npx @purpleraven/hits connect --all      Connect to all detected tools
  npx @purpleraven/hits connect --status   Show connection status

Tools:
  claude        Configure Claude Code (hooks + MCP)
  opencode      Configure OpenCode (MCP server)

Examples:
  npx @purpleraven/hits connect claude     # Set up Claude Code hooks
  npx @purpleraven/hits connect opencode   # Register MCP in OpenCode
  npx @purpleraven/hits connect --all      # Everything
  npx @purpleraven/hits connect --status   # Check what's connected
`);
    process.exit(0);
  }

  // Run postinstall.cjs with the right flags
  const postinstallPath = join(ROOT, 'postinstall.cjs');
  let flag = '';
  if (connectArgs.includes('--all')) flag = '--all';
  else if (connectArgs.includes('--status')) flag = '--status';
  else if (connectArgs[0] === 'claude') flag = '--claude';
  else if (connectArgs[0] === 'opencode') flag = '--opencode';
  else {
    console.error(`Unknown tool: ${connectArgs[0]}. Use 'claude', 'opencode', '--all', or '--status'.`);
    process.exit(1);
  }

  try {
    execSync(`node ${postinstallPath} ${flag}`, { cwd: ROOT, stdio: 'inherit' });
  } catch (err) {
    console.error('Failed to connect. See errors above.');
    process.exit(1);
  }
  process.exit(0);
}

// ── resume subcommand ───────────────────────────────────────
if (firstArg === 'resume') {
  // Parse resume-specific args
  const resumeArgs = process.argv.slice(3);
  let projectPath = null;
  let listMode = false;
  let tokenBudget = 2000;

  for (let i = 0; i < resumeArgs.length; i++) {
    const arg = resumeArgs[i];
    if (arg === '-l' || arg === '--list') listMode = true;
    else if ((arg === '-p' || arg === '--project') && resumeArgs[i + 1]) projectPath = resumeArgs[++i];
    else if ((arg === '-t' || arg === '--token-budget') && resumeArgs[i + 1]) tokenBudget = parseInt(resumeArgs[++i]);
    else if (arg === '--help' || arg === '-h') {
      console.log(`
HITS Resume - Resume work on a project

Usage:
  npx @purpleraven/hits resume [options]

Options:
  -p, --project <path>    Project path (default: auto-detect from CWD)
  -l, --list              List all projects with checkpoints
  -t, --token-budget <n>  Token budget for output (default: 2000)
  -h, --help              Show this help

Examples:
  npx @purpleraven/hits resume           # Resume current project
  npx @purpleraven/hits resume -l        # List all projects
  npx @purpleraven/hits resume -p /src   # Resume specific project
`);
      process.exit(0);
    }
  }

  // Find or create venv
  const pythonCmd = findPython();
  if (!pythonCmd) {
    console.error('Error: Python 3.10+ not found.');
    process.exit(1);
  }

  if (!existsSync(PYTHON_BIN)) {
    console.error('Setting up HITS... (first run)');
    execSync(`${pythonCmd} -m venv ${join(ROOT, 'venv')}`, { cwd: ROOT, stdio: 'inherit' });
  }

  // Ensure deps — use requirements.txt since npm package may lack pyproject.toml
  try {
    execSync(`${PYTHON_BIN} -c "import pydantic, fastapi"`, { stdio: 'ignore' });
  } catch {
    console.error('Installing Python dependencies...');
    execSync(`${PYTHON_BIN} -m pip install -q --upgrade pip`, { cwd: ROOT, stdio: 'inherit' });
    execSync(`${PYTHON_BIN} -m pip install -q -r ${join(ROOT, 'requirements.txt')}`, { cwd: ROOT, stdio: 'inherit' });
  }

  // Build resume args
  const pyArgs = ['-m', 'hits_core.cli', 'resume'];
  if (listMode) pyArgs.push('--list');
  if (projectPath) pyArgs.push('--project', projectPath);
  if (tokenBudget) pyArgs.push('--token-budget', String(tokenBudget));

  // Execute resume command with PYTHONPATH set to package root
  const result = execSync(`${PYTHON_BIN} ${pyArgs.join(' ')}`, {
    cwd: ROOT,
    encoding: 'utf-8',
    env: { ...process.env, PYTHONPATH: ROOT },
    stdio: 'inherit',
  });
  process.exit(0);
}

// Default: start server
const { values } = parseArgs({
  options: {
    port:   { type: 'string', short: 'p' },
    dev:    { type: 'boolean', short: 'd', default: false },
    setup:  { type: 'boolean', short: 's', default: false },
    help:   { type: 'boolean', short: 'h', default: false },
  },
  strict: true,
});

if (values.help) {
  console.log(`
HITS - Hybrid Intel Trace System

Usage:
  npx @purpleraven/hits [options]
  npx @purpleraven/hits resume [options]
  npx @purpleraven/hits connect <tool>

Server Options:
  -p, --port <port>   Server port (default: 8765)
  -d, --dev           Development mode (verbose logging)
  -s, --setup         Install dependencies only
  -h, --help          Show this help

Resume:
  npx @purpleraven/hits resume           Resume current project
  npx @purpleraven/hits resume -l        List all projects
  npx @purpleraven/hits resume -p /path  Resume specific project

Connect:
  npx @purpleraven/hits connect claude   Configure Claude Code
  npx @purpleraven/hits connect opencode Configure OpenCode
  npx @purpleraven/hits connect --all    Connect all tools
  npx @purpleraven/hits connect --status Show connection status

Environment:
  HITS_PORT           Server port override
  HITS_PYTHON         Path to python executable (default: auto-detect)
`);
  process.exit(0);
}

const port = parseInt(values.port || process.env.HITS_PORT || '8765', 10);

startServer({
  port,
  dev: values.dev,
  setupOnly: values.setup,
}).catch((err) => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
