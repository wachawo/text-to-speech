<template>
  <div class="tts-toaster">
    <div v-for="t in $store.state.toasts" :key="t.id"
         class="tts-toast" :class="'tts-toast-' + t.level"
         @click="$store.dispatch('dismiss_toast', t.id)">
      <i class="fa me-2" :class="icon(t.level)"></i>
      <span class="tts-toast-msg">{{ t.message }}</span>
      <i class="fa fa-xmark ms-2 tts-toast-x"></i>
    </div>
  </div>
</template>

<script>
/* The stack of toasts in the top right corner, fed by the store: any screen
   pushes one with `this.$store.dispatch('push_toast', {level, message, ttl})`
   and a click dismisses it early. Levels are danger, warning, success and
   info; anything else is drawn as info. */
module.exports = {
  methods: {
    icon: function (level) {
      if (level === 'danger')  return 'fa-circle-exclamation';
      if (level === 'success') return 'fa-circle-check';
      if (level === 'warning') return 'fa-triangle-exclamation';
      return 'fa-circle-info';
    },
  },
};
</script>
