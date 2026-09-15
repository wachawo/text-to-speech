<template>
  <div class="tts-page">

    <div class="alert alert-secondary text-center p-1 mb-2" v-show="wait.length > 0">
      <i class="fa fa-spinner fa-pulse"></i> {{ wait.join(', ') }}
    </div>

    <tts-alerts :error.sync="error" :warning.sync="warning"
                :info.sync="info" :success.sync="success"></tts-alerts>

    <div class="tts-card mb-2">
      <div class="fw-bold text-primary border-bottom mb-1">VOICE SAMPLES (coquitts)</div>
      <div class="set-grid">
        <label for="voice-name">Name</label>
        <!-- Both fields share one width: two controls of different lengths in
             a two-column grid read as a ragged edge, not as a form. -->
        <input id="voice-name" type="text" class="form-control form-control-sm" style="width:340px"
               v-model="form.name" placeholder="maria"
               pattern="[A-Za-z0-9_-]{1,48}"
               title="Letters, digits, underscore and dash, up to 48 characters" />

        <label for="voice-file">File</label>
        <!-- Two sources of one sample, one row each: a file from disk, or a
             take from the microphone. Only one is held at a time - a take
             empties the file input and a chosen file discards the take -
             because UPLOAD sends one WAV, and two controls both showing
             something would leave the operator guessing which. -->
        <input id="voice-file" ref="file" type="file" class="form-control form-control-sm" style="width:340px"
               accept=".wav,audio/wav" @change="onFile"
               title="A PCM WAV, mono, 22050 Hz, 5-10 seconds of clean speech; ttsrec records one from the command line" />

        <label for="voice-rec">Rec</label>
        <div class="d-flex gap-2 align-items-center">
          <button id="voice-rec" type="button" class="btn btn-sm btn-danger fw-bold" style="min-width:85px"
                  :title="recording ? 'Stop recording' : (canRecord ? 'Record a sample from the microphone (up to 30 seconds)' : 'REC needs https')"
                  :disabled="wait.length > 0 || !canRecord" @click="toggleRecording">
            <i class="fa" :class="recording ? 'fa-stop' : 'fa-microphone'"></i> {{ recording ? 'STOP ' + clock : 'REC' }}
          </button>
          <!-- getUserMedia exists only on https or localhost. The button stays,
               greyed, so the feature is visibly there; the glyph beside it
               says what to do about it, on click rather than as a paragraph. -->
          <i v-if="!canRecord" class="fa fa-circle-info text-primary cursor-pointer"
             title="Why REC is off" @click="explainRec"></i>
        </div>
      </div>

      <div v-if="take" class="tts-player mt-1">
        <audio controls :src="takeUrl"></audio>
        <small :class="takeSilent ? 'tts-state-off' : 'text-secondary'">{{ takeNote }}</small>
        <button type="button" class="btn btn-sm btn-secondary fw-bold" style="min-width:85px"
                title="Discard the recording" :disabled="wait.length > 0" @click="discardTake">
          <i class="fa fa-times"></i> DISCARD
        </button>
      </div>

      <div class="d-flex justify-content-end align-items-center gap-2 mt-1">
        <small v-if="note" class="text-end" :class="noteError ? 'tts-state-off' : 'text-secondary'">{{ note }}</small>
        <button type="button" class="btn btn-sm btn-success fw-bold" style="min-width:100px"
                @click="upload" :disabled="wait.length > 0 || !(file || take) || !nameValid"
                title="Store the WAV above as a coquitts voice sample">
          <i class="fa fa-upload"></i> UPLOAD
        </button>
      </div>
    </div>

    <div class="form-check-inline m-1 d-flex flex-wrap row-gap-1 align-items-center">
      <div style="margin-left: auto"></div>
      <div style="margin-right: 0.25rem" class="d-flex align-items-center">
        <small class="text-secondary" v-if="samples.length > 0">{{ samples.length }} voices</small>
      </div>
      <div>
        <button type="button" class="btn btn-sm btn-secondary fw-bold" style="min-width:85px" @click="fetchVoices"
                :disabled="wait.length > 0" title="Read the sample list again">
          <i class="fa fa-rotate"></i> RELOAD
        </button>
      </div>
    </div>

    <div class="tts-card p-0 overflow-hidden">
      <div class="table-responsive">
        <table class="table table-striped table-sm table-fixed mb-0">
          <caption>VOICES</caption>
          <colgroup>
            <col style="width:34%">
            <col style="width:12%">
            <col style="width:12%">
            <col style="width:12%">
            <col style="width:10%">
            <col style="width:10%">
            <col style="width:10%">
          </colgroup>
          <thead>
            <tr>
              <td>Name</td>
              <td>Size</td>
              <td>Rate</td>
              <td>Channels</td>
              <td>Seconds</td>
              <td>Default</td>
              <td></td>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in samples" :key="row.name">
              <td class="td-ellipsis" :title="rowTitle(row.name)">{{ row.name }}</td>
              <td>{{ $fmtBytes(row.bytes) }}</td>
              <!-- A sample `wave` could not parse shows "-" in the three
                   header columns; it is still listed because it is still on
                   disk, and the trash glyph is how it leaves. -->
              <td>{{ row.rate ? row.rate + ' Hz' : '-' }}</td>
              <td>{{ row.channels || '-' }}</td>
              <td>{{ $fmtSeconds(row.seconds) }}</td>
              <!-- A word in its own column, not a suffix on the name: the name
                   cell is ellipsised and a suffix is the part a long name
                   loses. -->
              <td>{{ row.name === defaultVoice ? 'default' : '' }}</td>
              <!-- Three glyphs, each an action on this row: play/pause the
                   sample through one shared Audio object, download it, delete
                   it. The default sample is deletable too; the confirm dialog
                   says what that costs. -->
              <td class="td-actions" @click.stop>
                <i class="fa fa-fw text-primary" :class="playing === row.name ? 'fa-pause' : 'fa-play'"
                   :title="playing === row.name ? 'Pause' : 'Listen to this sample'"
                   @click="togglePlay(row.name)"></i>
                <a :href="audioUrl(row.name, true)" download :title="'Download ' + row.name + '.wav'">
                  <i class="fa fa-fw fa-download"></i>
                </a>
                <i class="fa fa-fw fa-trash text-danger"
                   title="Delete this voice" :class="{ disabled: wait.length > 0 }"
                   @click="remove(row.name)"></i>
              </td>
            </tr>
            <tr v-if="samples.length === 0 && wait.length === 0">
              <td colspan="7" class="text-center text-secondary">No samples yet - upload a WAV above</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <tts-confirm ref="confirm"></tts-confirm>
  </div>
