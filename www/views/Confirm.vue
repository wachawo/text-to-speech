<template>
  <div class="modal fade" ref="modalEl" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog">
      <div class="modal-content">

        <div class="modal-header bg-blue py-1 px-3">
          <h5 class="modal-title fw-bold mb-0">{{ title }}</h5>
          <button type="button" class="btn btn-primary btn-sm ms-auto"
                  data-bs-dismiss="modal" title="Close" aria-label="Close">
            <i class="fa fa-times"></i>
          </button>
        </div>

        <!-- `pre-line`, so a question with two paragraphs is read as two. The
             body is plain text bound as text - it can never be markup - and
             without this a caller's blank line collapses into a space and the
             warning runs into the question it qualifies. -->
        <div class="modal-body py-2" style="white-space:pre-line">{{ body }}</div>

        <div class="modal-footer p-1 d-flex justify-content-end gap-1">
          <button type="button" ref="cancelEl"
                  class="btn btn-sm btn-secondary fw-bold" style="min-width:100px"
                  data-bs-dismiss="modal">CANCEL</button>
          <button type="button" class="btn btn-sm fw-bold" style="min-width:100px"
                  :class="danger ? 'btn-danger' : 'btn-primary'"
                  @click="confirm">{{ label }}</button>
        </div>

      </div>
    </div>
  </div>
</template>

<script>
/* The one question this application is allowed to ask before it destroys
   something.

   The browser's own confirm dialog is what this replaces. Two reasons beyond
   the look of it: it is drawn by the browser, so it says the page's origin
   rather than what is about to be deleted and cannot show the item's name at
   all; and it blocks the whole event loop, so anything polling while it is
   open piles up behind it.

   Used as:

     <tts-confirm ref="confirm"></tts-confirm>

     this.$refs.confirm.ask({
       title: 'DELETE VOICE',
       body: 'Delete the voice sample "maria"? Takes made with it stay.',
       label: 'DELETE',
       danger: true,
     }).then(function (ok) {
       if (!ok) return;
       ...
     });

   `ask()` resolves true only when the confirming button was pressed. Every
   other way out of the dialog - the cross, Cancel, Esc, a click on the
   backdrop, the route changing under it - resolves false. Never nothing: a
   promise left pending is a delete that silently does nothing, on a screen
   whose buttons stay disabled waiting for an answer that is not coming.

   Needs bootstrap.bundle.min.js, which index.html loads before app.js: the
   dialog is a Bootstrap Modal and without the bundle `ask()` answers false
   at once rather than opening nothing and waiting.
*/
module.exports = {
  data: function () {
    return {
      title:  'CONFIRM',
      body:   '',
      label:  'CONFIRM',
      danger: false,
    };
  },

  mounted: function () {
    // The Bootstrap handle is deliberately kept off `data`: Vue would make the
    // library object reactive and walk every field it owns.
    this.modalEl = this.$refs.modalEl;
    this.modal = (typeof bootstrap !== 'undefined' && bootstrap.Modal)
      ? new bootstrap.Modal(this.modalEl)
      : null;
    // Not reactive state either - these only carry one answer from the click
    // that produced it to the `hidden` event that reports it.
    this.settle = null;
    this.answer = false;
    this.shown = false;
    this.modalEl.addEventListener('hidden.bs.modal', this.handleHidden);
    this.modalEl.addEventListener('shown.bs.modal', this.handleShown);
  },

  /* A dialog left open when the route changes takes its backdrop with it -
     Bootstrap appends that to <body>, outside this component's subtree - and
     the next screen renders under a grey sheet it cannot dismiss, on a <body>
     still carrying `overflow: hidden`. */
  beforeDestroy: function () {
    if (this.modalEl) {
      this.modalEl.removeEventListener('hidden.bs.modal', this.handleHidden);
      this.modalEl.removeEventListener('shown.bs.modal', this.handleShown);
    }
    // Before dispose, or the `hidden` event that would have settled it never
    // arrives and the caller waits forever on a component that no longer
    // exists.
    this.finish(false);
    if (this.modal) {
      this.modal.dispose();
      this.modal = null;
    }
    this.modalEl = null;
  },

  methods: {
    ask: function (options) {
      var self = this;
      var opts = options || {};
      // A second ask() while one is open answers the first caller "no" rather
      // than leaving it behind a dialog it no longer owns.
      this.finish(false);
      this.title  = opts.title || 'CONFIRM';
      this.body   = opts.body  || '';
      this.label  = opts.label || 'CONFIRM';
      this.danger = !!opts.danger;
      this.answer = false;
      // No modal means no way to ask, and the safe answer to a question that
      // was never put is no.
      if (!this.modal) return Promise.resolve(false);
      return new Promise(function (resolve) {
        self.settle = resolve;
        self.modal.show();
      });
    },

    /* Recorded here, reported from `hidden`. Resolving on the click instead
       lets the caller open its own dialog while this one is still fading out,
       which leaves Bootstrap with two backdrops and only one of them
       removable.

       Ignored until `shown`: Bootstrap drops a hide() while the dialog is
       still fading in, and a yes recorded by a click it dropped would be
       reported by whatever closes the dialog next - Cancel included. */
    confirm: function () {
      if (this.modal && !this.shown) return;
      this.answer = true;
      if (this.modal) this.modal.hide();
      else this.finish(true);
    },

    handleHidden: function () {
      this.shown = false;
      this.finish(this.answer);
    },

    /* Focus lands on Cancel, not on the confirming button. Bootstrap focuses
       the dialog itself and leaves Enter doing nothing, which is safe but
       leaves the keyboard a tab away from an answer; starting on Cancel gives
       Enter a meaning, and the meaning it gets is the one that destroys
       nothing. */
    handleShown: function () {
      this.shown = true;
      if (this.$refs.cancelEl) this.$refs.cancelEl.focus();
    },

    /* Settle the outstanding promise exactly once. Every way out of the dialog
       ends here, and `settle` is cleared before it is called so a second path
       out - hide() followed by dispose(), say - cannot resolve it twice. */
    finish: function (value) {
      var settle = this.settle;
      this.settle = null;
      this.answer = false;
      if (settle) settle(!!value);
    },
  },
};
</script>
