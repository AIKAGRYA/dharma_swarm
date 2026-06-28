/* The Seam — THE GRAFT engine. Vanilla, hermetic (no libs/network).
   (1) the empty-center constellation (illustrative — NOT the live roster);
   (2) the Seam Index bands reveal. Honors prefers-reduced-motion. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var CLUSTERS = ["#46a26f", "#7bb5d6", "#caa14a", "#cf8a5b", "#9b8fd1", "#d6708f"];

  var canvas = document.getElementById("field");
  if (canvas && canvas.getContext) {
    var ctx = canvas.getContext("2d");
    var W = 0, H = 0, cx = 0, cy = 0, voidR = 0, maxR = 0, dpr = 1, nodes = [], edges = [], t0 = null, raf = null;
    function rand(a, b) { return a + Math.random() * (b - a); }

    function build() {
      var rect = canvas.parentElement.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = rect.width; H = rect.height;
      canvas.width = Math.floor(W * dpr); canvas.height = Math.floor(H * dpr);
      canvas.style.width = W + "px"; canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cx = W / 2; cy = H / 2;
      var m = Math.min(W, H); voidR = m * 0.17; maxR = m * 0.47;
      var N = Math.max(46, Math.min(96, Math.round(W / 14)));
      nodes = [];
      for (var i = 0; i < N; i++) {
        var cl = i % 6, sector = (cl / 6) * Math.PI * 2;
        nodes.push({
          ang: sector + rand(-0.55, 0.55), r: rand(voidR * 1.18, maxR), c: CLUSTERS[cl],
          size: rand(1.3, 3.2), phase: rand(0, Math.PI * 2), amp: rand(2, 7), spd: rand(0.18, 0.45)
        });
      }
      edges = [];
      var pos = nodes.map(function (n) { return { x: cx + Math.cos(n.ang) * n.r, y: cy + Math.sin(n.ang) * n.r }; });
      var thr = maxR * 0.34, cap = N * 2;
      for (var a = 0; a < N && edges.length < cap; a++)
        for (var b = a + 1; b < N; b++) {
          var dx = pos[a].x - pos[b].x, dy = pos[a].y - pos[b].y;
          if (dx * dx + dy * dy < thr * thr) { edges.push([a, b]); if (edges.length >= cap) break; }
        }
    }
    function xyOf(n, t) { var r = n.r + Math.sin(t * n.spd + n.phase) * n.amp; return { x: cx + Math.cos(n.ang) * r, y: cy + Math.sin(n.ang) * r }; }

    function frame(ts) {
      if (t0 === null) t0 = ts;
      var t = (ts - t0) / 1000;
      ctx.clearRect(0, 0, W, H);
      var pulse = reduce ? 0 : (Math.sin(t * 0.6) * 0.5 + 0.5);
      var g = ctx.createRadialGradient(cx, cy, voidR * 0.2, cx, cy, voidR * (1.5 + pulse * 0.15));
      g.addColorStop(0, "rgba(70,162,111,0)"); g.addColorStop(0.82, "rgba(70,162,111,0.05)"); g.addColorStop(1, "rgba(70,162,111,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, voidR * 1.65, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "rgba(120,180,150," + (0.10 + pulse * 0.10) + ")"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(cx, cy, voidR, 0, Math.PI * 2); ctx.stroke();
      var P = nodes.map(function (n) { return xyOf(n, t); });
      ctx.lineWidth = 1;
      for (var e = 0; e < edges.length; e++) {
        var pa = P[edges[e][0]], pb = P[edges[e][1]];
        ctx.strokeStyle = "rgba(150,190,170,0.07)";
        ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
      }
      for (var i = 0; i < nodes.length; i++) {
        var p = P[i], n = nodes[i];
        ctx.globalAlpha = 0.92; ctx.fillStyle = n.c;
        ctx.beginPath(); ctx.arc(p.x, p.y, n.size, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 0.14; ctx.beginPath(); ctx.arc(p.x, p.y, n.size * 2.6, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 1;
      }
      if (!reduce) raf = requestAnimationFrame(frame);
    }
    function start() { if (raf) cancelAnimationFrame(raf); t0 = null; if (reduce) frame(0); else raf = requestAnimationFrame(frame); }
    var rz; window.addEventListener("resize", function () { clearTimeout(rz); rz = setTimeout(function () { build(); start(); }, 150); });
    build(); start();
  }

  function fill() { document.querySelectorAll(".bar[data-w]").forEach(function (bar) { var i = bar.querySelector("i"); if (i) i.style.width = bar.getAttribute("data-w") + "%"; }); }
  var panel = document.querySelector(".index-panel");
  if (panel && "IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (en) { en.forEach(function (x) { if (x.isIntersecting) { fill(); io.disconnect(); } }); }, { threshold: 0.35 });
    io.observe(panel);
  } else { fill(); }
})();
