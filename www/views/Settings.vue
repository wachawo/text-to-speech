<template>
  <div class="modal fade" ref="modalEl" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-dialog-scrollable">
      <div class="modal-content">

        <div class="modal-header bg-blue py-1 px-3">
          <h5 class="modal-title fw-bold mb-0">SETTINGS</h5>
          <button type="button" class="btn btn-primary btn-sm ms-auto"
                  data-bs-dismiss="modal" title="Close" aria-label="Close">
            <i class="fa fa-times"></i>
          </button>
        </div>

        <div class="modal-body py-2">
          <div class="alert alert-secondary text-center p-1 mb-2" v-show="wait.length > 0">
            <i class="fa fa-spinner fa-pulse"></i> {{ wait.join(', ') }}
          </div>
          <tts-alerts :error.sync="error"></tts-alerts>

          <div class="fw-bold text-primary text-uppercase border-bottom mt-2 mb-1">Studio defaults</div>
          <small class="text-secondary d-block mb-1">
            Studio opens with these and remembers whatever you pick there;
            server default follows TTS_ENGINE, TTS_LANGUAGE and COQUITTS_SAMPLE.
          </small>
          <div class="set-grid">
            <label for="set-engine">Engine</label>
            <select id="set-engine" class="form-select form-select-sm set-select" style="width: 220px"
                    v-model="form.engine" :disabled="wait.length > 0">
              <option value="">server default ({{ serverEngine || '-' }})</option>
              <option v-for="name in engines" :key="name" :value="name">{{ name }}</option>
            </select>

            <label for="set-language">Language</label>
            <select id="set-language" class="form-select form-select-sm set-select" style="width: 220px"
                    v-model="form.language" :disabled="wait.length > 0">
              <option value="">server default ({{ serverLanguage || '-' }})</option>
              <option v-for="lang in languages" :key="lang.code" :value="lang.code">
                {{ lang.code }} {{ lang.name }}
              </option>
            </select>

            <label for="set-voice">Voice</label>
            <select id="set-voice" class="form-select form-select-sm set-select" style="width: 220px"
                    v-model="form.voice" :disabled="wait.length > 0 || voices.length === 0">
              <option value="">server default ({{ serverVoice || '-' }})</option>
              <option v-for="name in voices" :key="name" :value="name">{{ name }}</option>
            </select>
          </div>
          <!-- The report sits beside the button that produced it, not in a bar
               at the top: whoever pressed SAVE is looking here. -->
          <div class="d-flex justify-content-end align-items-center gap-2 mt-1 mb-2">
            <small v-if="note" class="text-end"
                   :class="noteFailed ? 'tts-state-off' : 'text-secondary'">{{ note }}</small>
            <button type="button" class="btn btn-sm btn-success fw-bold" style="min-width:100px"
                    @click="saveStudio" :disabled="wait.length > 0">SAVE</button>
          </div>

          <div class="fw-bold text-primary text-uppercase border-bottom mt-2 mb-1">View</div>
          <div class="form-check">
            <input id="set-curl" class="form-check-input" type="checkbox"
                   v-model="curl" @change="saveView" />
            <label class="form-check-label" for="set-curl">Show the curl example under the player</label>
          </div>
        </div>

        <div class="modal-footer p-1 d-flex justify-content-end">
          <button type="button" class="btn btn-sm btn-secondary fw-bold" style="min-width:100px"
                  data-bs-dismiss="modal">CLOSE</button>
        </div>

      </div>
    </div>
  </div>
</template>

<script>
/* The settings of this browser: what the studio opens with, and what the
   screens show. Nothing here is about the server - that is why it is a dialog
   behind a gear and not a screen with an address.

   Rendered by the App root, once, beside the toaster. It is asked for through
   `$store.state.settingsOpen`: the gear in the header sets the flag, this
   dialog watches it, opens, and clears it on `hidden` - so the bar and the
   dialog never hold a reference to each other, and closing by any route (the
   cross, CLOSE, Escape, the backdrop) leaves the flag telling the truth.

   The two blocks commit differently, and on purpose. The studio block is
   three fields that hang together - a voice belongs to an engine and a
   language - so it has a SAVE, and leaving by any other way discards what was
   picked rather than writing a half-chosen triple. The view block is one
   switch, and a switch is its own commit: it applies on change, because a SAVE
   under a checkbox is a second click that only confirms the first.

   Needs bootstrap.bundle.min.js, as Confirm.vue does; without it the flag is
   cleared at once and nothing opens.
*/

/* The languages xtts_v2 speaks. A copy of the list in Studio.vue, and the two
   MUST STAY EQUAL: a default picked here that the studio's select does not
   carry would render as a blank select. No engine reports its languages yet,
   so neither file can ask the server instead. */
var LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'pl', name: 'Polish' },
  { code: 'tr', name: 'Turkish' },
  { code: 'ru', name: 'Russian' },
  { code: 'nl', name: 'Dutch' },
  { code: 'cs', name: 'Czech' },
  { code: 'ar', name: 'Arabic' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ja', name: 'Japanese' },
  { code: 'hu', name: 'Hungarian' },
  { code: 'ko', name: 'Korean' },
  { code: 'hi', name: 'Hindi' },
];

var NOT_KEPT = 'This browser would not store the setting, so it holds until the page is reloaded.';

/* Remove one label from the wait queue. */
var dropWait = function (wait, label) {
  var i = wait.indexOf(label);
  if (i !== -1) wait.splice(i, 1);
};