</template>

<script>
/* Voice samples for coquitts voice cloning: one upload block and the list of
   what the server holds. The other engines have no samples to manage, so the
   engine is fixed to coquitts here and never asked for.
*/

/* The same rule as VoiceUploadSchema on the server: a bare file stem, one to
   forty-eight characters. Checked here as well so UPLOAD stays disabled on a
   name the server would refuse, instead of round-tripping to find out. */
var NAME_REGEX = /^[A-Za-z0-9_-]{1,48}$/;

var ENGINE = 'coquitts';

/* The take's format, fixed to what the sample is for: xtts_v2 conditions on
   22050 Hz mono, and ttsrec writes the same, so a browser take and a terminal
   take are the same file on the server. */
var SAMPLE_RATE = 22050;
var MAX_SECONDS = 30;

/* Below this peak the take is treated as silent - the same three percent of
   full scale ttsrec.py draws its line at (1000 of 32767). A muted microphone
   still delivers a stream, and the server accepts a WAV of nothing without a
   word, so this is the only place the operator hears about it before the
   clone comes out as noise. */
var SILENT_PEAK = 0.03;

/* m:ss for the clock in the STOP label. */
var formatClock = function (seconds) {
  var whole = Math.floor(seconds);
  var rest = whole % 60;
  return Math.floor(whole / 60) + ':' + (rest < 10 ? '0' : '') + rest;
};

