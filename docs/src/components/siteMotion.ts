import gsap from "gsap";

const CATS = [
  "GENERAL",
  "ANIME",
  "MARVEL",
  "DC",
  "HOLLYWOOD",
  "TECH",
  "AI",
  "SPORTS",
  "GAMING",
  "SCIENCE",
  "BUSINESS",
  "MY FEEDS",
];

export function mountAmbientTicker(host: HTMLElement): void {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const track = document.createElement("div");
  track.className = "ticker-track";
  track.setAttribute("aria-hidden", "true");
  const text = [...CATS, ...CATS].map((c) => `<span>${c}</span>`).join("");
  track.innerHTML = text;
  host.appendChild(track);

  if (reduced) return;

  gsap.to(track, {
    yPercent: -50,
    duration: 48,
    ease: "none",
    repeat: -1,
  });
}

/** Wire CSS class .reveal elements with GSAP ScrollTrigger-like IO */
export function mountScrollReveals(): void {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(".reveal"));
  if (!nodes.length) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) {
    nodes.forEach((n) => {
      n.style.opacity = "1";
      n.style.transform = "none";
    });
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target as HTMLElement;
        gsap.to(el, {
          opacity: 1,
          y: 0,
          duration: 0.85,
          ease: "power3.out",
          overwrite: true,
        });
        io.unobserve(el);
      });
    },
    { threshold: 0.18, rootMargin: "0px 0px -8% 0px" }
  );

  nodes.forEach((n) => io.observe(n));
}