module.exports = {
  data: function () {
    return {
      wait: [],
      error: '',
      engines: [],
      languages: LANGUAGES,
      voices: [],
      // What /api/engines and /api/voices say the server falls back to, for
      // the "server default (...)" option of each select.
      serverEngine: '',
      serverLanguage: '',
      serverVoice: '',
      form: { engine: '', language: '', voice: '' },
      curl: true,
      note: '',
      noteFailed: false,
    };
  },

  mounted: function () {
    // The Bootstrap handle is kept off `data`, as in Confirm.vue: Vue would
    // make the library object reactive and walk every field it owns. The
    // voices serial is not reactive either - nothing renders from it.
    this.modalEl = this.$refs.modalEl;
    this.modal = (typeof bootstrap !== 'undefined' && bootstrap.Modal)
      ? new bootstrap.Modal(this.modalEl)
      : null;
    this.voiceSerial = 0;
    this.modalEl.addEventListener('hidden.bs.modal', this.handleHidden);
    if (this.$store.state.settingsOpen) this.open();
  },

  beforeDestroy: function () {
    if (this.modalEl) this.modalEl.removeEventListener('hidden.bs.modal', this.handleHidden);
    if (this.modal) {
      this.modal.dispose();
      this.modal = null;
    }
    this.modalEl = null;
  },

  computed: {
    /* The pair the voices are asked for, with the server's own values in
       place of "server default" - the list the operator picks from must be
       the list of the engine the studio would actually open with. Empty until
       /api/engines has answered, so nothing is asked of a pair that is not
       known yet. */
    voiceKey: function () {
      var engine = this.form.engine || this.serverEngine;
      var language = this.form.language || this.serverLanguage;
      return engine && language ? engine + '/' + language : '';
    },
  },

  watch: {
    '$store.state.settingsOpen': function (asked) {
      if (asked) this.open();
    },

    voiceKey: function () {
      this.fetchVoices();
    },
  },

  methods: {
    /* Seed from the store and open. Seeded on every open rather than once:
       an edit abandoned by Escape last time must not be what the dialog shows
       this time. The lists are fetched now rather than at app start - the
       dialog is opened rarely, and the catalogue is not worth a request on
       every page load for a screen that may never be opened. */
    open: function () {
      var studio = this.$store.state.studio;
      // The engine and the voice are corrected against the lists the server
      // answers with; the language has no such list, so it is checked here.
      // A hand-edited code the select has no option for would otherwise show
      // as a blank select and be written back by SAVE as it came.
      var language = LANGUAGES.some(function (l) { return l.code === studio.language; })
        ? studio.language : '';
      this.form = { engine: studio.engine, language: language, voice: studio.voice };
      this.curl = this.$store.state.view.curl;
      this.note = '';
      this.noteFailed = false;
      this.error = '';
      if (!this.modal) {
        this.$store.state.settingsOpen = false;
        return;
      }
      this.modal.show();
      this.fetchEngines();
    },

    handleHidden: function () {
      this.$store.state.settingsOpen = false;
    },

    /* Catalogue */

    fetchEngines: function () {
      var self = this;
      var keyBefore = this.voiceKey;
      this.wait.push('engines');
      this.$http.get('/api/engines')
        .then(function (resp) {
          var data = resp.data || {};
          self.engines = data.available || [];
          self.serverEngine = data['default'] || '';
          self.serverLanguage = data.language || '';
          // A stored engine this server no longer has is shown as the server
          // default rather than as a blank select claiming nothing.
          if (self.form.engine && self.engines.indexOf(self.form.engine) === -1) self.form.engine = '';
          // The pair may be the same as on the last open, in which case the
          // watcher stays quiet - but the list behind it may have changed.
          if (self.voiceKey === keyBefore) self.fetchVoices();
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () { dropWait(self.wait, 'engines'); });
    },

    /* The voices of the pair in force. Answers arriving out of order are
       dropped by the serial, as in Studio.vue: two quick changes of engine
       would otherwise leave the first engine's voices under the second
       engine's name. A stored voice the new list does not carry falls back to
       the server default; the select cannot show a value it has no option
       for. */
    fetchVoices: function () {
      var self = this;
      var key = this.voiceKey;
      if (!key) return;
      var serial = ++this.voiceSerial;
      var parts = key.split('/');
      this.wait.push('voices');
      this.$http.get('/api/voices', { params: { engine: parts[0], language: parts[1] } })
        .then(function (resp) {
          if (serial !== self.voiceSerial) return;
          var data = resp.data || {};
          self.voices = data.voices || [];
          self.serverVoice = data['default'] || '';
          if (self.voices.indexOf(self.form.voice) === -1) self.form.voice = '';
        })
        .catch(function (err) {
          if (serial !== self.voiceSerial) return;
          self.voices = [];
          self.serverVoice = '';
          self.form.voice = '';
          self.error = self.$apiError(err);
        })
        .finally(function () { dropWait(self.wait, 'voices'); });
    },

    /* Save */

    saveStudio: function () {
      var kept = this.$savePrefs('studio', {
        engine: this.form.engine,
        language: this.form.language,
        voice: this.form.voice,
      });
      this.noteFailed = !kept;
      this.note = kept ? 'Saved.' : NOT_KEPT;
    },

    /* The switch, reported the way the theme toggle reports: a toast, because
       the operator's eye is on the checkbox and not on a note under another
       block's button. */
    saveView: function () {
      var kept = this.$savePrefs('view', { curl: this.curl });
      if (kept) return;
      this.$store.dispatch('push_toast', { level: 'warning', message: NOT_KEPT, ttl: 12000 });
    },
  },
};
</script>
