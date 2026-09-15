<template>
  <div class="tts-page">

    <!-- One control, and it stands alone on the right: there is nothing to
         filter on a screen whose whole job is two short lists. -->
    <div class="form-check-inline m-1 d-flex flex-wrap row-gap-1 align-items-center">
      <div style="margin-left:auto"></div>
      <div>
        <button type="button" class="btn btn-sm btn-secondary fw-bold" style="min-width:100px"
                title="Ask the server again what is installed"
                :disabled="wait.length > 0" @click="reload">
          <i class="fa fa-rotate"></i> RELOAD
        </button>
      </div>
    </div>

    <div class="alert alert-secondary text-center p-1 mb-2" v-show="wait.length > 0">
      <i class="fa fa-spinner fa-pulse"></i> {{ wait.join(', ') }}
    </div>
    <tts-alerts :error.sync="error" :warning.sync="warning"
                :info.sync="info" :success.sync="success"></tts-alerts>

    <!-- ENGINES: every engine this build knows about, one row each, and the
         two facts the server holds about it - whether its dependencies are
         importable here, and whether it is warmed up at start.

         A missing engine is tinted and its title says how to install it.
         Installing from the browser is deliberately not offered: it is a pip
         run plus gigabytes of model downloads inside the server container,
         and a button here would either time out or leave a half-installed
         engine nobody can see. `ttsgen --install <name>` and TTS_ENGINES in
         the compose file remain the only two ways. -->
    <div class="tts-card p-0 overflow-hidden mb-2">
      <div class="table-responsive">
        <table class="table table-striped table-sm table-fixed mb-0">
          <caption>ENGINES</caption>
          <colgroup>
            <col style="width:30%">
            <col style="width:20%">
            <col style="width:20%">
            <col style="width:15%">
            <col style="width:15%">
          </colgroup>
          <thead>
            <tr>
              <td>NAME</td>
              <td>STATUS</td>
              <td>PRELOADED</td>
              <td>DEFAULT</td>
              <td>LANGUAGE</td>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in engineRows" :key="row.name"
                :class="{ 'row-warning': !row.installed }"
                :title="row.installed ? null : installHint(row.name)">
              <td class="td-ellipsis" :title="row.name">{{ row.name }}</td>
              <td :class="{ 'tts-state-on': row.installed }">
                {{ row.installed ? 'installed' : 'missing' }}
              </td>
              <td>{{ row.preloaded ? 'yes' : '-' }}</td>
              <td>{{ row.isDefault ? 'yes' : '-' }}</td>
              <td>{{ row.isDefault ? (engines.language || '-') : '-' }}</td>
            </tr>
            <tr v-if="engineRows.length === 0 && wait.length === 0">
              <td colspan="5" class="text-center">-</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- MODELS: the same rows `ttsgen --list` prints inside the container,
         one per model file on disk, or one per engine with a note where the
         engine ships no files (cloud and system voices). -->
    <div class="tts-card p-0 overflow-hidden">
      <div class="table-responsive">
        <table class="table table-striped table-sm table-fixed mb-0">
          <caption>MODELS</caption>
          <colgroup>
            <col style="width:25%">
            <col style="width:15%">
            <col style="width:60%">
          </colgroup>
          <thead>
            <tr>
              <td>ENGINE</td>
              <td>STATUS</td>
              <td>MODEL</td>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in models" :key="row.engine + ':' + row.model + ':' + index"
                :class="{ 'row-warning': row.status !== 'installed' }"
                :title="row.status === 'installed' ? null : installHint(row.engine)">
              <td class="td-ellipsis" :title="row.engine">{{ row.engine || '-' }}</td>
              <td :class="{ 'tts-state-on': row.status === 'installed' }">
                {{ row.status || '-' }}
              </td>
              <td class="td-ellipsis" :title="row.model">{{ row.model || '-' }}</td>
            </tr>
            <tr v-if="models.length === 0 && wait.length === 0">
              <td colspan="3" class="text-center">-</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>

<script>
/* What is installed on this server: the engines the build knows about and
   the model files each one has on disk. Read-only - both lists are facts
   about the container, and the only things that change them are a pip run
   and a download, neither of which belongs behind a button in a browser. */

module.exports = {
  data: function () {
    return {
      wait: [],
      error: '',
      warning: '',
      info: '',
      success: '',
      // The /api/engines answer as sent: supported, available, preload,
      // default, language. Kept whole rather than unpacked so the template
      // can read the default language off the same object as the default
      // engine.
      engines: { supported: [], available: [], preload: [], default: '', language: '' },
      // The /api/models rows as sent: {engine, status, model}.
      models: [],
    };
  },

  computed: {
    /* One row per supported engine, with the three memberships resolved
       here rather than in the template - a template doing indexOf four
       times per row is a template nobody can read. */
    engineRows: function () {
      var engines = this.engines;
      var available = engines.available || [];
      var preload = engines.preload || [];
      return (engines.supported || []).map(function (name) {
        return {
          name: name,
          installed: available.indexOf(name) !== -1,
          preloaded: preload.indexOf(name) !== -1,
          isDefault: name === engines.default,
        };
      });
    },
  },

  created: function () {
    this.reload();
  },

  methods: {
    /* The tooltip on a missing engine: the two ways it can be installed,
       neither of them from here. */
    installHint: function (name) {
      return 'Install with: ttsgen --install ' + name +
        ' or add it to TTS_ENGINES in the compose file';
    },

    reload: function () {
      this.error = '';
      this.fetchEngines();
      this.fetchModels();
    },

    fetchEngines: function () {
      var self = this;
      self.wait.push('engines');
      self.$http.get('/api/engines').then(function (resp) {
        self.engines = resp.data || {};
      }).catch(function (err) {
        self.error = self.$apiError(err);
      }).finally(function () {
        var i = self.wait.indexOf('engines');
        if (i !== -1) self.wait.splice(i, 1);
      });
    },

    fetchModels: function () {
      var self = this;
      self.wait.push('models');
      self.$http.get('/api/models').then(function (resp) {
        self.models = (resp.data && resp.data.models) || [];
      }).catch(function (err) {
        self.error = self.$apiError(err);
      }).finally(function () {
        var i = self.wait.indexOf('models');
        if (i !== -1) self.wait.splice(i, 1);
      });
    },
  },
};
</script>
