import gsap from "gsap";

const STORIES = [
  {
    title: "Studio announces fall anime slate",
    meta: "ANN · English · 2m read",
    body: "Production committees confirmed a stacked fall season. Trailers, key visuals, and cast notes land in your list as they publish — full story bodies when the feed carries them.",
  },
  {
    title: "Open models climb the leaderboard",
    meta: "Verge · English · 3m read",
    body: "Fresh evals reshuffle the open-weight board. Summarize the thread in-app, or press t and listen while you keep moving through headlines.",
  },
  {
    title: "MCU phase rumors, carefully filtered",
    meta: "CBR · English · 2m read",
    body: "Marvel category feeds stay on-topic — tag feeds plus keyword filters so Batman does not sneak into your Avengers list.",
  },
  {
    title: "Match report: late equalizer",
    meta: "ESPN · English · 1m read",
    body: "Sports wire updates in the same three-pane layout. Bookmark the finish, open the source in a browser, or save offline for the commute.",
  },
];

export function startTuiMock(): void {
  const root = document.querySelector<HTMLElement>("[data-tui]");
  if (!root) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rows = Array.from(root.querySelectorAll<HTMLElement>("[data-row]"));
  const title = root.querySelector<HTMLElement>("#tui-reader-title");
  const meta = root.querySelector<HTMLElement>("#tui-reader-meta");
  const body = root.querySelector<HTMLElement>("#tui-reader-body p");

  if (!rows.length || !title || !meta || !body) return;

  const apply = (index: number) => {
    const story = STORIES[index % STORIES.length];
    rows.forEach((row, i) => row.classList.toggle("is-hi", i === index % rows.length));
    title.textContent = story.title;
    meta.textContent = story.meta;
    body.textContent = story.body;
  };

  apply(0);
  if (reduced) return;

  let idx = 0;
  const cycle = () => {
    idx = (idx + 1) % Math.min(rows.length, STORIES.length);
    gsap
      .timeline()
      .to([title, meta, body], {
        opacity: 0,
        y: 6,
        duration: 0.28,
        ease: "power2.in",
        stagger: 0.03,
      })
      .add(() => apply(idx))
      .fromTo(
        [title, meta, body],
        { opacity: 0, y: -6 },
        { opacity: 1, y: 0, duration: 0.4, ease: "power3.out", stagger: 0.04 }
      );
  };

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          if (!(root as HTMLElement & { _tuiTimer?: number })._tuiTimer) {
            (root as HTMLElement & { _tuiTimer?: number })._tuiTimer = window.setInterval(
              cycle,
              3200
            ) as unknown as number;
          }
        } else {
          const t = (root as HTMLElement & { _tuiTimer?: number })._tuiTimer;
          if (t) {
            window.clearInterval(t);
            (root as HTMLElement & { _tuiTimer?: number })._tuiTimer = undefined;
          }
        }
      });
    },
    { threshold: 0.35 }
  );
  observer.observe(root);
}
