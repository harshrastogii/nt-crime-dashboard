// Count KPI figures up (or down) to their new value whenever the filters
// change. Only the numbers inside the existing text node are rewritten, so
// React keeps ownership of the element and later updates still land.
(function () {
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NUM = /\d[\d,]*(?:\.\d+)?/g;

  function nums(s) { return (s.match(NUM) || []).map(function (n) { return parseFloat(n.replace(/,/g, "")); }); }

  function animate(node, from) {
    var target = node.nodeValue;
    var to = nums(target);
    if (!to.length || reduce) return;
    var start = nums(from || "");
    if (start.length !== to.length) start = to.map(function () { return 0; });
    var t0 = performance.now(), dur = 700;
    node._target = target;
    function frame(now) {
      if (node._target !== target) return;          // a newer value took over
      var p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3), i = 0;
      var text = p < 1 ? target.replace(NUM, function (m) {
        var v = start[i] + (to[i] - start[i]) * e; i++;
        var dp = (m.split(".")[1] || "").length;
        return v.toLocaleString("en-AU", { minimumFractionDigits: dp, maximumFractionDigits: dp });
      }) : target;
      node._written = text;
      node.nodeValue = text;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function isKpi(node) { var p = node.parentNode; return p && p.classList && p.classList.contains("kpi-value"); }

  new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      if (m.type === "characterData" && isKpi(m.target)) {
        if (m.target.nodeValue === m.target._written) return;   // our own frame
        animate(m.target, m.oldValue);
      } else if (m.type === "childList") {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType === 3 && isKpi(n)) animate(n, "");
          else if (n.querySelectorAll) n.querySelectorAll(".kpi-value").forEach(function (el) {
            if (el.firstChild && el.firstChild.nodeType === 3) animate(el.firstChild, "");
          });
        });
      }
    });
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true, characterDataOldValue: true });
})();
