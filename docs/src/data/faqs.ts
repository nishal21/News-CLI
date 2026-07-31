export type FaqItem = {
  q: string;
  /** Plain answer for schema / llms (must stay accurate). */
  a: string;
  /** Optional labeled links shown as a clean list. */
  links?: { label: string; href: string }[];
};

export const faqs: FaqItem[] = [
  {
    q: "What is World News CLI?",
    a: "World News CLI (PyPI: worldnews-cli) is a full-screen terminal news reader built with Textual. You get a feeds rail, headline list, and article pane in one window, plus speak aloud and optional AI summarize.",
  },
  {
    q: "How do I install it?",
    a: "Install Python 3.9+, then run pip install worldnews-cli and worldnews. Prefer an isolated tool install? Use pipx install worldnews-cli or uv tool install worldnews-cli.",
  },
  {
    q: "Python or pip is not recognized on Windows. What should I run?",
    a: "Use the Windows Python launcher: py -m pip install worldnews-cli, then py -m worldnews. That works when python and pip are missing from PATH.",
  },
  {
    q: "worldnews works nowhere after install. Now what?",
    a: "Call the module instead: python -m worldnews or py -m worldnews. Your Scripts folder is likely off PATH; the module form still finds the package.",
  },
  {
    q: "Do I need an API key?",
    a: "No for reading. AI summarize can use a free OpenCode Zen path with no key. Other AI and voice providers are optional under Settings.",
  },
  {
    q: "Can I run World News CLI on a phone?",
    a: "Yes on Android via Termux (install Python and deps, then pip install worldnews-cli and python -m worldnews). It is still a terminal UI, not a native app. On narrow screens the layout becomes list-or-reader. iOS has no official app; a-Shell/iSH or SSH to another machine are the usual workarounds.",
  },
  {
    q: "What are the mobile limitations?",
    a: "No App Store build. Touch is secondary to keys. Complex scripts may not render well in Termux without a good font; safe mode hides them and you can press o for the browser or t to speak. First install needs native libraries and can be slow on older devices.",
  },
  {
    q: "Where is the project site and who made it?",
    a: "Product site: https://nishal21.github.io/News-CLI/. Source: https://github.com/nishal21/News-CLI. Author site: https://nishal.dev.",
    links: [
      { label: "Product site", href: "https://nishal21.github.io/News-CLI/" },
      { label: "Source on GitHub", href: "https://github.com/nishal21/News-CLI" },
      { label: "Author site", href: "https://nishal.dev" },
    ],
  },
];

/** Escape HTML, then wrap http(s) URLs in anchors. */
export function linkifyAnswer(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
  return escaped.replace(
    /(https?:\/\/[^\s<]+[^.,)\s])/g,
    '<a href="$1" rel="noopener noreferrer" target="_blank">$1</a>'
  );
}
