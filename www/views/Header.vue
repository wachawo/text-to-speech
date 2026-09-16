<template>
  <header class="tts-header">
    <ul>
      <li class="navbar-brand">
        <router-link to="/studio">TTS</router-link>
      </li>

      <!-- The sign-in screen gets the brand alone: the tabs lead to screens
           that would only send the visitor back here. -->
      <template v-if="$route.name !== 'login'">
      <li class="nav-item" :class="{ active: tabActive('/studio') }">
        <router-link to="/studio">STUDIO</router-link>
      </li>
      <li class="nav-item" :class="{ active: tabActive('/voices') }">
        <router-link to="/voices">VOICES</router-link>
      </li>
      <li class="nav-item" :class="{ active: tabActive('/models') }">
        <router-link to="/models">MODELS</router-link>
      </li>

      <li class="m-auto"></li>

      <!-- Light or dark. In the bar rather than on a settings screen: it is
           the one setting an operator changes because of the room they are
           sitting in, and a setting they have to navigate away from their work
           to reach is one they change and then have to find their way back
           from.

           A real <button>, so it is reachable by keyboard and announced as a
           control; the glyph alone would be a decoration to a screen reader.
           `title` and `aria-label` carry the same sentence and both name the
           theme it switches TO - a control labelled with the state it is in
           reads, to whoever meets it first, as the state it will produce. -->
      <li class="nav-item nav-theme">
        <button type="button" class="tts-theme-toggle"
          @click="toggleTheme" :title="themeAction" :aria-label="themeAction">
          <i class="fa" :class="darkTheme ? 'fa-sun' : 'fa-moon'"></i>
        </button>
      </li>

      <!-- The settings, behind a gear rather than on a tab: two blocks about
           this browser - what the studio opens with, what the screens show -
           and nothing about the server, so there is nothing to link to or
           bookmark. Right of the theme switch, in the same reset, because both
           are about this browser and the operator finds them by moving to the
           right edge.

           The gear only raises a flag in the store. The dialog itself is
           rendered by the App root beside the toaster, not here: the bar
           paints every link and control inside it in the bar's own ink, and a
           dialog left in this subtree would have its labels and its selects
           drawn white on white. -->
      <li class="nav-item nav-theme">
        <button type="button" class="tts-theme-toggle"
          title="Settings" aria-label="Settings" @click="openSettings">
          <i class="fa fa-gear"></i>
        </button>
      </li>

      <!-- The way out, only when there was a way in: a server without tokens
           has nothing to sign out of. -->
      <li class="nav-item nav-theme" v-if="signedIn">
        <button type="button" class="tts-theme-toggle"
          title="Sign out" aria-label="Sign out" @click="logout">
          <i class="fa fa-right-from-bracket"></i>
        </button>
      </li>
      </template>
    </ul>
  </header>
</template>

<script>
/* The screens a tab stands for beyond its own path. Empty while every screen is
   its own tab; the lookup falls back to the tab's path. Kept as a table so a
   route added later is either owned by a tab or visibly owned by none - a page
   where nothing in the row lights up reads as a broken app rather than as a
   sub-page. */
var TAB_ROUTES = {};

module.exports = {
  computed: {
    signedIn: function () {
      var auth = this.$store.state.auth;
      return !!(auth && auth.required && auth.token);
    },

    /* Which half of the palette is in force. Read from the store rather than off
       the document element: app.js is what owns the attribute, and a bar that
       read the DOM back would show the wrong glyph for as long as it took Vue to
       notice a change it has no way of noticing. */
    darkTheme: function () {
      return this.$store.state.theme === 'dark';
    },
    themeAction: function () {
      return this.darkTheme ? 'Switch to the light theme' : 'Switch to the dark theme';
    },
  },

  mounted: function () {
    this.watchBarHeight();
  },

  beforeDestroy: function () {
    this.releaseBarHeight();
  },

  methods: {
    /* Forget the token and go to the sign-in screen. Nothing to tell the
       server: a bearer token has no session behind it. */
    logout: function () {
      this.$saveToken('');
      this.$goto('/login');
    },

    /* Whether a tab is the one the operator is on. By path rather than by
       name, through TAB_ROUTES, so a screen that belongs to a tab without
       being it can be declared rather than guessed. */
    tabActive: function (own) {
      var owned = TAB_ROUTES[own] || [own];
      return owned.indexOf(this.$route.path) !== -1;
    },

    /* Publish how tall this bar is, for the dialogs that open under it.

       Every modal in this UI is offset by `--tts-header-height`, and the bar is
       the only thing that knows the answer - so it is the bar that measures and
       publishes it, once, on the document element. A dialog measuring for itself
       would be one measurement per dialog, and the one that forgot would open
       across the tabs.

       Watched rather than measured once: the bar wraps onto a second line on a
       narrow window, so the height changes without anything else on the page
       changing. ResizeObserver sees that; a window listener is the fallback for
       a browser without it.

       The value is published as a pixel string because that is what the CSS
       consumes. A bar that measures zero - hidden, or not laid out yet - leaves
       the declared floor in place rather than collapsing every dialog to the top
       of the screen. */
    watchBarHeight: function () {
      var self = this;
      this.publishBarHeight();
      if (typeof ResizeObserver === 'function' && this.$el && this.$el.nodeType === 1) {
        this.barWatcher = new ResizeObserver(function () { self.publishBarHeight(); });
        this.barWatcher.observe(this.$el);
        return;
      }
      this.barResizeHandler = function () { self.publishBarHeight(); };
      window.addEventListener('resize', this.barResizeHandler);
    },

    publishBarHeight: function () {
      var root = document.documentElement;
      var bar = this.$el;
      if (!root || !root.style || !bar || !bar.getBoundingClientRect) return;
      var height = Math.round(bar.getBoundingClientRect().height);
      if (height > 0) {
        root.style.setProperty('--tts-header-height', height + 'px');
      } else {
        root.style.removeProperty('--tts-header-height');
      }
    },

    /* The observer and the published value both go when the bar does. A value
       left on the document outlives the element it measured. */
    releaseBarHeight: function () {
      if (this.barWatcher) {
        this.barWatcher.disconnect();
        this.barWatcher = null;
      }
      if (this.barResizeHandler) {
        window.removeEventListener('resize', this.barResizeHandler);
        this.barResizeHandler = null;
      }
      if (document.documentElement && document.documentElement.style) {
        document.documentElement.style.removeProperty('--tts-header-height');
      }
    },

    /* The switch. `$saveTheme` repaints the page and answers whether this browser
       agreed to remember it; the toast is for the case where it did not. Without
       it the operator picks dark, gets dark, reloads tomorrow and finds light -
       with nothing anywhere to say the server is not at fault. */
    toggleTheme: function () {
      var kept = this.$saveTheme(this.darkTheme ? 'light' : 'dark');
      if (kept) return;
      this.$store.dispatch('push_toast', {
        level: 'warning',
        message: 'This browser would not store the setting, so it holds until the page is reloaded.',
        ttl: 12000,
      });
    },

    /* Ask for the dialog. The flag is the whole contract between the bar and
       the dialog: it watches the flag, opens, and clears it once closed. */
    openSettings: function () {
      this.$store.state.settingsOpen = true;
    },
  },
};
</script>
