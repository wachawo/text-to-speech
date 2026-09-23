<template>
  <div class="tts-page tts-studio">

    <div class="form-check-inline m-1 d-flex flex-wrap row-gap-1 align-items-center">
      <div style="margin-right: 0.25rem">
        <div class="input-group input-group-sm" title="Engine">
          <select class="form-select form-select-sm" style="width: 130px"
                  v-model="form.engine" :disabled="wait.length > 0">
            <option v-for="name in engines" :key="name" :value="name">{{ name }}</option>
          </select>
        </div>
      </div>

      <div style="margin-right: 0.25rem">
        <div class="input-group input-group-sm" title="Language">
          <select class="form-select form-select-sm" style="width: 150px"
                  v-model="form.language" :disabled="wait.length > 0">
            <option v-for="lang in $languages" :key="lang.code" :value="lang.code">
              {{ lang.code }} {{ lang.name }}
            </option>
          </select>
        </div>
      </div>

      <div style="margin-right: 0.25rem">
        <!-- An engine that mixes takes free text with the list as suggestions;
             the datalist sits outside the group so the input keeps its right
             corners. -->
        <template v-if="voiceMix">
          <div class="input-group input-group-sm" title="Voice or mix, e.g. af_bella(2)+af_sky(1)">
            <input type="text" class="form-control form-control-sm" style="width: 220px"
                   list="studio-voices" placeholder="default" autocomplete="off" spellcheck="false"
                   maxlength="128" v-model="form.voice" :disabled="wait.length > 0">
          </div>
          <datalist id="studio-voices">
            <option v-for="name in voices" :key="name" :value="name"></option>
          </datalist>
        </template>
        <div class="input-group input-group-sm" title="Voice" v-else>
          <select class="form-select form-select-sm" style="width: 150px"
                  v-model="form.voice" :disabled="wait.length > 0 || voices.length === 0">
            <option value="">default</option>
            <option v-for="name in voices" :key="name" :value="name">{{ name }}</option>
          </select>
        </div>
      </div>

      <!-- A link, not a button: it goes somewhere rather than doing something,
           so it can be middle-clicked and opened in a new tab like any other
           route. .btn keeps it on the 24px rhythm of the row. -->
      <div style="margin-right: 0.25rem" v-if="form.engine === 'coquitts'">
        <router-link to="/voices" class="btn btn-sm btn-secondary fw-bold btn-w85"
                     title="Add a voice sample" aria-label="Add a voice sample">
          <i class="fa fa-plus"></i> VOICE
        </router-link>
      </div>

      <div style="margin-left: auto"></div>

      <div style="margin-right: 0.25rem" class="d-flex align-items-center">
        <small class="text-secondary">{{ form.text.length }} chars</small>
      </div>

      <div>
        <button type="button" class="btn btn-primary btn-sm fw-bold" style="min-width:100px"
                @click="generate" :disabled="!canGenerate">
          <i class="fa fa-play"></i> GENERATE
        </button>
      </div>
    </div>

    <!-- The health poll reports in the warning bar, on its own string: while
         the server is down the poll writes every five seconds, and written
         to `error` it would overwrite whatever a request had just said. -->
    <tts-alerts :wait="wait" :error.sync="error" :warning.sync="healthError"
                :info.sync="info" :success.sync="success"></tts-alerts>

    <div class="row g-2">
      <div class="col-lg-8">
        <textarea class="form-control" v-model="form.text"
                  placeholder="Type or paste the text to synthesize"
                  @keydown.ctrl.enter.prevent="generate"
                  @keydown.meta.enter.prevent="generate"></textarea>

        <!-- The take is fetched through axios (the token goes in the header,
             and a bare src could not carry it) and both the player and the
             SAVE link are pointed at the object URL of the Blob. -->
        <div class="tts-player mt-2">
          <template v-if="selected">
            <audio ref="player" controls :src="audioUrl || null"></audio>
            <a class="btn btn-sm btn-secondary fw-bold btn-w85" :href="audioUrl" :download="audioName"
               :class="{ disabled: !audioUrl }">
              <i class="fa fa-download"></i> SAVE
            </a>
            <small class="text-secondary">{{ summary }}</small>
          </template>
          <small class="text-secondary" v-else>Nothing generated yet</small>
        </div>

        <!-- The same request as GENERATE, written for a shell. Follows the
             selects and the editor live, so an operator who has found the
             voice they want leaves with the command that reproduces it. -->
        <div class="tts-card mt-2" v-if="$store.state.view.curl">
          <div class="fw-bold text-primary border-bottom pb-1 mb-1 d-flex align-items-center">
            <span>CURL</span>
            <span class="ms-auto"></span>
            <button type="button" class="btn btn-sm btn-secondary fw-bold btn-w85" title="Copy the command"
                    @click="copyCurl">
              <i class="fa fa-copy"></i> COPY
            </button>
          </div>
          <pre class="tts-code"><code>{{ curlCommand }}</code></pre>
        </div>
      </div>

      <div class="col-lg-4">
        <div class="tts-card p-0 overflow-hidden">
          <div class="table-responsive">
            <table class="table table-striped table-sm table-fixed mb-0">
              <caption>HISTORY</caption>
              <colgroup>
                <col style="width:28%">
                <col style="width:22%">
                <col style="width:14%">
                <col style="width:30%">
                <col style="width:6%">
              </colgroup>
              <thead>
                <tr>
                  <td>Time</td>
                  <td>Engine</td>
                  <td>Voice</td>
                  <td>Text</td>
                  <td></td>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id" class="cursor-pointer"
                    :class="{ 'table-active': selected && selected.id === item.id }"
                    :title="item.text" @click="select(item)">
                  <td class="td-ellipsis" :title="item.created_at">{{ fmtTime(item.created_at) }}</td>
                  <td class="td-ellipsis" :title="item.engine">{{ item.engine || '-' }}</td>
                  <td class="td-ellipsis" :title="item.voice">{{ item.voice || '-' }}</td>
                  <td class="td-ellipsis">{{ item.text || '-' }}</td>
                  <td class="td-actions" @click.stop>
                    <i class="fa fa-trash text-danger" title="Delete this item"
                       :class="{ disabled: wait.length > 0 }" @click="remove(item)"></i>
                  </td>
                </tr>
                <tr v-if="items.length === 0 && wait.length === 0">
                  <td colspan="5" class="text-center">No history yet</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="d-flex align-items-center gap-2 px-2 py-1">
            <small class="text-secondary">{{ total }} items</small>
            <button type="button" class="btn btn-sm btn-secondary fw-bold ms-auto btn-w85"
                    v-if="total > items.length"
                    @click="fetchMore" :disabled="wait.length > 0">LOAD MORE</button>
          </div>
        </div>
      </div>
    </div>

    <tts-confirm ref="confirm"></tts-confirm>
  </div>
