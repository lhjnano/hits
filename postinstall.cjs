#!/usr/bin/env node

/**
 * HITS — Post-Install Script
 *
 * Automatically installs hooks and MCP config after npm install.
 *
 * What it does:
 *   OpenCode → ~/.config/opencode/
 *     - opencode.json MCP entry (hits-mcp)
 *
 *   Claude Code → ~/.claude/
 *     - hooks/claude_signal_watcher.sh (SessionStart)
 *
 *   Shared → ~/.hits/
 *     - hooks/opencode_signal_watcher.sh
 *
 * Usage:
 *   npx @purpleraven/hits --install
 *   (Also runs automatically on npm postinstall)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const HOME = os.homedir();
// __dirname is the directory of this script (postinstall.cjs)
// In npm package: <package-root>/postinstall.cjs
// Hooks are at:    <package-root>/hooks/
const ROOT = __dirname;

// ── Helpers ──────────────────────────────────────────────────

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyFile(src, dest) {
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
}

function copyDir(src, dest) {
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function log(msg) {
  console.log(`  ${msg}`);
}

// ── OpenCode MCP Config ──────────────────────────────────────

function installOpenCode() {
  const OPENCODE_DIR = path.join(HOME, '.config', 'opencode');
  const configFile = path.join(OPENCODE_DIR, 'opencode.json');

  log('');
  log('Installing OpenCode components...');

  // Read or create config
  let config = {};
  if (fs.existsSync(configFile)) {
    try {
      config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
    } catch {
      config = { $schema: 'https://opencode.ai/config.json' };
    }
  } else {
    config = { $schema: 'https://opencode.ai/config.json', mcp: {} };
  }
  if (!config.mcp) config.mcp = {};

  // Add hits MCP server
  config.mcp['hits'] = {
    type: 'local',
    command: ['npx', 'hits-mcp'],
    enabled: true,
  };

  // Backup before overwrite
  if (fs.existsSync(configFile)) {
    const backup = configFile + `.backup.${Date.now()}`;
    fs.copyFileSync(configFile, backup);
  }

  ensureDir(path.dirname(configFile));
  fs.writeFileSync(configFile, JSON.stringify(config, null, 2));
  log('  ✓ opencode.json updated (hits MCP server registered)');

  log('');
  log(`✓ OpenCode configured`);
  return true;
}

// ── Claude Code Hooks ────────────────────────────────────────

function installClaudeCode() {
  const CLAUDE_DIR = path.join(HOME, '.claude');
  const hooksSrc = path.join(ROOT, 'hooks');

  if (!fs.existsSync(hooksSrc)) {
    log('⚠  hooks/ directory not found, skipping Claude Code setup');
    return false;
  }

  log('');
  log('Installing Claude Code hooks...');

  // Copy claude_signal_watcher.sh
  const claudeHook = path.join(hooksSrc, 'claude_signal_watcher.sh');
  if (fs.existsSync(claudeHook)) {
    const dest = path.join(CLAUDE_DIR, 'hooks', 'claude_signal_watcher.sh');
    copyFile(claudeHook, dest);
    fs.chmodSync(dest, 0o755);
    log('  ✓ hooks/claude_signal_watcher.sh');
  }

  // Update Claude Code settings.json to register the hook
  const settingsFile = path.join(CLAUDE_DIR, 'settings.json');
  let settings = {};
  if (fs.existsSync(settingsFile)) {
    try {
      settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'));
    } catch {
      settings = {};
    }
  }
  if (!settings.hooks) settings.hooks = {};
  if (!settings.hooks.SessionStart) settings.hooks.SessionStart = [];

  const hookCommand = `bash ${path.join(CLAUDE_DIR, 'hooks', 'claude_signal_watcher.sh')}`;
  const alreadyRegistered = settings.hooks.SessionStart.some(
    h => h.command && h.command.includes('claude_signal_watcher')
  );

  if (!alreadyRegistered) {
    settings.hooks.SessionStart.push({
      type: 'command',
      command: hookCommand,
    });

    if (fs.existsSync(settingsFile)) {
      fs.copyFileSync(settingsFile, settingsFile + `.backup.${Date.now()}`);
    }

    ensureDir(path.dirname(settingsFile));
    fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2));
    log('  ✓ settings.json updated (SessionStart hook registered)');
  } else {
    log('  ↩ SessionStart hook already registered');
  }

  log('');
  log(`✓ Claude Code hooks installed`);
  return true;
}

// ── HITS Data Directory ──────────────────────────────────────

function ensureHitsDataDir() {
  const hitsDir = path.join(HOME, '.hits', 'data');
  const subdirs = [
    'work_logs', 'trees', 'workflows',
    'signals/pending', 'signals/consumed',
  ];

  for (const sub of subdirs) {
    ensureDir(path.join(hitsDir, sub));
  }

  // Copy opencode hook to ~/.hits/hooks/ for project-level use
  const opencodeHook = path.join(ROOT, 'hooks', 'opencode_signal_watcher.sh');
  if (fs.existsSync(opencodeHook)) {
    const dest = path.join(HOME, '.hits', 'hooks', 'opencode_signal_watcher.sh');
    copyFile(opencodeHook, dest);
    fs.chmodSync(dest, 0o755);
    log('  ✓ hooks/opencode_signal_watcher.sh → ~/.hits/hooks/');
  }

  log('  ✓ ~/.hits/data/ directory structure created');
}

// ── Main ─────────────────────────────────────────────────────

function main() {
  if (process.env.HITS_SKIP_INSTALL === '1') {
    log('HITS_SKIP_INSTALL=1, skipping component installation');
    return;
  }

  const isExplicit = process.argv.includes('--install') || process.argv.includes('--setup');
  const isCI = process.env.CI || process.env.CONTINUOUS_INTEGRATION;

  if (isCI && !isExplicit) {
    log('CI environment detected, skipping component installation');
    return;
  }

  console.log('');
  console.log('╔══════════════════════════════════════╗');
  console.log('║   HITS — Component Installer         ║');
  console.log('╚══════════════════════════════════════╝');

  ensureHitsDataDir();
  installOpenCode();
  installClaudeCode();

  console.log('');
  console.log('Done! Restart OpenCode or Claude Code to activate.');
  console.log('');
}

main();
