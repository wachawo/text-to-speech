/* Behaviour of the screens, one method or watcher at a time: each is called
   against a bare object standing in for the component instance, with only
   the fields that method reads. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

const loadComponent = function (name) {
  const file = path.join(ROOT, 'www', 'views', name);
  const body = fs.readFileSync(file, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
  const sandbox = { module: { exports: {} }, window: {}, TtsWait: { methods: {} } };
  vm.runInNewContext(body, sandbox, { filename: file });
  return sandbox.module.exports;
};

const LANGUAGES = ['en', 'ru'];
const knownLanguage = (code) => LANGUAGES.indexOf(code) !== -1;

/* Lets the promise chains of a method run to their end. */
const settle = () => new Promise((resolve) => setImmediate(resolve));

test('Studio.vue: a server the store has seen ok opens ready, with no warm-up bar', () => {
  const data = loadComponent('Studio.vue').data;
  const seen = data.call({ $store: { state: { health: { status: 'ok' } } } });
  assert.equal(seen.ready, true);
  assert.equal(seen.info, '');
  const unseen = data.call({ $store: { state: { health: null } } });
  assert.equal(unseen.ready, false);
  assert.notEqual(unseen.info, '');
});

test('Studio.vue: the health poll publishes whether the server wants a token', async () => {
  const pollHealth = loadComponent('Studio.vue').methods.pollHealth;
  const state = { health: null, auth: { required: null, token: 'abc' } };
  const view = {
    $store: { state },
    $http: { get: () => Promise.resolve({ data: { status: 'ok', auth: true } }) },
    $apiError: (err) => String(err),
    info: '', healthError: '', healthTimer: null, ready: false,
    form: { engine: 'gtts' }, items: [1], wait: [],
    fetchEngines() {}, fetchHistory() {},
  };
  pollHealth.call(view);
  await settle();
  assert.equal(view.ready, true);
  assert.equal(state.auth.required, true);
  assert.equal(state.auth.token, 'abc', 'the token is kept');
});

test('Studio.vue: a SAVE back to "default" keeps the language when the server default has no option', () => {
  const watcher = loadComponent('Studio.vue').watch['$store.state.studio'];
  const view = {
    settled: true,
    engines: ['gtts'], serverEngine: 'gtts', serverLanguage: 'uk',
    form: { engine: 'gtts', language: 'en', voice: '' },
    $knownLanguage: knownLanguage,
    voiceKnown: () => true,
  };
  watcher.call(view, { engine: '', language: '', voice: '' });
  assert.equal(view.form.language, 'en');
  watcher.call(view, { engine: '', language: 'ru', voice: '' });
  assert.equal(view.form.language, 'ru', 'a known language still applies');
});

test('Settings.vue: the voices are asked for only while the dialog is open', () => {
  const watcher = loadComponent('Settings.vue').watch.voiceKey;
  let asked = 0;
  const view = { $store: { state: { settingsOpen: false } }, fetchVoices() { asked += 1; } };
  watcher.call(view);
  assert.equal(asked, 0, 'closed: no request');
  view.$store.state.settingsOpen = true;
  watcher.call(view);
  assert.equal(asked, 1, 'open: one request');
});

test('Settings.vue: a storage refusal is a short label with the reason as its title', () => {
  const saveStudio = loadComponent('Settings.vue').methods.saveStudio;
  const view = { form: { engine: '', language: '', voice: '' }, $savePrefs: () => false };
  saveStudio.call(view);
  assert.equal(view.noteFailed, true);
  assert.ok(view.note.split(' ').length <= 3, view.note);
  assert.ok(view.noteTitle, 'the reason is on the title');
});

test('Voices.vue: switching rows silences the sample that was playing', () => {
  const togglePlay = loadComponent('Voices.vue').methods.togglePlay;
  let paused = 0;
  const view = {
    player: { pause() { paused += 1; } },
    playing: 'anna',
    // The next sample never arrives: the old one must already be quiet.
    fetchSample: () => new Promise(() => {}),
  };
  togglePlay.call(view, 'maria');
  assert.equal(view.playing, 'maria');
  assert.equal(paused, 1);
});

test('Voices.vue: a silent take adds one word to the note, not the cause', () => {
  const takeNote = loadComponent('Voices.vue').computed.takeNote;
  const view = {
    take: { size: 1000 }, takeSeconds: 1, takeSilent: true,
    $fmtSeconds: (value) => value + ' s', $fmtBytes: (value) => value + ' B',
  };
  assert.equal(takeNote.call(view), 'Recorded 1 s, 22050 Hz mono, 1000 B - silent');
});
