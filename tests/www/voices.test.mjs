/* The single-voice rule of the voice selects: www/js/app.js publishes
   $soleVoice, and the Studio and the settings dialog offer only "default"
   for an engine whose one voice is its default. app.js runs with stand-ins
   that absorb every call, so only the helpers it puts on Vue.prototype are
   real. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/* Anything app.js touches at load (Vuex, the router, axios, window,
   document) answers with another stand-in, never throws. */
const standIn = function () {
  return new Proxy(function () {}, {
    get: (target, key) => (key === 'then' ? undefined : standIn()),
    apply: () => standIn(),
    construct: () => standIn(),
  });
};

const loadHelpers = function () {
  const proto = {};
  const Vue = new Proxy(function () {}, {
    get: (target, key) => (key === 'prototype' ? proto : standIn()),
    construct: () => standIn(),
  });
  const sandbox = {
    Vue, Vuex: standIn(), VueRouter: standIn(), axios: standIn(), httpVueLoader: standIn(),
    numeral: standIn(), window: standIn(), document: standIn(),
  };
  const file = path.join(ROOT, 'www', 'js', 'app.js');
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), sandbox, { filename: file });
  return proto;
};

const loadComponent = function (name) {
  const file = path.join(ROOT, 'www', 'views', name);
  const body = fs.readFileSync(file, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
  const sandbox = { module: { exports: {} }, window: {}, TtsWait: { methods: {} } };
  vm.runInNewContext(body, sandbox, { filename: file });
  return sandbox.module.exports;
};

const helpers = loadHelpers();

test('$soleVoice names the one voice only when it is the default', () => {
  const sole = helpers.$soleVoice;
  assert.equal(sole({ voices: ['maria'], default: 'maria' }), 'maria');
  assert.equal(sole({ voices: ['anna'], default: 'maria' }), '');
  assert.equal(sole({ voices: ['maria', 'anna'], default: 'maria' }), '');
  assert.equal(sole({ voices: ['af_bella'], default: 'af_bella', mix: true }), '');
  assert.equal(sole({ voices: [], default: '' }), '');
  assert.equal(sole(null), '');
});

for (const name of ['Studio.vue', 'Settings.vue']) {
  test(`${name}: an engine whose one voice is its default offers only "default"`, () => {
    const computed = loadComponent(name).computed;
    const view = { form: { voice: 'maria' }, voices: ['maria'], soleVoice: 'maria' };
    // Compared by length: the empty list is made inside the sandbox, a different realm.
    assert.equal(computed.voiceChoices.call(view).length, 0);
    assert.equal(computed.voicePick.get.call(view), '');
    computed.voicePick.set.call(view, '');
    assert.equal(view.form.voice, '');
  });

  test(`${name}: an engine with other voices keeps them all`, () => {
    const computed = loadComponent(name).computed;
    const view = { form: { voice: 'anna' }, voices: ['anna', 'maria'], soleVoice: '' };
    assert.deepEqual(computed.voiceChoices.call(view), ['anna', 'maria']);
    assert.equal(computed.voicePick.get.call(view), 'anna');
  });
}
