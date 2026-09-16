/* www/js/recorder.js: the pure parts - the WAV encoder and the resampler -
   loaded the way the browser loads them (a plain script that publishes
   window.TtsRecorder), with a bare object standing in for window. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const SOURCE = path.join(ROOT, 'www', 'js', 'recorder.js');

const loadRecorder = function () {
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(SOURCE, 'utf8'), sandbox, { filename: SOURCE });
  return sandbox.window.TtsRecorder;
};

const ascii = function (view, offset, length) {
  let text = '';
  for (let i = 0; i < length; i++) text += String.fromCharCode(view.getUint8(offset + i));
  return text;
};

test('recorder.js publishes encodeWav and resample', () => {
  const recorder = loadRecorder();
  assert.equal(typeof recorder.encodeWav, 'function');
  assert.equal(typeof recorder.resample, 'function');
  assert.equal(typeof recorder.create, 'function');
  assert.equal(recorder.supported(), false, 'no navigator here, so not supported');
});

test('encodeWav writes a 44-byte RIFF header for 16-bit mono PCM', () => {
  const { encodeWav } = loadRecorder();
  const samples = new Float32Array([0, 0.5, -0.5, 1, -1]);
  const rate = 22050;
  const buffer = encodeWav(samples, rate);
  const view = new DataView(buffer);

  assert.equal(buffer.byteLength, 44 + samples.length * 2);
  assert.equal(ascii(view, 0, 4), 'RIFF');
  assert.equal(view.getUint32(4, true), 36 + samples.length * 2, 'RIFF chunk size');
  assert.equal(ascii(view, 8, 4), 'WAVE');
  assert.equal(ascii(view, 12, 4), 'fmt ');
  assert.equal(view.getUint32(16, true), 16, 'fmt chunk size');
  assert.equal(view.getUint16(20, true), 1, 'PCM');
  assert.equal(view.getUint16(22, true), 1, 'channels');
  assert.equal(view.getUint32(24, true), rate, 'sample rate');
  assert.equal(view.getUint32(28, true), rate * 2, 'byte rate');
  assert.equal(view.getUint16(32, true), 2, 'block align');
  assert.equal(view.getUint16(34, true), 16, 'bits per sample');
  assert.equal(ascii(view, 36, 4), 'data');
  assert.equal(view.getUint32(40, true), samples.length * 2, 'data size');

  assert.equal(view.getInt16(44, true), 0);
  assert.equal(view.getInt16(46, true), Math.trunc(0.5 * 0x7FFF));
  assert.equal(view.getInt16(48, true), -0.5 * 0x8000);
  assert.equal(view.getInt16(50, true), 0x7FFF, 'full scale clamps to the top');
  assert.equal(view.getInt16(52, true), -0x8000, 'full scale clamps to the bottom');
});

test('encodeWav clamps samples outside the unit range', () => {
  const { encodeWav } = loadRecorder();
  const view = new DataView(encodeWav(new Float32Array([2, -2]), 22050));
  assert.equal(view.getInt16(44, true), 0x7FFF);
  assert.equal(view.getInt16(46, true), -0x8000);
});

test('resample 48000 -> 22050 keeps the duration', () => {
  const { resample } = loadRecorder();
  const from = 48000;
  const to = 22050;
  const second = new Float32Array(from);
  for (let i = 0; i < second.length; i++) second[i] = Math.sin(i / 10);
  const out = resample(second, from, to);
  assert.equal(out.length, to, 'one second in is one second out');
  assert.equal(resample(new Float32Array(4800), from, to).length, 2205, 'a tenth of a second');
  assert.ok(out.every((value) => value >= -1 && value <= 1), 'interpolation stays in range');
});

test('resample with equal rates answers the same samples', () => {
  const { resample } = loadRecorder();
  const samples = new Float32Array([0.1, 0.2, 0.3]);
  assert.equal(resample(samples, 22050, 22050), samples);
});
