// Shared health component for the player and bots.
export class Health {
  constructor(max) {
    this.max = max;
    this.hp = max;
    this.invulnerable = false;
    this.onDamage = null; // (amount, source) => void
    this.onDeath = null;  // (source) => void
  }
  get dead() { return this.hp <= 0; }
  get ratio() { return this.hp / this.max; }
  // Returns the damage actually dealt (0 if blocked).
  damage(amount, source) {
    if (this.dead || this.invulnerable || !(amount > 0)) return 0;
    const dealt = Math.min(this.hp, amount);
    this.hp -= dealt;
    this.onDamage?.(dealt, source);
    if (this.hp <= 0) this.onDeath?.(source);
    return dealt;
  }
  heal(amount) { if (!this.dead) this.hp = Math.min(this.max, this.hp + amount); }
  reset(max = this.max) { this.max = max; this.hp = max; this.invulnerable = false; }
}
