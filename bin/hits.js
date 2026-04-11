#!/usr/bin/env node

/**
 * HITS CLI - starts the web server.
 *
 * Usage:
 *   npx hits            → start production server
 *   npx hits --dev       → start in development mode
 *   npx hits --setup     → install Python deps + build frontend
 *   npx hits --port 9000 → use custom port
 *   npx hits --help
 */

import { parseArgs } from 'node:util';
import { startServer } from '../server.js';

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
  npx hits [options]

Options:
  -p, --port <port>   Server port (default: 8765)
  -d, --dev           Development mode (verbose logging)
  -s, --setup         Install dependencies only
  -h, --help          Show this help

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
