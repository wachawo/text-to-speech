/* TtsRecorder - a microphone take as a PCM WAV, for the Voices screen.

   A plain script rather than a module, like everything else under /js: there
   is no build step, and index.html loads it ahead of app.js so the screens can
   assume `window.TtsRecorder` exists.

   The output is fixed at 16-bit mono at 22050 Hz because that is what the
   sample is for: xtts_v2 conditions on a 22050 Hz reference, and ttsrec - the
   command-line recorder - writes exactly this format, so a take from the
   browser and a take from the terminal are interchangeable on the server.

   The pure parts - the resampler and the WAV encoder - are exposed on the
   object as well, so they can be checked from node without a browser to stand
   in for `navigator` and `AudioContext`. */
(function () {
  'use strict';

  var HEADER_BYTES = 44;

  /* Linear interpolation between neighbouring samples. Enough for speech that
     is going to be conditioned on, not listened to for pleasure: the aliasing
     a proper low-pass would remove sits above the band a voice occupies. The
     length is rounded from the ratio rather than truncated, so a whole second
     at 48000 comes back as a whole second at 22050. */
  var resample = function (samples, from, to) {
    if (from === to) return samples;
    var length = Math.round(samples.length * to / from);
    var out = new Float32Array(length);
    var ratio = from / to;
    for (var i = 0; i < length; i++) {
      var position = i * ratio;
      var index = Math.floor(position);
      var fraction = position - index;
      var left = samples[index];
      var right = index + 1 < samples.length ? samples[index + 1] : left;
      out[i] = left + (right - left) * fraction;
    }
    return out;
  };

  var writeAscii = function (view, offset, text) {
    for (var i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };

  /* Float samples in -1..1 to a complete RIFF/WAVE file: a 44-byte header and
     16-bit little-endian PCM, one channel. Clamped before conversion because a
     ScriptProcessor buffer is not guaranteed to stay inside the unit range,
     and an unclamped overflow wraps to the opposite sign - the loudest syllable
     of the take would come back as a click. Returns the ArrayBuffer; the
     caller wraps it in a Blob or hands it to a file. */
  var encodeWav = function (samples, sampleRate) {
    var buffer = new ArrayBuffer(HEADER_BYTES + samples.length * 2);
    var view = new DataView(buffer);
    writeAscii(view, 0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeAscii(view, 8, 'WAVE');
    writeAscii(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeAscii(view, 36, 'data');
    view.setUint32(40, samples.length * 2, true);
    var offset = HEADER_BYTES;
    for (var i = 0; i < samples.length; i++, offset += 2) {
      var sample = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
    }
    return buffer;
  };

  /* Whether this page can record at all. getUserMedia exists only on a secure
     page - https, or localhost - so on plain http over the network this is
     false, and the screen says so instead of offering a control that can only
     fail. */
  var supported = function () {
    if (typeof navigator === 'undefined' || typeof window === 'undefined') return false;
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia &&
      (window.AudioContext || window.webkitAudioContext));
  };

  /* One take. `start()` opens the microphone and resolves once it streams;
     `stop()` closes it and answers the WAV as a Blob; `release()` closes it
     and answers nothing, for a screen that is being left mid-take. `seconds`
     and `peak` are read by the screen while recording and after `stop()`. */
  var create = function (options) {
    var settings = options || {};
    var sampleRate = settings.sampleRate || 22050;
    var maxSeconds = settings.maxSeconds || 30;
    var onTick = typeof settings.onTick === 'function' ? settings.onTick : function () {};
    var onEnded = typeof settings.onEnded === 'function' ? settings.onEnded : function () {};

    var stream = null;
    var context = null;
    var source = null;
    var processor = null;
    var timer = null;
    var chunks = [];
    var captureRate = sampleRate;
    var startedAt = 0;
    // Set by release(). The permission prompt can outlive the screen that
    // asked, and a grant that arrives after release() would otherwise open
    // the microphone for a take nobody is going to stop.
    var released = false;

    var recorder = { seconds: 0, peak: 0 };

    /* Safe to call twice: the time limit tears the capture down on its own,
       and the screen's `stop()` that follows must find nothing left to close
       rather than a closed context to close again. */
    var teardown = function () {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (processor) {
        processor.onaudioprocess = null;
        processor.disconnect();
        processor = null;
      }
      if (source) {
        source.disconnect();
        source = null;
      }
      if (stream) {
        stream.getTracks().forEach(function (track) { track.stop(); });
        stream = null;
      }
      if (context) {
        try { context.close(); } catch (err) { /* already closed */ }
        context = null;
      }
    };

    /* Chrome honours the requested rate and hands over 22050 Hz buffers
       directly; a browser that refuses the option, or quietly opens the
       context at the device rate, is caught by the resample on stop, which is
       why the rate the buffers actually arrived at is kept. */
    var openContext = function () {
      var Context = window.AudioContext || window.webkitAudioContext;
      try {
        return new Context({ sampleRate: sampleRate });
      } catch (err) {
        return new Context();
      }
    };

    var onAudio = function (event) {
      var input = event.inputBuffer.getChannelData(0);
      var copy = new Float32Array(input.length);
      var peak = recorder.peak;
      for (var i = 0; i < input.length; i++) {
        copy[i] = input[i];
        var magnitude = input[i] < 0 ? -input[i] : input[i];
        if (magnitude > peak) peak = magnitude;
      }
      recorder.peak = peak;
      chunks.push(copy);
    };

    /* The clock, and the limit. At the limit the microphone is closed here
       rather than left running while the screen reacts: the tick reports the
       limit as the elapsed time, the screen calls stop(), and stop() encodes
       what was captured. */
    var onTimer = function () {
      recorder.seconds = (Date.now() - startedAt) / 1000;
      if (recorder.seconds >= maxSeconds) {
        recorder.seconds = maxSeconds;
        teardown();
      }
      onTick(recorder.seconds);
    };

    /* The device going away mid-take: unplugged, or access revoked from the
       browser's site popup. The source keeps outputting zeros after that,
       so without this the take would run on as silence to the limit. The
       track's own stop() does not fire `ended`, and a late one after
       teardown finds no stream to end. */
    var onTrackEnded = function () {
      if (!stream) return;
      teardown();
      onEnded();
    };

    recorder.start = function () {
      var constraints = { audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } };
      return navigator.mediaDevices.getUserMedia(constraints).then(function (granted) {
        if (released) {
          granted.getTracks().forEach(function (track) { track.stop(); });
          return;
        }
        // From here the microphone is open, so a throw on the way to the
        // timer must close it: the rejection reaches a screen that has no
        // handle to close it with.
        try {
          stream = granted;
          context = openContext();
          captureRate = context.sampleRate;
          source = context.createMediaStreamSource(stream);
          stream.getAudioTracks()[0].addEventListener('ended', onTrackEnded);
          // Deprecated in favour of AudioWorklet, and used anyway: a worklet is a
          // separate file the page has to serve and load, and this is a
          // thirty-second take of one voice, not a mixer. The worklet is the
          // upgrade path if a browser drops the node.
          processor = context.createScriptProcessor(4096, 1, 1);
          processor.onaudioprocess = onAudio;
          source.connect(processor);
          // Nothing is heard through this: the node is silent on its output,
          // but Chrome only runs a ScriptProcessor that is wired to the
          // destination.
          processor.connect(context.destination);
          startedAt = Date.now();
          recorder.seconds = 0;
          recorder.peak = 0;
          timer = setInterval(onTimer, 250);
        } catch (err) {
          teardown();
          throw err;
        }
      });
    };

    recorder.stop = function () {
      teardown();
      var total = 0;
      for (var i = 0; i < chunks.length; i++) total += chunks[i].length;
      var joined = new Float32Array(total);
      var offset = 0;
      for (var j = 0; j < chunks.length; j++) {
        joined.set(chunks[j], offset);
        offset += chunks[j].length;
      }
      chunks = [];
      var samples = resample(joined, captureRate, sampleRate);
      // The length of the audio, not of the clock: the two differ by the
      // latency of the first buffer, and the figure the screen prints beside
      // the player should be the one the player agrees with.
      recorder.seconds = samples.length / sampleRate;
      return new Blob([encodeWav(samples, sampleRate)], { type: 'audio/wav' });
    };

    recorder.release = function () {
      released = true;
      teardown();
      chunks = [];
    };

    return recorder;
  };

  window.TtsRecorder = {
    supported: supported,
    create: create,
    encodeWav: encodeWav,
    resample: resample,
  };
})();
