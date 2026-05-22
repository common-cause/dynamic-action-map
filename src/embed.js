/**
 * Common Cause grassroots action map embed.
 *
 * Drop these two lines into a WordPress Custom HTML block:
 *   <div id="cc-grassroots-map-embed"></div>
 *   <script src="https://common-cause.github.io/dynamic-action-map/src/embed.js"></script>
 *
 * The script finds the mount div, loads data/states.json relative to itself,
 * and renders a clickable US map. Per-state action content is sourced from
 * a Google Sheet via a daily Civis sync (see scripts/sync_actions.py).
 */
(function () {
  "use strict";

  // Hardcoded fallback so the widget renders even if states.json fetch fails.
  // Kept in sync with the canonical default row in the Google Sheet.
  var FALLBACK_DEFAULT_ACTION = {
    url: "https://www.mobilize.us/commoncause/event/758610/",
    headline: "Phone Bank with Common Cause!",
    description: "Join Common Cause for an important phone bank as we mobilize voters to take action against dangerous legislation in state houses and Congress. We will focus on the most urgent campaigns that need our help. No prior experience is necessary—our team will provide full training at the start of each shift!"
  };

  // Resolve base URL so we can fetch states.json + embed.css from the right place.
  var scriptEl = document.currentScript;
  if (!scriptEl) {
    var scripts = document.querySelectorAll("script[src]");
    for (var i = 0; i < scripts.length; i++) {
      if (scripts[i].src && scripts[i].src.indexOf("embed.js") !== -1) {
        scriptEl = scripts[i];
        break;
      }
    }
  }
  var baseUrl = scriptEl
    ? scriptEl.src.replace(/\/src\/embed\.js([?#].*)?$/, "/")
    : "./";

  // Inject stylesheet so the WordPress snippet stays two lines.
  var link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = baseUrl + "src/embed.css";
  document.head.appendChild(link);

  var mount = document.getElementById("cc-grassroots-map-embed");
  if (!mount) {
    console.warn("[cc-grassroots-map] No element with id='cc-grassroots-map-embed' found.");
    return;
  }

  // Fetch states data, fall back to defaults on failure.
  fetch(baseUrl + "data/states.json", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      initMap(data.default || FALLBACK_DEFAULT_ACTION, data.states || {});
    })
    .catch(function (err) {
      console.warn("[cc-grassroots-map] states.json fetch failed, using fallback default:", err);
      initMap(FALLBACK_DEFAULT_ACTION, {});
    });

  function initMap(DEFAULT_ACTION, sheetStates) {
    var stateNames = [
      "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware","Florida","Georgia",
      "Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts",
      "Michigan","Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey","New Mexico",
      "New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina",
      "South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming"
    ];

    // Build full STATE_DATA: sheet rows for states that have one, default for the rest.
    var STATE_DATA = {};
    for (var s = 0; s < stateNames.length; s++) {
      STATE_DATA[stateNames[s]] = sheetStates[stateNames[s]] || DEFAULT_ACTION;
    }
    STATE_DATA["District of Columbia"] = DEFAULT_ACTION;
    STATE_DATA["Other"] = DEFAULT_ACTION;

    var STATE_TO_ABBR = {
      "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO","Connecticut":"CT",
      "Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
      "Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI",
      "Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH",
      "New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
      "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX",
      "Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"
    };

    var ALL_STATES_ALPHA = stateNames.concat(["District of Columbia","Other"]);

    function addSourceParam(url) {
      try {
        var u = new URL(url);
        u.searchParams.set("source", "grassroots_map");
        return u.toString();
      } catch (e) { return url; }
    }

    function escapeHtml(s) {
      return String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function bodyToHtml(md) {
      var raw = String(md || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
      var filteredLines = raw.split("\n").filter(function (line) {
        return !/^\s*\[[^\]]+\]\(https?:\/\/[^\s)]+\)\s*$/.test(line);
      });
      var filtered = filteredLines.join("\n");
      var safe = escapeHtml(filtered);
      var noMdLinks = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, "$1");
      var lines = noMdLinks.split(/\r?\n/);
      var html = "";
      var inList = false;
      var closeList = function () { if (inList) { html += "</ul>"; inList = false; } };
      for (var j = 0; j < lines.length; j++) {
        var line = lines[j].trim();
        if (!line) { closeList(); html += "<p></p>"; continue; }
        if (line.indexOf("- ") === 0) {
          if (!inList) { closeList(); html += "<ul>"; inList = true; }
          html += "<li>" + line.slice(2) + "</li>";
        } else {
          closeList();
          html += "<p>" + line + "</p>";
        }
      }
      closeList();
      return html;
    }

    function getEntry(state) {
      var entry = STATE_DATA[state];
      if (!entry || !entry.url || !entry.headline || !entry.description) return DEFAULT_ACTION;
      try { new URL(entry.url); } catch (e) { return DEFAULT_ACTION; }
      return entry;
    }

    function stateToRegionCode(state) {
      if (state === "Other" || state === "District of Columbia") return null;
      var abbr = STATE_TO_ABBR[state];
      return abbr ? ("US-" + abbr) : null;
    }

    mount.innerHTML = ''
      + '<div class="ccgm-bleed">'
      + '  <div class="ccgm-wrap">'
      + '    <div class="ccgm-card">'
      + '      <div class="ccgm-header">'
      + '        <div class="ccgm-kicker">Take action</div>'
      + '        <h2 class="ccgm-title">Choose your state to get plugged into a grassroots action</h2>'
      + '      </div>'
      + '      <div class="ccgm-controls">'
      + '        <label class="ccgm-label" for="ccgm-stateSelect">Select your state</label>'
      + '        <select class="ccgm-select" id="ccgm-stateSelect">'
      + '          <option value="" selected disabled>Choose a state…</option>'
      + '        </select>'
      + '      </div>'
      + '      <div class="ccgm-mapWrap">'
      + '        <div class="ccgm-mapTopbar">'
      + '          <strong>Map</strong>'
      + '          <div class="ccgm-hoverName" id="ccgm-hoverName" aria-live="polite"></div>'
      + '        </div>'
      + '        <div id="ccgm-map" class="ccgm-map" aria-label="Interactive map of the United States"></div>'
      + '      </div>'
      + '    </div>'
      + '  </div>'
      + '</div>'
      + '<div class="ccgm-modalBackdrop" id="ccgm-modalBackdrop" aria-hidden="true">'
      + '  <div class="ccgm-modal" role="dialog" aria-modal="true" aria-labelledby="ccgm-modalTitle">'
      + '    <div class="ccgm-modalTexture"></div>'
      + '    <button type="button" class="ccgm-close" id="ccgm-closeBtn" aria-label="Close dialog">×</button>'
      + '    <div class="ccgm-modalInner">'
      + '      <div class="ccgm-modalKicker" id="ccgm-modalKicker">State</div>'
      + '      <h3 class="ccgm-modalHeadline" id="ccgm-modalTitle">Headline</h3>'
      + '      <div class="ccgm-modalBody" id="ccgm-modalBody"></div>'
      + '    </div>'
      + '    <div class="ccgm-modalFooter">'
      + '      <a class="ccgm-cta" id="ccgm-cta" href="#" target="_blank" rel="noopener">GET STARTED</a>'
      + '      <div class="ccgm-disclaimer">Opens in a new tab.</div>'
      + '    </div>'
      + '  </div>'
      + '</div>';

    var selectEl = mount.querySelector("#ccgm-stateSelect");
    var mapEl = mount.querySelector("#ccgm-map");
    var hoverNameEl = mount.querySelector("#ccgm-hoverName");
    var backdrop = mount.querySelector("#ccgm-modalBackdrop");
    var closeBtn = mount.querySelector("#ccgm-closeBtn");
    var modalTitle = mount.querySelector("#ccgm-modalTitle");
    var modalKicker = mount.querySelector("#ccgm-modalKicker");
    var modalBody = mount.querySelector("#ccgm-modalBody");
    var cta = mount.querySelector("#ccgm-cta");

    for (var k = 0; k < ALL_STATES_ALPHA.length; k++) {
      var opt = document.createElement("option");
      opt.value = ALL_STATES_ALPHA[k];
      opt.textContent = ALL_STATES_ALPHA[k];
      selectEl.appendChild(opt);
    }

    var currentState = null;

    function openModal(state) {
      var entry = getEntry(state);
      currentState = state;
      modalKicker.textContent = state;
      modalTitle.textContent = entry.headline || DEFAULT_ACTION.headline;
      modalBody.innerHTML = bodyToHtml(entry.description || DEFAULT_ACTION.description);
      var href = addSourceParam(entry.url || DEFAULT_ACTION.url);
      cta.href = href;
      backdrop.dataset.open = "true";
      backdrop.setAttribute("aria-hidden", "false");
      closeBtn.focus();
      cta.onclick = function () {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event: "grassroots_map_get_started", state: state, url: href });
        return true;
      };
    }

    function closeModal() {
      backdrop.dataset.open = "false";
      backdrop.setAttribute("aria-hidden", "true");
    }

    closeBtn.addEventListener("click", closeModal);
    backdrop.addEventListener("click", function (e) { if (e.target === backdrop) closeModal(); });
    document.addEventListener("keydown", function (e) {
      if (backdrop.dataset.open === "true" && e.key === "Escape") closeModal();
    });

    var svgIndex = new Map();
    var selectedState = null;

    function applyBasePathStyle(p) {
      p.style.stroke = "#FFFFFF";
      p.style.strokeWidth = "3.5";
      p.style.strokeLinejoin = "round";
      p.style.cursor = "pointer";
      p.style.pointerEvents = "all";
    }

    function clearSelectedClass() {
      var svg = mapEl.querySelector("svg");
      if (!svg) return;
      svg.querySelectorAll(".ccgm-selected").forEach(function (el) { el.classList.remove("ccgm-selected"); });
    }

    function applySelected(state) {
      selectedState = state;
      clearSelectedClass();
      if (selectedState && svgIndex.has(selectedState)) {
        svgIndex.get(selectedState).classList.add("ccgm-selected");
      }
    }

    function indexSvgRegions() {
      svgIndex.clear();
      var svg = mapEl.querySelector("svg");
      if (!svg) return;
      var paths = Array.from(svg.querySelectorAll("path"));
      for (var p = 0; p < paths.length; p++) {
        var path = paths[p];
        applyBasePathStyle(path);
        var label = (path.getAttribute("aria-label") || "").trim();
        if (!label) continue;
        var match = null;
        for (var n = 0; n < stateNames.length; n++) {
          if (label.indexOf(stateNames[n]) === 0) { match = stateNames[n]; break; }
        }
        if (!match || svgIndex.has(match)) continue;
        path.classList.add("ccgm-state");
        svgIndex.set(match, path);
        (function (m, el) {
          el.addEventListener("mouseenter", function () { hoverNameEl.textContent = m; });
          el.addEventListener("mouseleave", function () { hoverNameEl.textContent = ""; });
        })(match, path);
      }
      if (selectedState) applySelected(selectedState);
    }

    var obs = new MutationObserver(function () { setTimeout(indexSvgRegions, 0); });
    obs.observe(mapEl, { childList: true, subtree: true });

    function setSelection(state, opts) {
      opts = opts || {};
      currentState = state;
      if (selectEl.value !== state) selectEl.value = state;
      applySelected(state);
      if (opts.open) openModal(state);
    }

    selectEl.addEventListener("change", function (e) {
      var state = e.target.value;
      if (!state) return;
      setSelection(state, { open: true });
    });

    function loadGoogleCharts(cb) {
      if (window.google && window.google.charts && window.google.visualization) { cb(); return; }
      var s = document.createElement("script");
      s.src = "https://www.gstatic.com/charts/loader.js";
      s.async = true;
      s.onload = cb;
      s.onerror = function () {
        mapEl.innerHTML = '<div style="padding:14px;color:rgba(27,31,35,0.75)">Map failed to load. You can still use the dropdown.</div>';
      };
      document.head.appendChild(s);
    }

    function drawMap() {
      google.charts.load("current", { packages: ["geochart"] });
      google.charts.setOnLoadCallback(function () {
        var dt = new google.visualization.DataTable();
        dt.addColumn("string", "State");
        dt.addColumn("number", "Value");
        dt.addColumn({ type: "string", role: "tooltip" });

        var rows = [];
        for (var i = 0; i < ALL_STATES_ALPHA.length; i++) {
          var state = ALL_STATES_ALPHA[i];
          var region = stateToRegionCode(state);
          if (!region) continue;
          rows.push([region, 1, state]);
        }
        dt.addRows(rows);

        var options = {
          region: "US",
          resolution: "provinces",
          legend: "none",
          backgroundColor: "transparent",
          datalessRegionColor: "#FFFFFF",
          colorAxis: { colors: ["#D2BCD8", "#804191"] },
          tooltip: { trigger: "none" },
          keepAspectRatio: true
        };

        var chart = new google.visualization.GeoChart(mapEl);

        google.visualization.events.addListener(chart, "regionClick", function (e) {
          var abbr = e.region.replace("US-", "");
          var state = null;
          for (var key in STATE_TO_ABBR) {
            if (STATE_TO_ABBR[key] === abbr) { state = key; break; }
          }
          if (state) setSelection(state, { open: true });
        });

        chart.draw(dt, options);
        setTimeout(indexSvgRegions, 0);

        var t = null;
        window.addEventListener("resize", function () {
          clearTimeout(t);
          t = setTimeout(function () {
            chart.draw(dt, options);
            setTimeout(indexSvgRegions, 0);
            if (currentState) applySelected(currentState);
          }, 150);
        });
      });
    }

    loadGoogleCharts(drawMap);
  }
})();
