/** Hero boot sequence — respects reduced motion */
export function bootHero(): void {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const brand = document.querySelector<HTMLElement>(".hero-brand-text");
  const answer = document.querySelector<HTMLElement>(".hero-answer");
  const line = document.querySelector<HTMLElement>(".hero-line");
  const ctas = document.querySelector<HTMLElement>(".hero-ctas");
  const meta = document.querySelector<HTMLElement>(".hero-meta");
  const cmd = document.querySelector<HTMLElement>(".hero-cmd");

  if (!brand) return;

  if (reduced) {
    [brand, answer, line, ctas, meta, cmd].forEach((el) => {
      if (el) {
        el.style.opacity = "1";
        el.style.transform = "none";
      }
    });
    return;
  }

  const full = brand.textContent?.trim() || "WORLD NEWS";
  brand.textContent = "";
  brand.style.opacity = "1";

  [answer, line, ctas, meta, cmd].forEach((el) => {
    if (!el) return;
    el.style.opacity = "0";
    el.style.transform = "translateY(12px)";
  });

  let i = 0;
  const tick = () => {
    i += 1;
    brand.textContent = full.slice(0, i);
    if (i < full.length) {
      window.setTimeout(tick, 48 + Math.random() * 40);
    } else {
      fadeIn(meta, 0);
      fadeIn(answer, 80);
      fadeIn(line, 180);
      fadeIn(ctas, 280);
      fadeIn(cmd, 380);
    }
  };
  window.setTimeout(tick, 280);
}

function fadeIn(el: HTMLElement | null, delay: number): void {
  if (!el) return;
  window.setTimeout(() => {
    el.style.transition = "opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1)";
    el.style.opacity = "1";
    el.style.transform = "translateY(0)";
  }, delay);
}
