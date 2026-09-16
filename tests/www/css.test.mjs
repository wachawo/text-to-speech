/* www/css/main.css keeps to its own rule: every colour lives in the two
   palette blocks on :root, and no rule below them paints a literal. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const SOURCE = path.join(ROOT, 'www', 'css', 'main.css');

const stripComments = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');

/* The text of the file outside every `:root ... { ... }` block. Blocks in
   this file do not nest, so the first closing brace after a :root selector
   ends it. */
const outsideRoot = function (css) {
  return css.replace(/:root[^{]*\{[^}]*\}/g, '');
};

const HEX = /#[0-9a-fA-F]{3,8}(?![\w-])/g;

test('main.css has its two palette blocks', () => {
  const css = stripComments(fs.readFileSync(SOURCE, 'utf8'));
  assert.match(css, /:root\s*\{[^}]*--tts-primary:\s*#[0-9a-fA-F]{6}/, 'light palette');
  assert.match(css, /:root\[data-theme="dark"\]\s*\{[^}]*--tts-primary:\s*#[0-9a-fA-F]{6}/, 'dark palette');
});

test('main.css paints no literal hex colour outside the :root blocks', () => {
  const css = stripComments(fs.readFileSync(SOURCE, 'utf8'));
  const rest = outsideRoot(css);
  const lines = rest.split('\n');
  const hits = [];
  lines.forEach((line, index) => {
    const found = line.match(HEX);
    if (found) hits.push(`${index + 1}: ${line.trim()} (${found.join(', ')})`);
  });
  assert.deepEqual(hits, [], 'literal colours outside :root:\n' + hits.join('\n'));
});
