/* The pure helpers www/js/app.js puts on Vue.prototype: the sign-in
   redirect guard, the voice check and the error sentence. app.js runs with
   stand-ins that absorb every call, so only those helpers are real. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/* Anything app.js touches at load answers with another stand-in, never throws. */
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

const helpers = loadHelpers();

test('$internalPath keeps a path of this app and drops everything else', () => {
  const internal = helpers.$internalPath;
  assert.equal(internal('/voices'), '/voices');
  assert.equal(internal('/history?page=2'), '/history?page=2');
  // "//host" is an absolute URL to a browser: an open redirect after sign-in.
  assert.equal(internal('//evil.example/x'), '');
  assert.equal(internal('https://evil.example/'), '');
  assert.equal(internal('voices'), '');
  assert.equal(internal('/'), '');
  assert.equal(internal('/login'), '');
  assert.equal(internal('/login?next=/voices'), '');
  assert.equal(internal(undefined), '');
  assert.equal(internal(['/voices']), '');
});

test('$knownVoice accepts the default, a listed voice and, when the engine mixes, a mix of listed voices', () => {
  const known = helpers.$knownVoice;
  const voices = ['af_bella', 'af_sky'];
  assert.equal(known('', voices, false), true);
  assert.equal(known('af_bella', voices, false), true);
  assert.equal(known('am_adam', voices, false), false);
  assert.equal(known('af_bella+af_sky', voices, false), false);
  assert.equal(known('af_bella(2)+af_sky(1)', voices, true), true);
  assert.equal(known('af_bella + af_sky', voices, true), true);
  assert.equal(known('af_bella(2)+am_adam(1)', voices, true), false);
});

test('$apiError prefers the message, adds the request id and falls back to the status line', () => {
  const error = helpers.$apiError;
  const response = (data, status = 400, statusText = 'Bad Request') => ({ response: { data, status, statusText } });
  assert.equal(
    error(response({ error: 'ValidationError', message: 'Unknown voice', request_id: 'abc' })),
    'Unknown voice (request abc)',
  );
  assert.equal(error(response({ error: 'Not Found' }, 404, 'NOT FOUND')), 'Not Found');
  assert.equal(error(response({ error: { message: 'x' } })), '{"message":"x"}');
  assert.equal(error(response('plain sentence', 502, 'Bad Gateway')), 'plain sentence');
  assert.equal(error(response('<html>proxy</html>', 502, 'Bad Gateway')), '502 Bad Gateway');
  assert.equal(error({ message: 'Network Error' }), 'Network Error');
  assert.equal(error(null), 'The request failed');
});
