<template>
  <div id="loginPage">
    <main>
      <article>
        <form class="login" @submit.prevent="submit">
          <div class="input-group input-group-sm mb-1">
            <span class="input-group-text"><label for="login-token">Token</label></span>
            <input id="login-token" ref="token" class="form-control form-control-sm"
                   type="password" name="token" v-model="token" autocomplete="current-password"
                   :disabled="wait.length > 0" />
          </div>

          <div class="input-group input-group-sm mb-1">
            <button class="form-control form-control-sm btn btn-sm btn-primary fw-bold"
                    type="submit" :disabled="wait.length > 0">
              <i class="fa fa-spinner fa-pulse me-1" v-if="wait.length > 0"></i>
              <i class="fa fa-right-to-bracket me-1" v-else></i>
              <span>{{ wait.length > 0 ? 'SIGNING IN' : 'SIGN IN' }}</span>
            </button>
          </div>

          <div class="alert alert-danger p-1 mb-0 d-flex align-items-center cursor-pointer"
               v-if="error" @click="error = ''" title="Dismiss">
            <div class="m-auto text-center">{{ error }}</div>
            <i class="fa fa-times"></i>
          </div>
        </form>
      </article>
    </main>
  </div>
</template>

<script>
/* The sign-in screen: one field for the API token the server was started
   with (TTS_TOKENS). The token is tried against /api/engines - the cheapest
   route behind the token check - and kept in this browser only after the
   server has accepted it, so a typo never becomes a stored credential that
   401s on every screen. */
module.exports = {
  data: function () {
    return {
      token: '',
      wait: [],
      error: '',
    };
  },

  mounted: function () {
    // `autofocus` is inert on an element inserted after the document loaded,
    // and the router mounts this form long after.
    if (this.$refs.token) this.$refs.token.focus();
  },

  methods: {
    submit: function () {
      var self = this;
      var token = self.token.trim();
      if (!token) return;
      self.error = '';
      self.wait.push('signing in');
      // X-Tts-Probe marks this request for the 401 interceptor: a refusal
      // here is "wrong token", not a lost session to bounce back from.
      self.$http.get('/api/engines', { headers: { Authorization: 'Bearer ' + token, 'X-Tts-Probe': '1' } })
        .then(function () {
          var kept = self.$saveToken(token);
          self.token = '';
          if (!kept) {
            self.$store.dispatch('push_toast', {
              level: 'warning',
              message: 'This browser would not store the token, so it holds until the page is reloaded.',
              ttl: 12000,
            });
          }
          self.$goto(self.$internalPath(self.$route.query.next) || '/studio');
        })
        .catch(function (err) {
          if (err && err.response && err.response.status === 401) self.error = 'Wrong token';
          else self.error = self.$apiError(err);
        })
        .finally(function () {
          var i = self.wait.indexOf('signing in');
          if (i !== -1) self.wait.splice(i, 1);
        });
    },
  },
};
</script>
