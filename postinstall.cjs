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

  // Only configure if OpenCode is already installed
  if (!fs.existsSync(OPENCODE_DIR)) {
    log('  ↩ OpenCode not detected, skipping');
    return false;
  }

  log('');
  log('Configuring OpenCode...');

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

  // Check if already registered
  if (config.mcp['hits']) {
    log('  ↩ hits MCP already registered in OpenCode');
    return true;
  }

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

  // Only configure if Claude Code is already installed
  if (!fs.existsSync(CLAUDE_DIR)) {
    log('  ↩ Claude Code not detected, skipping');
    return false;
  }

  if (!fs.existsSync(hooksSrc)) {
    log('⚠  hooks/ directory not found, skipping Claude Code setup');
    return false;
  }

  log('');
  log('Configuring Claude Code...');

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
    entry => entry.hooks && entry.hooks.some(
      h => h.command && h.command.includes('claude_signal_watcher')
    )
  );

  if (!alreadyRegistered) {
    settings.hooks.SessionStart.push({
      matcher: '',
      hooks: [
        {
          type: 'command',
          command: hookCommand,
        }
      ],
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

  // Determine which tools to configure
  // Usage: node postinstall.cjs [--claude] [--opencode] [--all] [--status]
  const args = process.argv.slice(2);
  const wantClaude = args.includes('--claude');
  const wantOpenCode = args.includes('--opencode');
  const wantAll = args.includes('--all');
  const wantStatus = args.includes('--status');
  const isAutoInstall = !wantClaude && !wantOpenCode && !wantAll && !wantStatus;

  // --status: just print current state and exit
  if (wantStatus) {
    console.log('');
    console.log('HITS Connection Status');
    console.log('─'.repeat(30));
    const claudeDir = path.join(HOME, '.claude');
    const claudeSettings = path.join(claudeDir, 'settings.json');
    const opencodeDir = path.join(HOME, '.config', 'opencode');
    const opencodeConfig = path.join(opencodeDir, 'opencode.json');

    // Claude Code
    let claudeConnected = false;
    if (fs.existsSync(claudeSettings)) {
      try {
        const s = JSON.parse(fs.readFileSync(claudeSettings, 'utf8'));
        claudeConnected = s.hooks && s.hooks.SessionStart &&
          s.hooks.SessionStart.some(entry => entry.hooks && entry.hooks.some(
            h => h.command && h.command.includes('claude_signal_watcher')
          ));
      } catch {}
    }
    console.log(`  Claude Code:  ${claudeConnected ? '✅ connected' : '❌ not connected'}`);
    if (fs.existsSync(path.join(claudeDir, 'hooks', 'claude_signal_watcher.sh'))) {
      console.log(`                hook script installed`);
    }

    // OpenCode
    let opencodeConnected = false;
    if (fs.existsSync(opencodeConfig)) {
      try {
        const c = JSON.parse(fs.readFileSync(opencodeConfig, 'utf8'));
        opencodeConnected = c.mcp && c.mcp['hits'];
      } catch {}
    }
    console.log(`  OpenCode:     ${opencodeConnected ? '✅ connected' : '❌ not connected'}`);

    // MCP
    console.log(`  MCP Server:   npx -y -p @purpleraven/hits hits-mcp`);
    console.log('');
    return { claudeConnected, opencodeConnected };
  }

  // Auto-install (postinstall): only configure detected tools
  const doClaude = wantClaude || wantAll || isAutoInstall;
  const doOpenCode = wantOpenCode || wantAll || isAutoInstall;

  console.log('');
  console.log('╔══════════════════════════════════════╗');
  console.log('║   HITS — Setup                        ║');
  console.log('╚══════════════════════════════════════╝');

  ensureHitsDataDir();
  const hasOpenCode = doOpenCode ? installOpenCode() : false;
  const hasClaude = doClaude ? installClaudeCode() : false;

  console.log('');
  if (hasClaude || hasOpenCode) {
    console.log('Done! Restart your AI tool to activate.');
  } else if (isAutoInstall) {
    console.log('Data directory created at ~/.hits/data/');
    console.log('No AI tools detected — connect manually with:');
    console.log('  npx @purpleraven/hits connect claude');
    console.log('  npx @purpleraven/hits connect opencode');
    console.log('  npx @purpleraven/hits connect --all');
  } else {
    console.log('No changes made.');
  }
  console.log('');
}

main();