module.exports = {
  data: function () {
    return {
      wait: [],
      error: '',
      warning: '',
      info: '',
      success: '',
      // One row per sample from GET /api/voices "samples": name, bytes,
      // rate, channels, seconds. `voices` (the bare names) is what the
      // studio's select uses; this screen shows the files behind them.
      samples: [],
      defaultVoice: null,
      form: { name: '' },
      file: null,
      note: '',
      noteError: false,
      // The name whose sample is sounding, or null. The Audio object itself is
      // kept off `data` (see mounted): Vue would make it reactive and walk
      // every field the browser owns.
      playing: null,
      tlsPort: '',
      // The microphone take, once there is one: the Blob UPLOAD sends, the
      // object URL the preview plays, and what the recorder measured. The
      // recorder itself is kept off `data` for the same reason the Audio
      // object is (see mounted).
      recording: false,
      clock: '0:00',
      take: null,
      takeUrl: '',
      takeSeconds: 0,
      takePeak: 0,
    };
  },

  created: function () {
    this.fetchVoices();
    this.fetchUiConfig();
  },

  mounted: function () {
    var self = this;
    this.recorder = null;
    this.player = new Audio();
    this.player.addEventListener('ended', function () { self.playing = null; });
    this.player.addEventListener('error', function () {
      self.playing = null;
      self.error = 'The sample could not be played';
    });
  },

  /* Leaving the screen silences it: the Audio object is not in the DOM, so
     nothing else would stop a sample that is still sounding. The microphone
     likewise - a take in progress is dropped, not kept for a screen nobody is
     looking at, and the tab's recording indicator goes out with it. */
  beforeDestroy: function () {
    if (this.player) {
      this.player.pause();
      this.player = null;
    }
    if (this.recorder) {
      this.recorder.release();
      this.recorder = null;
    }
    this.discardTake();
  },

  computed: {
    nameValid: function () {
      return NAME_REGEX.test(this.form.name);
    },

    hasRecorder: function () {
      return typeof window !== 'undefined' && !!window.TtsRecorder;
    },

    canRecord: function () {
      return this.hasRecorder && window.TtsRecorder.supported();
    },

    /* The https address of this same UI, for the REC explanation. The port
       comes from nginx (/ui-config.json); 8443 until it has answered. */
    httpsUrl: function () {
      return 'https://' + window.location.hostname + ':' + (this.tlsPort || '8443');
    },

    takeSilent: function () {
      return !!this.take && this.takePeak < SILENT_PEAK;
    },

    /* "Recorded 7.3 s, 22050 Hz mono, 320 KB", and the one thing worth
       saying about a silent take: what usually caused it. */
    takeNote: function () {
      if (!this.take) return '';
      var text = 'Recorded ' + this.$fmtSeconds(this.takeSeconds) + ', ' + SAMPLE_RATE + ' Hz mono, ' +
        this.$fmtBytes(this.take.size);
      if (this.takeSilent) {
        text += ' - the take is silent: the microphone is muted or the browser is listening to the wrong input device';
      }
      return text;
    },
  },

  methods: {
    rowTitle: function (name) {
      if (name === this.defaultVoice) return name + ' - the COQUITTS_SAMPLE default, used when a request names no voice';
      return name;
    },

    /* The chosen file, and a name proposed from it when the field is empty.
       A sample is usually recorded under the name the operator wants to
       select it by, so the stem is the right first guess; anything outside
       the allowed set becomes "_" because the server refuses the name
       otherwise, and a proposal the server refuses is worse than none. */
    onFile: function (event) {
      var files = event.target.files;
      this.file = (files && files.length) ? files[0] : null;
      this.note = '';
      this.noteError = false;
      if (this.file) this.discardTake();
      if (!this.file || this.form.name) return;
      var stem = this.file.name.replace(/\.[^.]*$/, '');
      this.form.name = stem.replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 48);
    },

    /* Recording */
    toggleRecording: function () {
      if (this.recording) this.stopRecording();
      else this.startRecording();
    },

    /* The button turns into STOP only once the microphone streams: while the
       browser's permission prompt is up there is nothing to stop yet, and the
       wait queue says what is being waited for. A refusal is the one failure
       with a name the operator can act on; anything else is the browser's
       own sentence. */
    startRecording: function () {
      var self = this;
      if (!self.canRecord || self.recorder) return;
      self.discardTake();
      self.error = '';
      var recorder = window.TtsRecorder.create({
        sampleRate: SAMPLE_RATE,
        maxSeconds: MAX_SECONDS,
        onTick: function (seconds) {
          self.clock = formatClock(seconds);
          if (seconds >= MAX_SECONDS) self.stopRecording();
        },
        // The take is closed with what was really captured, and the note says
        // why it is shorter than the clock the operator was watching.
        onEnded: function () {
          self.stopRecording();
          self.warning = 'The microphone went away - the take ends here';
        },
      });
      self.recorder = recorder;
      self.clock = '0:00';
      self.wait.push('microphone');
      recorder.start()
        .then(function () {
          // The screen was left while the prompt was up: beforeDestroy has
          // already released this recorder, and there is nothing to show.
          if (self.recorder !== recorder) return;
          self.recording = true;
        })
        .catch(function (err) {
          if (self.recorder === recorder) self.recorder = null;
          if (err && err.name === 'NotAllowedError') self.error = 'Microphone access was refused';
          else self.error = (err && err.message) || 'The microphone could not be opened';
        })
        .finally(function () {
          var i = self.wait.indexOf('microphone');
          if (i !== -1) self.wait.splice(i, 1);
        });
    },

    /* The take replaces whatever file was chosen (see the template). The
       name is left alone: a file brings a stem to propose, a take does not. */
    stopRecording: function () {
      var recorder = this.recorder;
      if (!recorder) return;
      this.recorder = null;
      this.recording = false;
      var blob = recorder.stop();
      this.take = blob;
      this.takeUrl = URL.createObjectURL(blob);
      this.takeSeconds = recorder.seconds;
      this.takePeak = recorder.peak;
      this.file = null;
      if (this.$refs.file) this.$refs.file.value = '';
      this.note = '';
      this.noteError = false;
    },

    /* The object URL is revoked with the take: each one pins its Blob in
       memory until the document goes away, and a screen used all afternoon
       would hold every take ever discarded. */
    discardTake: function () {
      if (this.takeUrl) URL.revokeObjectURL(this.takeUrl);
      this.take = null;
      this.takeUrl = '';
      this.takeSeconds = 0;
      this.takePeak = 0;
    },

    fetchUiConfig: function () {
      var self = this;
      this.$http.get('/ui-config.json')
        .then(function (resp) {
          var port = resp.data && resp.data.tls_port;
          self.tlsPort = /^\d+$/.test(String(port)) ? String(port) : '';
        })
        .catch(function () { self.tlsPort = ''; });
    },

    /* What blocks REC and the two ways out, in the info bar on demand. */
    explainRec: function () {
      if (!this.hasRecorder) {
        this.info = 'recorder.js did not load - reload the page';
        return;
      }
      this.info = 'The browser gives the microphone only to https or localhost. ' +
        'Open ' + this.httpsUrl + ' (accept the certificate once), ' +
        'or add ' + window.location.origin + ' to chrome://flags/#unsafely-treat-insecure-origin-as-secure';
    },

    audioUrl: function (name, download) {
      return '/api/voices/' + encodeURIComponent(name) + '/audio?engine=' + ENGINE +
        (download ? '&download=1' : '');
    },

    /* One sample sounds at a time. A second click on the same row pauses it;
       a click on another row switches to that one, with no pause step. */
    togglePlay: function (name) {
      if (!this.player) return;
      if (this.playing === name) {
        this.player.pause();
        this.playing = null;
        return;
      }
      this.player.src = this.audioUrl(name);
      this.playing = name;
      var started = this.player.play();
      if (started && started.catch) started.catch(function () {});
    },

    /* Reading */
    fetchVoices: function () {
      var self = this;
      self.wait.push('voices');
      self.$http.get('/api/voices', { params: { engine: ENGINE } })
        .then(function (resp) {
          self.samples = resp.data.samples || [];
          self.defaultVoice = resp.data.default || null;
        })
        .catch(function (err) {
          self.error = self.$apiError(err);
        })
        .finally(function () {
          var i = self.wait.indexOf('voices');
          if (i !== -1) self.wait.splice(i, 1);
        });
    },

    /* Creating */
    upload: function () {
      var self = this;
      if (!(self.file || self.take) || !self.nameValid) return;
      var name = self.form.name;
      var body = new FormData();
      // A Blob has no file name of its own; the server reads the name from
      // the form field, but a multipart part without a filename is a text
      // field to Flask and never reaches request.files.
      if (self.take) body.append('file', self.take, name + '.wav');
      else body.append('file', self.file);
      body.append('name', name);
      body.append('engine', ENGINE);
      self.note = '';
      self.noteError = false;
      self.wait.push('uploading ' + name);
      // No Content-Type header of our own: axios writes the multipart boundary
      // into it, and a header set here would drop the boundary.
      self.$http.post('/api/voices', body)
        .then(function (resp) {
          var said = resp.data || {};
          self.note = 'Saved ' + (said.voice || name) + ': ' + self.$fmtBytes(said.bytes) +
            ', ' + said.rate + ' Hz, ' + said.channels + ' ch, ' + self.$fmtSeconds(said.seconds);
          self.$store.dispatch('push_toast', {
            level: 'success',
            message: 'Voice "' + (said.voice || name) + '" uploaded',
          });
          self.form.name = '';
          self.file = null;
          if (self.$refs.file) self.$refs.file.value = '';
          self.discardTake();
          self.fetchVoices();
        })
        .catch(function (err) {
          var data = err && err.response && err.response.data;
          if (err && err.response && err.response.status === 413) {
            var limit = data && data.limit_mb;
            self.note = 'The file is too large' + (limit ? ' - the limit is ' + limit + ' MB' : '');
          } else {
            self.note = self.$apiError(err);
          }
          self.noteError = true;
        })
        .finally(function () {
          var i = self.wait.indexOf('uploading ' + name);
          if (i !== -1) self.wait.splice(i, 1);
        });
    },

    /* Deleting */
    remove: function (name) {
      var self = this;
      var body = 'Delete the voice sample "' + name + '"?';
      // The default is what a request without a voice falls back on; without
      // it coquitts refuses such requests until a sample of that name is back.
      if (name === self.defaultVoice) {
        body += '\n\nThis is the COQUITTS_SAMPLE default: requests that name no voice will fail until it is uploaded again.';
      }
      self.$refs.confirm.ask({
        title: 'DELETE VOICE',
        body: body,
        label: 'DELETE',
        danger: true,
      }).then(function (ok) {
        if (!ok) return;
        self.wait.push('deleting ' + name);
        self.$http.delete('/api/voices/' + encodeURIComponent(name), { params: { engine: ENGINE } })
          .then(function () {
            if (self.playing === name) self.togglePlay(name);
            self.$store.dispatch('push_toast', { level: 'success', message: 'Voice "' + name + '" deleted' });
            self.fetchVoices();
          })
          .catch(function (err) {
            self.error = self.$apiError(err);
          })
          .finally(function () {
            var i = self.wait.indexOf('deleting ' + name);
            if (i !== -1) self.wait.splice(i, 1);
          });
      });
    },
  },
};
</script>
