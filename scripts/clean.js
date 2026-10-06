// scripts/clean.js
// Recursively cleans build artifacts and bytecode caches.
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const targets = [
  path.join(root, 'web', '.next'),
  path.join(root, 'web', 'out'),
  path.join(root, '.pytest_cache'),
  path.join(root, 'dist'),
  path.join(root, 'build'),
];

function deleteFolderRecursive(dirPath) {
  if (fs.existsSync(dirPath)) {
    try {
      fs.rmSync(dirPath, { recursive: true, force: true });
      console.log('[clean] Removed directory: ' + path.relative(root, dirPath));
    } catch (e) {
      console.warn('[clean] Warning removing ' + dirPath + ': ' + e.message);
    }
  }
}

function cleanPycache(dir) {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '__pycache__' || entry.name === '.pytest_cache') {
        deleteFolderRecursive(full);
      } else if (entry.name !== 'node_modules' && entry.name !== '.git') {
        cleanPycache(full);
      }
    }
  }
}

console.log('[clean] Starting AgriMind project cleanup...');
for (const t of targets) {
  deleteFolderRecursive(t);
}
cleanPycache(root);
console.log('[clean] Cleanup completed.');
