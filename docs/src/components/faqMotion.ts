import gsap from "gsap";

export function initFaqAccordion(): void {
  const list = document.querySelector<HTMLElement>("[data-faq-list]");
  if (!list) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const items = Array.from(list.querySelectorAll<HTMLElement>(".faq-item"));

  const closeItem = (item: HTMLElement, animate: boolean) => {
    const btn = item.querySelector<HTMLButtonElement>(".faq-trigger");
    const panel = item.querySelector<HTMLElement>(".faq-panel");
    const icon = item.querySelector<HTMLElement>(".faq-icon");
    if (!btn || !panel) return;

    btn.setAttribute("aria-expanded", "false");
    item.classList.remove("is-open");
    if (icon) icon.textContent = "+";

    if (!animate || reduced) {
      gsap.killTweensOf(panel);
      panel.style.height = "0px";
      panel.hidden = true;
      return;
    }

    gsap.killTweensOf(panel);
    gsap.to(panel, {
      height: 0,
      duration: 0.4,
      ease: "power3.inOut",
      onComplete: () => {
        panel.hidden = true;
      },
    });
  };

  const openItem = (item: HTMLElement, animate: boolean) => {
    const btn = item.querySelector<HTMLButtonElement>(".faq-trigger");
    const panel = item.querySelector<HTMLElement>(".faq-panel");
    const inner = item.querySelector<HTMLElement>(".faq-panel-inner");
    const icon = item.querySelector<HTMLElement>(".faq-icon");
    if (!btn || !panel || !inner) return;

    // Close others (accordion)
    items.forEach((other) => {
      if (other !== item && other.classList.contains("is-open")) {
        closeItem(other, animate);
      }
    });

    btn.setAttribute("aria-expanded", "true");
    item.classList.add("is-open");
    if (icon) icon.textContent = "+"; // rotated to X via CSS
    panel.hidden = false;

    if (!animate || reduced) {
      gsap.killTweensOf(panel);
      panel.style.height = "auto";
      return;
    }

    const target = inner.scrollHeight;
    gsap.killTweensOf(panel);
    gsap.fromTo(
      panel,
      { height: 0 },
      {
        height: target,
        duration: 0.48,
        ease: "power3.out",
        onComplete: () => {
          panel.style.height = "auto";
        },
      }
    );
    gsap.fromTo(
      inner,
      { opacity: 0, y: -10 },
      { opacity: 1, y: 0, duration: 0.4, delay: 0.06, ease: "power2.out" }
    );
  };

  items.forEach((item) => {
    const btn = item.querySelector<HTMLButtonElement>(".faq-trigger");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const isOpen = item.classList.contains("is-open");
      if (isOpen) closeItem(item, true);
      else openItem(item, true);
    });
  });
}
