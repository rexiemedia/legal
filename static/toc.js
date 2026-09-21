(function () {
  var toc = document.querySelector(".toc");
  if (!toc) return;

  // Contents list is always open on wide screens, collapsed on phones.
  var wide = window.matchMedia("(min-width: 56rem)");
  function sync() { toc.open = wide.matches; }
  sync();
  wide.addEventListener("change", sync);

  // Highlight the section currently being read.
  if (!("IntersectionObserver" in window)) return;
  var links = {};
  toc.querySelectorAll('a[href^="#"]').forEach(function (a) { links[a.hash.slice(1)] = a; });
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting || !links[e.target.id]) return;
      Object.keys(links).forEach(function (k) { links[k].removeAttribute("aria-current"); });
      links[e.target.id].setAttribute("aria-current", "true");
    });
  }, { rootMargin: "0px 0px -70% 0px" });
  document.querySelectorAll(".doc h2[id]").forEach(function (h) { io.observe(h); });
})();