<template>
  <div class="tts-alerts" v-if="bars.length">
    <div v-for="bar in bars" :key="bar.kind"
         class="tts-alert" :class="'tts-alert-' + bar.kind" :role="bar.role">
      <i class="fa" :class="bar.icon" aria-hidden="true"></i>
      <span class="tts-alert-msg">{{ bar.text }}</span>
      <button type="button" class="btn-close" aria-label="Dismiss"
              @click="dismiss(bar.kind)"></button>
    </div>
  </div>
</template>

<script>
/* The four message bars every screen carries, above its content.

   Used everywhere as:

     <tts-alerts :error.sync="error" :warning.sync="warning"
                 :info.sync="info" :success.sync="success"></tts-alerts>

   Four strings on the screen's own `data`, one component, and no screen
   deciding for itself where a failure goes or what colour it is.

   The spinner strip a screen shows while `wait.length > 0` is not one of
   these: that is progress, and it belongs to the request rather than to the
   operator.
*/

/* The order, fixed here rather than by whichever string was set last. A bar
   that moves between renders is a bar the operator has to read again to find
   out which one it is, and the one they are most likely to skip is the one
   that says the write failed.

   The role is the same decision for a screen reader. `alert` interrupts
   whatever is being spoken; `status` waits its turn. An error and a warning
   are worth interrupting for - the operator is about to act on a screen that
   is not saying what they think it says - and a save that worked is not. */
var BARS = [
  { kind: 'error',   icon: 'fa-circle-exclamation',   role: 'alert'  },
  { kind: 'warning', icon: 'fa-triangle-exclamation', role: 'alert'  },
  { kind: 'info',    icon: 'fa-circle-info',          role: 'status' },
  { kind: 'success', icon: 'fa-circle-check',         role: 'status' },
];

module.exports = {
  props: {
    error:   { type: String, default: '' },
    warning: { type: String, default: '' },
    info:    { type: String, default: '' },
    success: { type: String, default: '' },
  },

  computed: {
    /* Only the bars with something to say, in BARS order.

       A screen holding four empty strings renders nothing at all - not four
       empty boxes, not one collapsed container - so the content below it sits
       in the same place whether or not the last write had anything to report.
       Anything that reserved space here would move every row down the moment a
       message arrived, which is exactly when the operator is looking at
       them. */
    bars: function () {
      var self = this;
      return BARS.filter(function (bar) {
        return !!self[bar.kind];
      }).map(function (bar) {
        return { kind: bar.kind, icon: bar.icon, role: bar.role, text: self[bar.kind] };
      });
    },
  },

  methods: {
    /* The dismiss control. `.sync` on the parent turns this into
       `error = ''`, so the string stays the screen's to own and this component
       never writes a prop of its own - which Vue would warn about and the next
       render of the parent would undo anyway. */
    dismiss: function (kind) {
      this.$emit('update:' + kind, '');
    },
  },
};
</script>
