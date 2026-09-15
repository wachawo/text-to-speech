/* TTS - Vue 2 entry point.
   - Hash-mode router with named routes and no guard: the web UI has no
     sign-in, nginx carries the API token on its behalf
   - Minimal Vuex: the toasts, the theme in force, the two preference groups,
     whether the settings dialog is asked for, the last health answer
   - Shared formatters, so every screen prints a size and a duration the same
     way
   - Shared error unwrapping, so no screen shows the operator raw JSON
*/

Vue.prototype.$http = axios;

Vue.use(httpVueLoader);
Vue.use(Vuex);

/* The one place an axios failure becomes a sentence for an alert box.

   The API reports failures as {"error": "...", "request_id": "..."}, and an
   engine that failed on purpose adds a "message" to that - the sentence a
   person can act on, where "error" is the short name of the class. The
   request id goes on the end in brackets: it is the one thing the operator
   can quote that finds the same failure in the server log. */
const apiError = function (err) {
  var data = err && err.response && err.response.data;
  var text = '';
  if (data && typeof data === 'object') {
    if (typeof data.message === 'string' && data.message) text = data.message;
    else if (typeof data.error === 'string' && data.error) text = data.error;
    else if (data.error) text = JSON.stringify(data.error);
    if (text && data.request_id) text += ' (request ' + data.request_id + ')';
  } else if (typeof data === 'string' && data && data.charAt(0) !== '<') {
    // A plain-text body is a sentence; a body that opens a tag is a proxy's
    // own error page, and the status line below says the same thing shorter.
    text = data;
  }
  if (text) return text;
  if (err && err.response) return err.response.status + ' ' + err.response.statusText;
  return (err && err.message) || 'The request failed';
};
Vue.prototype.$apiError = apiError;

/* Screens are loaded from .vue files at runtime - there is no build step.
   A screen whose file is missing must not take the shell down with it: the
   header and the router keep working, and the router-view says which file
   did not load.

   The fallback is resolved here rather than handed to vue-router as the
   `{component, error}` factory form: that form is Vue's own and vue-router 3
   does not read it - a rejected loader aborts the navigation, so the address
   stays where it was and the fallback never renders. Catching the rejection
   and answering the placeholder is what lets the navigation finish. */
const MissingScreen = {
  template:
    '<div class="tts-page">' +
    '<div class="tts-card">' +
    '<div class="label">Screen unavailable</div>' +
    '<div class="sub">This screen is not installed in this build. ' +
    'Expected the component file to be served from /views/.</div>' +
    '</div></div>',
};

const screen = function (name) {
  var load = httpVueLoader('/views/' + name + '.vue');
  return function () {
    return load().catch(function () { return MissingScreen; });
  };
};

/* The furniture every screen shares, registered once rather than through a
   `components:` block per screen - one screen keeping its own loader is how
   two copies of the same control end up drifting apart.

   `tts-alerts` is the four bars - error, warning, info, success - each bound
   with `.sync` to a string on the screen. `tts-confirm` is the only dialog
   allowed to stand in front of a destructive action; `window.confirm` is what
   it replaces and no screen may go back to it. `tts-header`, `tts-toaster`
   and `tts-settings` are the shell's own and are rendered by the App root
   below - the settings dialog beside the header, not inside it, because the
   bar paints everything in it in its own ink. */
Vue.component('tts-alerts',   httpVueLoader('/views/Alerts.vue'));
Vue.component('tts-confirm',  httpVueLoader('/views/Confirm.vue'));
Vue.component('tts-toaster',  httpVueLoader('/views/Toaster.vue'));
Vue.component('tts-header',   httpVueLoader('/views/Header.vue'));
Vue.component('tts-settings', httpVueLoader('/views/Settings.vue'));

/* Shared formatters. Two screens print a file size and a duration, and a
   size written "186 KB" on one and "186.0 KB" on the other reads as two
   different numbers. */
const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

/* Bytes as a short figure: "186 KB", "1.2 MB". Whole numbers below a
   kilobyte and from 10 up, one decimal in between - the decimal is what tells
   1.2 MB from 1.9 MB, and past ten it is noise. Null and anything unusable
   print as "-" rather than "0 B", which would claim a size nobody measured. */
Vue.prototype.$fmtBytes = function (value) {
  if (value === null || value === undefined || value === '') return '-';
  var bytes = Number(value);
  if (!isFinite(bytes) || bytes < 0) return '-';
  var index = 0;
  while (bytes >= 1024 && index < UNITS.length - 1) {
    bytes /= 1024;
    index += 1;
  }
  var figure = (index === 0 || bytes >= 10) ? Math.round(bytes).toString() : bytes.toFixed(1);
  return figure + ' ' + UNITS[index];
};

/* Seconds with one decimal and the unit: 4.2 -> "4.2 s". Null, undefined and
   anything that is not a number print as "-" rather than "NaN s". */
Vue.prototype.$fmtSeconds = function (value) {
  if (value === null || value === undefined || value === '') return '-';
  var seconds = Number(value);
  if (!isFinite(seconds)) return '-';
  return seconds.toFixed(1) + ' s';
};