</template>

<script>
/* The studio: text in, audio out, and the history of what came out.

   Every GENERATE is a new history item - editing the text after picking a
   row never touches that row, so "the same text with another voice" is a
   click on the row and a click on GENERATE.
*/

var PAGE_SIZE = 50;
var WARMUP_INFO = 'The server is warming up its engines';

/* The clipboard the old way, for a page the browser does not trust with
   navigator.clipboard - plain http from another host is the common case for
   a UI like this one. Answers whether the copy went through. */
var copyByTextarea = function (text) {
  if (typeof document === 'undefined' || !document.body) return false;
  var box = document.createElement('textarea');
  box.value = text;
  box.setAttribute('readonly', '');
  box.style.position = 'fixed';
  box.style.opacity = '0';
  document.body.appendChild(box);
  box.select();
  var copied;
  try {
    copied = document.execCommand('copy');
  } catch (err) {
    copied = false;
  }
  document.body.removeChild(box);
  return copied;
};

module.exports = {
  mixins: [TtsWait],

  data: function () {
    return {
      wait: [],
      error: '',
      // What the health poll has to say while the server does not answer.
      healthError: '',
      // Up until the first ok from /api/health; see pollHealth.
      info: WARMUP_INFO,
      success: '',
      form: { engine: '', language: 'en', voice: '', text: '' },
      items: [],
      total: 0,
      selected: null,
      // The object URL of the selected take's Blob and the file name SAVE
      // gives it; '' while the Blob is on its way.
      audioUrl: '',
      audioName: '',
      ready: false,
      elapsed: 0,
    };
  },

  created: function () {
    // Timers are kept off `data`: nothing renders from them, and a reactive
    // interval handle is just noise.
    this.healthTimer = null;
    this.elapsedTimer = null;
    // False until the engines and the first voices answer have been applied;
    // see the `choice` watcher.
    this.settled = false;
    this.fetchEngines();
    this.fetchHistory();
    this.pollHealth();
    this.healthTimer = setInterval(this.pollHealth, 5000);
  },

  beforeDestroy: function () {
    if (this.healthTimer) clearInterval(this.healthTimer);
    if (this.elapsedTimer) clearInterval(this.elapsedTimer);
    this.setAudio('', '');
  },

  computed: {
    canGenerate: function () {
      return this.wait.length === 0 && !!this.form.text.trim() && this.ready;
    },

    /* The catalogue, from the store: the engines this server has, its own
       defaults (kept for the case where a saved preference goes back to
       "server default"), and the voices of the pair in force. */
    engines: function () {
      return this.$store.state.catalog.engines;
    },
    serverEngine: function () {
      return this.$store.state.catalog.defaultEngine;
    },
    serverLanguage: function () {
      return this.$store.state.catalog.defaultLanguage;
    },
    voices: function () {
      var entry = this.$store.state.catalog.voices[this.voiceKey];
      return entry ? entry.voices : [];
    },
    /* Whether the engine in force blends voices; false until its list is in. */
    voiceMix: function () {
      var entry = this.$store.state.catalog.voices[this.voiceKey];
      return !!(entry && entry.mix);
    },

    /* "WAV - 4.2 s - 186 KB - generated in 3.1 s". The duration is only known
       for WAV, so an MP3 take simply has no duration part. */
    summary: function () {
      var item = this.selected;
      if (!item) return '';
      var parts = [(item.format || '-').toUpperCase()];
      if (item.seconds !== null && item.seconds !== undefined) parts.push(this.$fmtSeconds(item.seconds));
      parts.push(this.$fmtBytes(item.bytes));
      parts.push('generated in ' + this.$fmtSeconds(item.elapsed));
      return parts.join(' - ');
    },

    /* One key for the pair, so a row click that changes both the engine and
       the language asks for the voices once rather than once per field. */
    voiceKey: function () {
      return this.form.engine + '/' + this.form.language;
    },

    /* The three selects as one string, so one watcher sees a row click that
       moves all three as one change rather than three. */
    choice: function () {
      return this.form.engine + '/' + this.form.language + '/' + this.form.voice;
    },

    /* The request GENERATE would send, as a curl command line, addressed to
       the origin of this page. Single quotes in the text end the shell's
       quoting, so each becomes the '\'' spelling; everything else
       JSON.stringify has already escaped.

       The token is never printed: this card is the most copied and the most
       screenshotted part of the UI. When the server wants one the header is
       written against $TTS_TOKEN, for the shell to fill in; when it wants
       none there is no header line. */
    curlCommand: function () {
      var body = {
        text: this.form.text.trim() || 'Hello world',
        engine: this.form.engine,
        language: this.form.language,
      };
      if (this.form.voice) body.voice = this.form.voice;
      var json = JSON.stringify(body).split("'").join("'\\''");
      var ext = this.form.engine === 'gtts' ? 'mp3' : 'wav';
      var lines = ['curl -sS -X POST ' + window.location.origin + '/api/tts'];
      if (this.$store.state.auth.required) lines.push('-H "Authorization: Bearer $TTS_TOKEN"');
      lines.push("-H 'Content-Type: application/json'", "-d '" + json + "'", '-o out.' + ext);
      return lines.join(' \\\n  ');
    },
  },

  watch: {
    voiceKey: function () {
      this.fetchVoices();
    },

    /* The selects are remembered as the operator's choice - but only once the
       initial load has settled. Before that they move on their own, as the
       engines answer and then the voices, and a value written then would be
       the server's default filed as a preference: change TTS_ENGINE on the
       server afterwards and every browser would keep the old one. A row
       click counts as a choice - it moves the selects, and the take on the
       screen is the one the operator asked to see. */
    choice: function () {
      if (!this.settled) return;
      this.$savePrefs('studio', {
        engine: this.form.engine,
        language: this.form.language,
        voice: this.form.voice,
      });
    },

    /* A SAVE in the settings dialog while this screen is open lands here, and
       is applied the way a fresh open applies it: engine and language from
       the saved values when this server has them, else the server's own
       defaults. The screen's own saves pass through too, carrying what is
       already on the selects, so they move nothing. A saved engine or
       language change refetches the voices through voiceKey and the stored
       voice is picked up there; a voice-only change is applied directly when
       voiceKnown accepts it (a listed name, or a mix of listed names). */
    '$store.state.studio': function (prefs) {
      if (!this.settled) return;
      var self = this;
      var engine = this.engines.indexOf(prefs.engine) !== -1 ? prefs.engine : this.serverEngine;
      var language = this.$knownLanguage(prefs.language) ? prefs.language : this.serverLanguage;
      var moved = false;
      if (engine && this.engines.indexOf(engine) !== -1 && engine !== this.form.engine) {
        this.form.engine = engine;
        moved = true;
      }
      if (language && language !== this.form.language) {
        this.form.language = language;
        moved = true;
      }
      if (moved) return;
      if (prefs.voice && prefs.voice !== this.form.voice && self.voiceKnown(prefs.voice)) {
        this.form.voice = prefs.voice;
      }
    },
  },

  methods: {
    /* Health */

    /* Until the server says ok, GENERATE stays off and the info bar says why:
       the engines take minutes to warm on CPU, and a button that fails with
       502 for the first five minutes reads as a broken deploy rather than a
       server that is not ready yet. The bar is cleared on the first ok, and so
       is the poll's own warning. */
    pollHealth: function () {
      var self = this;
      this.$http.get('/api/health')
        .then(function (resp) {
          self.$store.state.health = resp.data;
          if (!resp.data || resp.data.status !== 'ok') return;
          self.ready = true;
          if (self.info === WARMUP_INFO) self.info = '';
          self.healthError = '';
          if (self.healthTimer) {
            clearInterval(self.healthTimer);
            self.healthTimer = null;
          }
          // The catalogue and the history asked for while the server was
          // still coming up got a 502 - ask again now that it answers, unless
          // the first request is still on its way.
          if (!self.form.engine && self.wait.indexOf('engines') === -1) self.fetchEngines();
          if (!self.items.length && self.wait.indexOf('history') === -1) self.fetchHistory();
        })
        .catch(function (err) {
          self.ready = false;
          self.info = WARMUP_INFO;
          self.healthError = self.$apiError(err);
        });
    },

    /* Catalogue */

    fetchEngines: function () {
      var self = this;
      this.waitPush('engines');
      this.$store.dispatch('fetch_engines')
        .then(function (catalog) {
          // The default is TTS_ENGINE as configured, reported whether or not
          // that engine is installed here; a blank select and a 503 on
          // GENERATE would follow from taking it on trust.
          // The remembered choice outranks the default, and either only when
          // this server has it: a browser that last picked coquitts on another
          // deployment must not open on a blank select here.
          var prefs = self.$store.state.studio;
          var engines = catalog.engines;
          var wanted = engines.indexOf(prefs.engine) !== -1 ? prefs.engine : catalog.defaultEngine;
          if (!self.form.engine || engines.indexOf(self.form.engine) === -1) {
            self.form.engine = engines.indexOf(wanted) !== -1 ? wanted : (engines[0] || '');
          }
          if (self.$knownLanguage(prefs.language)) self.form.language = prefs.language;
          else if (self.$knownLanguage(catalog.defaultLanguage)) self.form.language = catalog.defaultLanguage;
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () { self.waitDrop('engines'); });
    },

    /* Whether a voice value can stay on the control against the list in
       force; the rule is $knownVoice's, shared with the settings dialog. */
    voiceKnown: function (value) {
      return this.$knownVoice(value, this.voices, this.voiceMix);
    },

    /* The voices of the engine and language in force, through the store.
       The chosen voice is kept when the new list still knows it (every name
       of a mix) - a row click sets the voice before this runs, and the
       answer must not undo it - otherwise the remembered one, otherwise the
       server's default, otherwise the engine default. An answer for a pair
       the selects have since moved off is not applied: the store files it
       under its own pair, and `voices` reads the pair in force.

       The first answer applied is what settles the initial load. Marked on the
       next tick rather than here: the watcher that this answer's assignment
       queued runs before that tick, and must still find the flag down. */
    fetchVoices: function () {
      var self = this;
      if (!this.form.engine) return;
      var key = this.voiceKey;
      this.waitPush('voices');
      this.$store.dispatch('fetch_voices', { engine: this.form.engine, language: this.form.language })
        .then(function (data) {
          if (key !== self.voiceKey) return;
          if (self.form.voice && self.voiceKnown(self.form.voice)) return;
          var stored = self.$store.state.studio.voice;
          if (stored && self.voiceKnown(stored)) self.form.voice = stored;
          else self.form.voice = self.voices.indexOf(data['default']) !== -1 ? data['default'] : '';
        })
        .catch(function (err) {
          if (key !== self.voiceKey) return;
          self.form.voice = '';
          self.error = self.$apiError(err);
        })
        .finally(function () {
          self.waitDrop('voices');
          if (key === self.voiceKey && !self.settled) {
            self.$nextTick(function () { self.settled = true; });
          }
        });
    },

    /* History */

    fetchHistory: function () {
      var self = this;
      this.waitPush('history');
      this.$http.get('/api/history', { params: { limit: PAGE_SIZE } })
        .then(function (resp) {
          self.items = resp.data.items || [];
          self.total = resp.data.total || 0;
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () { self.waitDrop('history'); });
    },

    fetchMore: function () {
      var self = this;
      this.waitPush('history');
      this.$http.get('/api/history', { params: { limit: PAGE_SIZE, offset: this.items.length } })
        .then(function (resp) {
          self.items = self.items.concat(resp.data.items || []);
          self.total = resp.data.total || 0;
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () { self.waitDrop('history'); });
    },

    /* The clock, not the date, for a take made today: the date column is
       where the eye lands to tell "just now" from "yesterday", and the full
       stamp is one hover away in the title. Compared as text against the
       browser's own date - the stamp is in the server's zone, and near
       midnight the two can disagree by a day, which is worth less than a
       Date-parsing round trip for every row. */
    fmtTime: function (stamp) {
      if (!stamp) return '-';
      var now = new Date();
      var today = now.getFullYear() + '-' +
        String(now.getMonth() + 1).padStart(2, '0') + '-' +
        String(now.getDate()).padStart(2, '0');
      var date = stamp.slice(0, 10);
      // Today by the clock alone; any other day as MM-DD HH:MM - the year is
      // never the fact being looked for in a list of recent takes.
      return date === today ? stamp.slice(11, 16) : stamp.slice(5, 16);
    },

    /* Generate */

    generate: function () {
      var self = this;
      if (!this.canGenerate) return;
      var body = {
        text: this.form.text,
        engine: this.form.engine,
        language: this.form.language,
        voice: this.form.voice || undefined,
      };
      this.error = '';
      this.elapsed = 0;
      var label = 'generating 0s';
      this.waitPush(label);
      // Seconds ticking in the wait strip: a CPU take of a paragraph runs into
      // minutes, and a spinner that does not count is a spinner that may have
      // stopped. The label is replaced in place and dropped under its last
      // text.
      this.elapsedTimer = setInterval(function () {
        self.elapsed += 1;
        var next = 'generating ' + self.elapsed + 's';
        var i = self.wait.indexOf(label);
        if (i !== -1) self.wait.splice(i, 1, next);
        label = next;
      }, 1000);
      this.$http.post('/api/history', body)
        .then(function (resp) {
          var item = resp.data;
          self.items.unshift(item);
          self.total += 1;
          self.selected = item;
          // After the tick that puts the URL on the player.
          self.loadAudio(item).then(function () { self.$nextTick(self.play); });
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () {
          clearInterval(self.elapsedTimer);
          self.elapsedTimer = null;
          self.waitDrop(label);
        });
    },

    /* Audio */

    /* Point the player and SAVE at a new object URL, or at nothing. The old
       one is revoked either way: each pins its Blob in memory until the
       document goes away, and a studio used all afternoon would hold every
       take ever listened to. */
    setAudio: function (url, name) {
      if (this.audioUrl) URL.revokeObjectURL(this.audioUrl);
      this.audioUrl = url;
      this.audioName = name;
    },

    /* The take's audio as a Blob, fetched through axios so the request
       carries the token - a bare <audio src> or <a href> cannot, and a server
       with TTS_TOKENS answers them 401. An answer for a row that is no longer
       the selected one is dropped. Resolves once the player has the URL, or
       at once when there is nothing to fetch. */
    loadAudio: function (item) {
      var self = this;
      this.setAudio('', '');
      if (!item) return Promise.resolve();
      this.waitPush('audio');
      return this.$http.get('/api/history/' + item.id + '/audio', { responseType: 'blob' })
        .then(function (resp) {
          if (!self.selected || self.selected.id !== item.id) return;
          var type = String(resp.headers['content-type'] || '');
          var ext = type.indexOf('audio/mpeg') === 0 ? 'mp3' : (item.format || 'wav');
          self.setAudio(URL.createObjectURL(resp.data), 'tts_' + item.id + '.' + ext);
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () { self.waitDrop('audio'); });
    },

    /* Autoplay may be refused - a browser that has not seen a click on this
       page yet says so with a rejected promise, or throws outright - and a
       refused autoplay is not an error: the take is on the player, and the
       play button is right there. */
    play: function () {
      var player = this.$refs.player;
      if (!player) return;
      try {
        var started = player.play();
        if (started && started.catch) started.catch(function () {});
      } catch (err) {
        // Nothing to report: see above.
      }
    },

    /* Copy */

    /* navigator.clipboard first, the textarea trick where the browser has
       none or refuses; a toast either way, because a COPY that says nothing
       is a COPY the operator presses three times and then pastes the wrong
       thing. */
    copyCurl: function () {
      var self = this;
      var text = this.curlCommand;
      var done = function () {
        self.$store.dispatch('push_toast', { level: 'success', message: 'Copied', ttl: 3000 });
      };
      var fallback = function () {
        if (copyByTextarea(text)) return done();
        self.$store.dispatch('push_toast', {
          level: 'danger',
          message: 'This browser would not copy - select the command and copy it by hand.',
        });
      };
      if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, fallback);
      } else {
        fallback();
      }
    },

    /* Select */

    /* A row click puts the take back on the screen: its text in the editor,
       its audio on the player, its engine, language and voice in the selects.
       The list carries a preview cut at 200 characters, so a row ending in
       "..." is fetched in full before it goes into the editor - a take
       regenerated from the preview would be a take of the first 200
       characters. */
    select: function (item) {
      var self = this;
      this.selected = item;
      this.loadAudio(item);
      this.form.engine = item.engine || this.form.engine;
      this.form.language = item.language || this.form.language;
      this.form.voice = item.voice || '';
      if (!/\.\.\.$/.test(item.text || '')) {
        this.form.text = item.text || '';
        return;
      }
      this.waitPush('text');
      this.$http.get('/api/history/' + item.id)
        .then(function (resp) {
          // Only if the row is still the one open: a second click during the
          // round trip must not have its text replaced by the first one's.
          if (self.selected && self.selected.id === item.id) self.form.text = resp.data.text || '';
        })
        .catch(function (err) { self.error = self.$apiError(err); })
        .finally(function () { self.waitDrop('text'); });
    },

    /* Delete */

    remove: function (item) {
      var self = this;
      var head = (item.text || '').slice(0, 60);
      if (!this.$refs.confirm) return;
      this.$refs.confirm.ask({
        title: 'DELETE HISTORY ITEM',
        body: 'Delete "' + head + '"? The audio file is removed as well.',
        label: 'DELETE',
        danger: true,
      }).then(function (ok) {
        if (!ok) return;
        self.waitPush('deleting');
        self.$http.delete('/api/history/' + item.id)
          .then(function () {
            var i = self.items.findIndex(function (row) { return row.id === item.id; });
            if (i !== -1) self.items.splice(i, 1);
            self.total = Math.max(0, self.total - 1);
            if (self.selected && self.selected.id === item.id) {
              self.selected = null;
              self.setAudio('', '');
            }
          })
          .catch(function (err) { self.error = self.$apiError(err); })
          .finally(function () { self.waitDrop('deleting'); });
      });
    },
  },
};
</script>
