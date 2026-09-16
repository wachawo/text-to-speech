/* Every screen under www/views compiles, and every script under www/js
   parses - the checks a build step would have done, run without one. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { compile } = require('vue-template-compiler');

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const VIEWS = path.join(ROOT, 'www', 'views');
const SCRIPTS = path.join(ROOT, 'www', 'js');

const views = fs.readdirSync(VIEWS).filter((name) => name.endsWith('.vue')).sort();
const scripts = fs.readdirSync(SCRIPTS).filter((name) => name.endsWith('.js')).sort();

/* The outermost <template> of a single-file component: from the first
   opening tag to the last closing one before <script>, so the nested
   <template v-if> blocks inside stay where they are. */
const templateOf = function (source) {
  const match = source.match(/<template>([\s\S]*)<\/template>\s*<script>/);
  return match ? match[1] : null;
};

const scriptOf = function (source) {
  const match = source.match(/<script>([\s\S]*?)<\/script>/);
  return match ? match[1] : null;
};

/* The script body the way httpVueLoader runs it: a plain script with
   `module` in scope and `module.exports` as the component. The wait-queue
   mixin app.js publishes on window is stood in for, so `mixins: [TtsWait]`
   resolves. */
const loadComponent = function (body, filename) {
  const sandbox = { module: { exports: {} }, window: {}, TtsWait: { methods: {} } };
  vm.runInNewContext(body, sandbox, { filename });
  return sandbox.module.exports;
};

assert.ok(views.length > 0, 'no .vue files found');
assert.ok(scripts.length > 0, 'no .js files found');

for (const name of views) {
  const file = path.join(VIEWS, name);
  const source = fs.readFileSync(file, 'utf8');

  test(`${name}: template compiles`, () => {
    const template = templateOf(source);
    assert.ok(template, 'no <template> block');
    const result = compile(template);
    assert.deepEqual(result.errors, [], result.errors.join('\n'));
  });

  test(`${name}: script parses and exports a component`, () => {
    const body = scriptOf(source);
    assert.ok(body, 'no <script> block');
    assert.doesNotThrow(() => new vm.Script(body, { filename: file }));
    const component = loadComponent(body, file);
    assert.equal(typeof component, 'object');
    assert.ok(component !== null);
    const shape = ['name', 'data', 'methods', 'props', 'computed'].some((key) => key in component);
    assert.ok(shape, 'module.exports has none of name, data, methods, props, computed');
    if (component.data) assert.equal(typeof component.data, 'function', 'data must be a function');
  });
}

for (const name of scripts) {
  const file = path.join(SCRIPTS, name);
  test(`js/${name}: parses`, () => {
    assert.doesNotThrow(() => new vm.Script(fs.readFileSync(file, 'utf8'), { filename: file }));
  });
}