/* localStorage, or null where there is none.

   A browser with site data switched off throws on the property itself rather
   than answering undefined, and this file is also run by syntax checks in a
   sandbox where the global is simply absent. Either way the app has to start:
   the preference becomes the default, not a ReferenceError thrown before the
   router exists. */
const browserStorage = function () {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch (err) {
    return null;
  }
};

/* Light or dark, chosen by the operator.

   A view preference belonging to this browser rather than configuration
   belonging to the server, so it lives in this browser's localStorage under
   one key. Only the two spellings are accepted on the way in as well as on
   the way out: the stored text is hand-editable, and `data-theme="sepia"` is
   a document that matches neither half of the palette and renders with no
   theme at all. The same key and the same rule as the inline guard in
   index.html, which sets the attribute before the stylesheets load. */
const THEME_KEY = 'tts.theme';
const THEMES = ['light', 'dark'];

/* What the operator's own system asks for, and the answer for an operator
   whose browser will not say. This is the default and only the default - a
   stored choice outranks it, because somebody who has picked dark on a light
   desktop picked it on purpose. */
const systemTheme = function () {
  try {
    if (typeof window === 'undefined' || !window || !window.matchMedia) return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch (err) {
    return 'light';
  }
};

const readTheme = function () {
  var box = browserStorage();
  var stored = null;
  if (box) {
    try {
      stored = box.getItem(THEME_KEY);
    } catch (err) {
      stored = null;
    }
  }
  return THEMES.indexOf(stored) === -1 ? systemTheme() : stored;
};

/* Both attributes, on the document element.

   `data-theme` is what css/main.css keys its dark palette on. `data-bs-theme`
   is what Bootstrap 5.3 keys its own on, and every dialog, input, pagination
   edge and close glyph on these screens is Bootstrap's - setting only ours
   would give a dark page full of white modals.

   Guarded rather than assumed: this file is also run by syntax checks against
   no document at all, and an app that throws here is an app that never
   reaches the router. */
const applyTheme = function (theme) {
  var root = (typeof document === 'undefined' || !document) ? null : document.documentElement;
  if (!root || !root.setAttribute) return;
  root.setAttribute('data-theme', theme);
  root.setAttribute('data-bs-theme', theme);
};

/* Applied here, as the file loads, and not from a mounted hook.

   Everything below this line is the app being assembled; the attribute is on
   the document before any of it runs. Set later, every load would paint the
   light palette, hold it, and then flip, and that flash is on every page an
   operator opens all day. */
const startingTheme = readTheme();
applyTheme(startingTheme);

/* The other two preferences of this browser: what the studio opens with, and
   what the screens show. Same home as the theme - localStorage, one key per
   group, 'tts.view' and 'tts.studio' - and the same rule on the way in: only
   the fields named here, only in the type named here, anything else the
   default. The stored text is hand-editable, and a `curl: "no"` read as
   truthy would be a checkbox that cannot be switched off.

   An empty string in the studio group means the server's own default -
   TTS_ENGINE, TTS_LANGUAGE, COQUITTS_SAMPLE - so a browser that never chose
   follows the deployment rather than a value baked into this file. */
const PREFS_PREFIX = 'tts.';
const PREFS = {
  view:   { curl: true },
  studio: { engine: '', language: '', voice: '' },
};

const validatePrefs = function (name, value) {
  var defaults = PREFS[name];
  var given = (value && typeof value === 'object') ? value : {};
  var clean = {};
  Object.keys(defaults).forEach(function (key) {
    var fallback = defaults[key];
    clean[key] = typeof given[key] === typeof fallback ? given[key] : fallback;
  });
  return clean;
};

const readPrefs = function (name) {
  var box = browserStorage();
  var stored = null;
  if (box) {
    try {
      stored = JSON.parse(box.getItem(PREFS_PREFIX + name));
    } catch (err) {
      // Nothing stored, or text that is not JSON any more: the defaults.
      stored = null;
    }
  }
  return validatePrefs(name, stored);
};

/* Global toast notifications.
   Pushed from anywhere via `this.$store.dispatch('push_toast', {...})`.
   Auto-dismissed after `ttl` ms (default 8000). Ids come off a counter: two
   toasts pushed in the same millisecond must still be two keys. */
var toastSerial = 0;

const push_toast = function (context, payload) {
  toastSerial += 1;
  var toast = Object.assign(
    { level: 'info', message: '', ttl: 8000 },
    payload,
    { id: toastSerial }
  );
  context.state.toasts.push(toast);
  setTimeout(function () {
    var i = context.state.toasts.findIndex(function (t) { return t.id === toast.id; });
    if (i !== -1) context.state.toasts.splice(i, 1);
  }, toast.ttl);
};

const dismiss_toast = function (context, id) {
  var i = context.state.toasts.findIndex(function (t) { return t.id === id; });
  if (i !== -1) context.state.toasts.splice(i, 1);
};

const state = {
  toasts: [],
  // The theme in force, always resolved to one of the two rather than left as
  // "whatever was stored": the header toggle reads this to know which way to
  // flip and which glyph to show, and "nothing stored yet" is not an answer to
  // either question. Already applied to the document above - this is the copy
  // the interface reads, and it is what holds the setting for the rest of the
  // session in a browser that refused to keep it.
  theme: startingTheme,
  // The last answer from /api/health, or null before the first one. The studio
  // polls it while the engines warm up and publishes what it got here, so a
  // screen opened later does not have to ask again to know the server is
  // ready.
  health: null,
  // The two preference groups, already validated. Screens read these and
  // never localStorage: the store is the copy that holds for the session in
  // a browser that refused to keep them, and it is what a screen can watch.
  // Replaced whole by $savePrefs, never edited in place, so a watcher on the
  // object fires.
  view: readPrefs('view'),
  studio: readPrefs('studio'),
  // Whether the settings dialog is asked for. The gear in the header sets it,
  // the dialog watches it and clears it once it has closed - the two never
  // hold a reference to each other, and the dialog is not rendered inside the
  // bar (see Header.vue for why).
  settingsOpen: false,
};

const actions = {
  push_toast,
  dismiss_toast,
};

const store = new Vuex.Store({ state, actions });

/* Write the theme: to storage, to the store so the header re-renders, and to
   the document so the page changes under it.

   Answers false when the browser refused to keep it. The setting is in force
   either way, which is the point of putting it in the store as well as in
   storage: a browser with site data switched off gets the theme it asked for
   until the tab is reloaded, rather than a control that visibly does nothing -
   and the header says so, because otherwise the operator picks dark, reloads
   tomorrow, finds light, and nothing anywhere says the server is not at
   fault. */
Vue.prototype.$saveTheme = function (next) {
  var theme = THEMES.indexOf(next) === -1 ? 'light' : next;
  var box = browserStorage();
  var kept = false;
  if (box) {
    try {
      box.setItem(THEME_KEY, theme);
      kept = true;
    } catch (err) {
      // A full quota, or storage in read-only mode. Reported to the caller
      // rather than swallowed: the alternative is a switch that silently
      // forgets itself on the next load.
      kept = false;
    }
  }
  store.state.theme = theme;
  applyTheme(theme);
  return kept;
};

/* Write one preference group: to storage and to the store, as a new object.

   `name` is 'view' or 'studio'; the value goes through the same validation as
   a stored one, so a caller cannot put a field in the store that a reload
   would not bring back. Answers false when the browser refused to keep it,
   for the same reason $saveTheme does: the setting holds until the tab is
   reloaded either way, and the dialog says so rather than leaving the
   operator to find out tomorrow. */
Vue.prototype.$savePrefs = function (name, value) {
  if (!PREFS[name]) return false;
  var clean = validatePrefs(name, value);
  var box = browserStorage();
  var kept = false;
  if (box) {
    try {
      box.setItem(PREFS_PREFIX + name, JSON.stringify(clean));
      kept = true;
    } catch (err) {
      kept = false;
    }
  }
  store.state[name] = clean;
  return kept;
};

/* Router. Every screen is a named route and the address bar always names one:
   the default is a redirect rather than a component on '/', so after it the
   address says which screen is open, and a typo in the address lands on the
   studio rather than on a blank page. */
const router = new VueRouter({
  mode: 'hash',
  routes: [
    { path: '/',        redirect: '/studio' },
    { path: '/studio',  name: 'studio', component: screen('Studio') },
    { path: '/voices',  name: 'voices', component: screen('Voices') },
    { path: '/models',  name: 'models', component: screen('Models') },
    { path: '*',        redirect: '/studio' },
  ],
});

/* Every programmatic navigation goes through here.

   vue-router 3 rejects the promise it returns when a navigation is redirected,
   cancelled or already where it was asked to go. All three are ordinary, and
   none of them is an error worth an "Uncaught (in promise)" in the console. */
const goto = function (target) {
  var leaving = router.push(target);
  if (leaving && leaving.catch) leaving.catch(function () {});
};
Vue.prototype.$goto = goto;

/* What the browser tab says. One name and the screen you are on, so a window
   with three tabs open on this UI can be told apart without clicking through
   them. Set from the route rather than by each screen: a screen that forgot
   would leave the previous one's name in the tab, which is worse than a name
   that never changes. */
const TAB_TITLES = {
  studio: 'Studio',
  voices: 'Voices',
  models: 'Models',
};

router.afterEach(function (to) {
  var name = TAB_TITLES[to.name];
  document.title = name ? 'TTS - ' + name : 'TTS';
});

/* App root. Mounted at once - there is no session to check first. */
const App = {
  template:
    '<div>' +
    '<tts-header></tts-header>' +
    '<tts-toaster></tts-toaster>' +
    '<tts-settings></tts-settings>' +
    '<router-view :key="$route.path" />' +
    '</div>',
};

new Vue({ router, store, render: function (h) { return h(App); } }).$mount('#app');
