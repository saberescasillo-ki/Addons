// A fake of @minecraft/server-ui: every form asks `ui.answer(form)` what to reply.
export const ui = { answer: () => ({ canceled: true, cancelationReason: "UserClosed" }), shown: [] };

class Form {
  constructor(kind) {
    this.kind = kind;
    this.controls = [];
    this.buttons = [];
  }
  title(t) { this._title = t; return this; }
  body(b) { this._body = b; return this; }
  button(text) { this.buttons.push(text); return this; }
  button1(text) { this.buttons[0] = text; return this; }
  button2(text) { this.buttons[1] = text; return this; }
  toggle(label, o) { this.controls.push({ type: "toggle", label, value: o?.defaultValue ?? false }); return this; }
  slider(label, min, max, o) { this.controls.push({ type: "slider", label, min, max, value: o?.defaultValue ?? min }); return this; }
  dropdown(label, items, o) { this.controls.push({ type: "dropdown", label, items, value: o?.defaultValueIndex ?? 0 }); return this; }
  textField(label, ph, o) { this.controls.push({ type: "text", label, value: o?.defaultValue ?? "" }); return this; }
  submitButton() { return this; }
  async show(player) {
    ui.shown.push({ player: player.name, title: this._title, buttons: this.buttons });
    return ui.answer(this, player);
  }
}
export class ActionFormData extends Form { constructor() { super("action"); } }
export class ModalFormData extends Form { constructor() { super("modal"); } }
export class MessageFormData extends Form { constructor() { super("message"); } }
