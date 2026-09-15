<template>
  <div class="tts-page">

    <div class="alert alert-secondary text-center p-1 mb-2" v-show="wait.length > 0">
      <i class="fa fa-spinner fa-pulse"></i> {{ wait.join(', ') }}
    </div>

    <tts-alerts :error.sync="error" :warning.sync="warning"
                :info.sync="info" :success.sync="success"></tts-alerts>

    <small class="text-secondary d-block mb-2">
      Samples are used by coquitts (xtts_v2) voice cloning; the other engines
      ship fixed voices - pick them in the studio.
    </small>

    <div class="tts-card mb-2">
      <div class="fw-bold text-primary border-bottom mb-1">VOICE SAMPLES (coquitts)</div>
      <div class="set-grid">
        <label for="voice-name">Name</label>
        <input id="voice-name" type="text" class="form-control form-control-sm" style="width:220px"
               v-model="form.name" placeholder="maria"
               pattern="[A-Za-z0-9_-]{1,48}"
               title="Letters, digits, underscore and dash, up to 48 characters" />

        <label for="voice-file">File</label>
        <input id="voice-file" ref="file" type="file" class="form-control form-control-sm" style="width:340px"
               accept=".wav,audio/wav" @change="onFile"
               title="A PCM WAV, mono, 22050 Hz, 5-10 seconds of clean speech; ttsrec records one from the command line" />
      </div>

      <div class="d-flex justify-content-end align-items-center gap-2 mt-1">
        <small v-if="note" class="text-end" :class="noteError ? 'tts-state-off' : 'text-secondary'">{{ note }}</small>
        <button type="button" class="btn btn-sm btn-success fw-bold" style="min-width:100px"
                @click="upload" :disabled="wait.length > 0 || !file || !nameValid"
                title="Store the WAV above as a coquitts voice sample">
          <i class="fa fa-upload"></i> UPLOAD
        </button>
      </div>
    </div>

    <div class="form-check-inline m-1 d-flex flex-wrap row-gap-1 align-items-center">
      <div style="margin-left: auto"></div>
      <div style="margin-right: 0.25rem" class="d-flex align-items-center">
        <small class="text-secondary" v-if="voices.length > 0">{{ voices.length }} voices</small>
      </div>
      <div>
        <button type="button" class="btn btn-sm btn-secondary" @click="fetchVoices"
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
            <col style="width:70%">
            <col style="width:20%">
            <col style="width:10%">
          </colgroup>
          <thead>
            <tr>
              <td>Name</td>
              <td>Default</td>
              <td></td>
            </tr>
          </thead>
          <tbody>
            <tr v-for="name in voices" :key="name">
              <td class="td-ellipsis" :title="rowTitle(name)">{{ name }}</td>
              <!-- A word in its own column, not a suffix on the name: the name
                   cell is ellipsised and a suffix is the part a long name
                   loses. -->
              <td>{{ name === defaultVoice ? 'default' : '' }}</td>
              <!-- The default sample has no trash glyph at all rather than a
                   greyed one: the server refuses to delete it, and a control
                   that can only fail invites the click it then refuses. -->
              <td class="td-actions" @click.stop>
                <i v-if="name !== defaultVoice" class="fa fa-trash text-danger"
                   title="Delete this voice" :class="{ disabled: wait.length > 0 }"
                   @click="remove(name)"></i>
              </td>
            </tr>
            <tr v-if="voices.length === 0 && wait.length === 0">
              <td colspan="3" class="text-center text-secondary">No samples yet - upload a WAV above</td>
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

module.exports = {
  data: function () {
    return {
      wait: [],
      error: '',
      warning: '',
      info: '',
      success: '',
      voices: [],
      defaultVoice: null,
      // GET /api/voices carries bare names and nothing about the files behind
      // them, so the table lists names only; the size, rate, channels and
      // seconds of an upload are reported once, in the note beside UPLOAD.
      form: { name: '' },
      file: null,
      note: '',
      noteError: false,
    };
  },

  created: function () {
    this.fetchVoices();
  },

  computed: {
    nameValid: function () {
      return NAME_REGEX.test(this.form.name);
    },
  },

  methods: {
    rowTitle: function (name) {
      if (name === this.defaultVoice) return name + ' - the COQUITTS_SAMPLE default; it cannot be deleted from here';
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
      if (!this.file || this.form.name) return;
      var stem = this.file.name.replace(/\.[^.]*$/, '');
      this.form.name = stem.replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 48);
    },

    /* Reading */
    fetchVoices: function () {
      var self = this;
      self.wait.push('voices');
      self.$http.get('/api/voices', { params: { engine: ENGINE } })
        .then(function (resp) {
          self.voices = resp.data.voices || [];
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
      if (!self.file || !self.nameValid) return;
      var name = self.form.name;
      var body = new FormData();
      body.append('file', self.file);
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
      self.$refs.confirm.ask({
        title: 'DELETE VOICE',
        body: 'Delete the voice sample "' + name + '"?',
        label: 'DELETE',
        danger: true,
      }).then(function (ok) {
        if (!ok) return;
        self.wait.push('deleting ' + name);
        self.$http.delete('/api/voices/' + encodeURIComponent(name), { params: { engine: ENGINE } })
          .then(function () {
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
