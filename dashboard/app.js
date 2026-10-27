(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const RED_SUITS = ["♥", "♦"];

  let data = null;
  let idx = 0;
  let followLive = true;
  let revealHands = false;
  let prevIdx = -1;
  let manualNav = false;
  let launching = false;

  // Reveal hands toggle
  const revealBtn = $("b-secrets");
  if (revealBtn) {
    revealBtn.onclick = () => {
      revealHands = !revealHands;
      revealBtn.setAttribute("aria-pressed", String(revealHands));
      revealBtn.textContent = revealHands ? "REVEAL (ON)" : "REVEAL";
      render();
    };
  }

  // Collapsible panels
  function setupCollapsible(btnId, panelId, storageKey) {
    const b = $(btnId), el = $(panelId);
    if (!b || !el) return;
    let visible = localStorage.getItem(storageKey) !== "0";
    const apply = () => { el.hidden = !visible; b.setAttribute("aria-pressed", String(visible)); };
    b.onclick = () => { visible = !visible; localStorage.setItem(storageKey, visible ? "1" : "0"); apply(); };
    apply();
  }
  setupCollapsible("b-signals", "pan-signals", "kems-signals");
  setupCollapsible("b-thoughts", "pan-thoughts", "kems-thoughts");

  // Timeline navigation & Auto-Play
  const tl = () => (data && data.timeline) || [];
  let autoPlay = false;
  let autoPlayTimer = null;

  function goToStep(i, manual = true) {
    const max = tl().length - 1;
    idx = Math.max(0, Math.min(max, i));
    if (manual) {
      setFollowLive(false);
      manualNav = true;
    }
    render();
  }

  function setFollowLive(v) {
    followLive = v;
    const btn = $("b-live");
    if (btn) btn.setAttribute("aria-pressed", String(followLive));
  }

  function toggleAutoPlay() {
    autoPlay = !autoPlay;
    const btn = $("b-auto");
    if (btn) {
      btn.textContent = autoPlay ? "❚❚ PAUSE" : "▶ PLAY";
      btn.setAttribute("aria-pressed", String(autoPlay));
      if (autoPlay) {
        btn.classList.add("btn-primary");
        btn.classList.remove("btn-secondary");
      } else {
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
      }
    }
    if (autoPlay) {
      setFollowLive(false);
      if (idx >= tl().length - 1) idx = 0;
      autoPlayLoop();
    } else {
      clearTimeout(autoPlayTimer);
    }
  }

  function autoPlayLoop() {
    clearTimeout(autoPlayTimer);
    if (!autoPlay) return;
    if (idx < tl().length - 1) {
      goToStep(idx + 1, false);
      const nextStep = tl()[idx];
      let delay = 1400;
      if (nextStep) {
        if (nextStep.type === "SWAP") delay = 2400;
        else if (nextStep.type === "SWEEP") delay = 2600;
        else if (nextStep.type === "CALL") delay = 2800;
      }
      autoPlayTimer = setTimeout(autoPlayLoop, delay);
    } else {
      autoPlayTimer = setTimeout(() => {
        if (!autoPlay) return;
        goToStep(0, false);
        autoPlayTimer = setTimeout(autoPlayLoop, 1500);
      }, 4000);
    }
  }

  if ($("b-auto")) $("b-auto").onclick = toggleAutoPlay;

  if ($("b-live")) {
    $("b-live").onclick = () => {
      if (autoPlay) toggleAutoPlay();
      setFollowLive(!followLive);
      if (followLive) goToStep(tl().length - 1, false);
    };
  }
  if ($("b-first")) $("b-first").onclick = () => { if (autoPlay) toggleAutoPlay(); goToStep(0); };
  if ($("b-prev")) $("b-prev").onclick = () => { if (autoPlay) toggleAutoPlay(); goToStep(idx - 1); };
  if ($("b-next")) $("b-next").onclick = () => { if (autoPlay) toggleAutoPlay(); goToStep(idx + 1); };
  if ($("scrub")) $("scrub").oninput = e => { if (autoPlay) toggleAutoPlay(); goToStep(+e.target.value); };

  function stepTurn(direction) {
    const t = tl();
    if (!t.length) return;
    const cur = t[idx].turn;
    let target = idx;
    while (target >= 0 && target < t.length && t[target].turn === cur) {
      target += direction;
    }
    goToStep(target);
  }
  const turnPrevBtn = $("b-turn-prev");
  if (turnPrevBtn) turnPrevBtn.onclick = () => { if (autoPlay) toggleAutoPlay(); stepTurn(-1); };
  const turnNextBtn = $("b-turn-next");
  if (turnNextBtn) turnNextBtn.onclick = () => { if (autoPlay) toggleAutoPlay(); stepTurn(1); };

  // Pixel Art SVGs for Suits (Hearts, Diamonds, Spades, Clubs)
  const SUIT_SVGS = {
    "♥": `<svg class="pixel-suit-center" viewBox="0 0 9 8" width="18" height="16" shape-rendering="crispEdges"><path fill="currentColor" d="M1 0h2v1H1zm5 0h2v1H6zM0 1h4v2H0zm5 0h4v2H5zM0 2h9v2H0zm1 2h7v1H1zm1 1h5v1H2zm1 1h3v1H3zm1 1h1v1H4z"/></svg>`,
    "♦": `<svg class="pixel-suit-center" viewBox="0 0 9 9" width="18" height="18" shape-rendering="crispEdges"><path fill="currentColor" d="M4 0h1v1H4zm-1 1h3v1H3zm-1 1h5v1H2zm-1 1h7v1H1zM0 4h9v1H0zm1 1h7v1H1zm1 1h5v1H2zm1 1h3v1H3zm1 1h1v1H4z"/></svg>`,
    "♠": `<svg class="pixel-suit-center" viewBox="0 0 9 9" width="18" height="18" shape-rendering="crispEdges"><path fill="currentColor" d="M4 0h1v1H4zm-1 1h3v1H3zm-1 1h5v1H2zm-1 1h7v1H1zM0 4h9v2H0zm0 2h3v1H0zm6 0h3v1H6zm-3 1h3v2H3z"/></svg>`,
    "♣": `<svg class="pixel-suit-center" viewBox="0 0 9 9" width="18" height="18" shape-rendering="crispEdges"><path fill="currentColor" d="M3 0h3v2H3zm-2 2h7v2H1zm-1 2h9v2H0zm1 2h7v1H1zm2 1h3v2H3z"/></svg>`
  };

  const cardHtml = (c, cls = "") => {
    if (!c) return `<div class="card-slot"></div>`;
    const suit = c.slice(-1);
    const mappedRank = c.slice(0, -1);
    const isRed = RED_SUITS.includes(suit);
    const colorCls = isRed ? "rouge" : "noire";
    const suitIcon = SUIT_SVGS[suit] || suit;

    return `
      <div class="card ${colorCls} ${cls}" data-c="${esc(c)}">
        <div class="card-val top">${esc(mappedRank)}</div>
        <div class="card-center">${suitIcon}</div>
        <div class="card-val bottom">${esc(mappedRank)}</div>
      </div>
    `;
  };

  function renderTable(step, skipCenter = false) {
    const players = data.players || [];
    const centerEl = $("center");
    if (centerEl) {
      centerEl.className = "center" + (step && step.phase === "EXCHANGE" ? " active" : "");
      if (!skipCenter) {
        const cards = (step && step.center) || (data && data.center) || [];
        let html = cards.map((c, i) => cardHtml(c, "", i)).join("");
        for (let i = cards.length; i < 4; i++) {
          html += `<div class="card-slot"></div>`;
        }
        centerEl.innerHTML = html;
      }
    }

    for (const p of players) {
      const el = $("seat-" + p.pid);
      if (!el) continue;
      const handsDict = (step && step.hands) || (data && data.secrets && data.secrets.hands) || {};
      const hand = handsDict[p.pid] || handsDict[String(p.pid)] || [];
      const hasSquare = revealHands && hand.length === 4 && new Set(hand.map(c => c.slice(0, -1))).size === 1;
      const cardCls = (revealHands ? "" : "flipped") + (hasSquare ? " square-card" : "");
      const cardsHtml = hand.length
        ? hand.map((c, i) => cardHtml(c, cardCls, i)).join("")
        : [0, 1, 2, 3].map(() => `<div class="card-slot"></div>`).join("");

      const team = p.team ?? 0;
      el.className = `seat p${p.pid + 1} t${team}` + (step && step.pid === p.pid ? " active" : "");

      const teamLabel = `TEAM ${team}`;
      const statusObj = (data.api_status || {})[p.pid];
      let apiStatusHtml = "";
      if (statusObj && statusObj.status && statusObj.status !== "idle") {
        let badgeClass = "badge";
        if (statusObj.status === "rate_limited") badgeClass += " badge-accent";
        apiStatusHtml = `<span class="${badgeClass}">${esc(statusObj.message)}</span>`;
      }

      const botTitle = (p.model || "Player").replace(/-/g, " ").toUpperCase();

      el.innerHTML = `
        <div class="seat-header">
          <div class="avatar t${team}">P${p.pid + 1}</div>
          <div class="seat-info">
            <div style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap;">
              <span class="nom">P${p.pid + 1}${hasSquare ? ' <span class="badge badge-accent">SQUARE</span>' : ""}</span>
              <span class="team-chip t${team}">${teamLabel}</span>
            </div>
            <span class="meta">${esc(botTitle)}</span>
            ${apiStatusHtml}
          </div>
        </div>
        <div class="hands">${cardsHtml}</div>
      `;
    }
  }

  function createSparkle(x, y) {
    const p = document.createElement("div");
    p.className = "pixel-poof";
    p.style.left = x + "px";
    p.style.top = y + "px";
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 400);
  }

  function highlightCard(el, cls, durationMs) {
    if (!el) return;
    el.classList.add(cls);
    setTimeout(() => el && el.classList.remove(cls), durationMs);
  }

  function animateFlight(card, fromRect, toRect, clsExtra, badgeLabel, durationMs = 950, offsetY = 0) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const tempDiv = document.createElement("div");
    const badgeHtml = badgeLabel ? `<div class="card-flight-badge ${clsExtra}">${badgeLabel}</div>` : "";
    tempDiv.innerHTML = `<div class="card-flying-wrap">${cardHtml(card, `card-flying ${clsExtra}`)}${badgeHtml}</div>`;
    const el = tempDiv.firstElementChild;
    if (!el) return;

    const cardEl = document.querySelector(".card");
    const halfW = (cardEl ? cardEl.offsetWidth : 58) / 2;
    const halfH = (cardEl ? cardEl.offsetHeight : 84) / 2;

    const startX = fromRect.left + fromRect.width / 2 - halfW;
    const startY = fromRect.top + fromRect.height / 2 - halfH;
    const endX = toRect.left + toRect.width / 2 - halfW;
    const endY = toRect.top + toRect.height / 2 - halfH;

    el.style.position = "fixed";
    el.style.zIndex = "1000";
    el.style.left = startX + "px";
    el.style.top = startY + "px";
    el.style.pointerEvents = "none";
    el.style.transition = `all ${durationMs / 1000}s cubic-bezier(0.25, 1, 0.4, 1)`;
    el.style.transform = "scale(1)";
    document.body.appendChild(el);

    createSparkle(startX + halfW, startY + halfH);

    requestAnimationFrame(() => {
      el.style.left = endX + "px";
      el.style.top = (endY + offsetY) + "px";
      el.style.transform = `scale(1.15) rotate(${clsExtra === "flying-take" ? "-6deg" : "6deg"})`;
    });

    setTimeout(() => {
      createSparkle(endX + halfW, endY + halfH);
      el.style.transition = "all 0.22s ease-out";
      el.style.transform = "scale(1) rotate(0deg)";
      setTimeout(() => el.remove(), 240);
    }, durationMs);
  }

  function animateSweep(newCards) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      renderTable({ phase: "SWEEP", center: newCards }, false);
      return;
    }
    const centerEl = $("center");
    if (!centerEl) return;

    const oldBanner = centerEl.querySelector(".center-banner");
    if (oldBanner) oldBanner.remove();
    const banner = document.createElement("div");
    banner.className = "center-banner";
    banner.textContent = "⇄ SWEEP: DEALING 4 NEW CARDS...";
    centerEl.appendChild(banner);
    setTimeout(() => banner.remove(), 2400);

    const currentCards = centerEl.querySelectorAll(".card, .card-slot");
    currentCards.forEach(c => c.classList.add("sweeping-out"));

    setTimeout(() => {
      let html = newCards.map((c, i) => cardHtml(c, `dealing-in delay-${i}`)).join("");
      for (let i = newCards.length; i < 4; i++) {
        html += `<div class="card-slot"></div>`;
      }
      centerEl.innerHTML = html;
      centerEl.appendChild(banner);

      const slots = centerEl.querySelectorAll(".card");
      slots.forEach((el, i) => {
        setTimeout(() => {
          const r = el.getBoundingClientRect();
          createSparkle(r.left + r.width / 2, r.top + r.height / 2);
        }, 100 + i * 140);
      });
    }, 480);
  }

  function triggerCallAnimation(step) {
    const table = $("table");
    const overlay = $("callout-overlay");
    if (!table || !overlay) return;

    table.classList.remove("table-shake");
    void table.offsetWidth;
    table.classList.add("table-shake");
    setTimeout(() => table.classList.remove("table-shake"), 600);

    const p = getPlayer(step.pid);
    const team = p.team ?? 0;
    const txt = step.text || "";
    const isCounter = txt.toUpperCase().includes("COUNTER");
    const title = isCounter ? "💥 COUNTER-KEMS ! 💥" : "⚡ KEMS ! ⚡";
    overlay.innerHTML = `
      <div class="callout-banner t${team}">
        <div class="callout-stars">✦ ✦ ✦</div>
        <div class="callout-title">${title}</div>
        <div class="callout-sub">${esc(p.name || "Player")} (Team ${team})</div>
      </div>
    `;
    overlay.classList.add("active");
    setTimeout(() => {
      overlay.classList.remove("active");
      overlay.innerHTML = "";
    }, 1800);
  }

  function updateBox(id, html, sig, manual) {
    const box = $(id);
    if (!box || box.dataset.sig === sig) return;
    const prevScroll = box.scrollTop;
    const wasBottom = box.scrollTop + box.clientHeight >= box.scrollHeight - 24;
    box.innerHTML = html;
    box.dataset.sig = sig;
    const now = box.querySelector(".now");
    if (manual && now) now.scrollIntoView({ block: "nearest" });
    else if (wasBottom) box.scrollTop = box.scrollHeight;
    else box.scrollTop = prevScroll;
  }

  function getPlayer(pid) {
    if (pid === null || pid === undefined) return { name: "SYSTEM" };
    const players = (data && data.players) || [];
    const p = players.find(x => x.pid === pid) || {};
    return { ...p, name: `P${pid + 1}` };
  }

  function renderFlow(steps, manual) {
    const chatSteps = steps.filter(e => ["MESSAGE", "CALL", "SYSTEM", "SWEEP", "SWAP", "PASS"].includes(e.type));
    updateBox("chat", chatSteps.length ? chatSteps.map(e => {
      const cls = e.type === "MESSAGE" ? "msg" : e.type === "CALL" ? "call" : e.type === "SWAP" ? "swap" : e.type === "PASS" ? "pass" : "sys";
      const p = getPlayer(e.pid);
      const team = p.team;
      const eq = team === undefined ? "" : ` t${team}`;
      const chip = team !== undefined ? `<span class="team-chip t${team}">T${team}</span> ` : "";
      const txt = e.text || "";
      const turnNum = e.turn ?? "";
      return `<div class="line ${cls}${eq} ${e.i === idx ? "now" : ""}"><span class="t">${turnNum}</span>`
           + `<span>${chip}${esc(txt)}</span></div>`;
    }).join("") : '<p class="vide">Nothing yet.</p>', `c${chatSteps.length}:${idx}`, manual);

    const negoSteps = steps.filter(e => ["NEGOTIATION", "DEBRIEFING"].includes(e.type));
    const negoBox = $("signals-chat");
    if (negoBox) {
      updateBox(negoBox.id, negoSteps.length ? negoSteps.map(e => {
        const p = getPlayer(e.pid);
        const team = p.team;
        const label = e.type === "DEBRIEFING" ? `team ${team} · debrief` : `team ${team}`;
        const prop = e.proposal;
        const trig = e.trigger;
        const agr = e.agree;
        const priv = e.private || "";
        const det = [prop ? `proposal: ${esc(prop)}` : "",
                     trig ? `trigger: <span class="mono">${esc(trig)}</span>` : "",
                     agr ? "<b>agreed</b>" : ""].filter(Boolean).join(" · ");
        const chip = team !== undefined ? `<span class="team-chip t${team}">T${team}</span> ` : "";
        return `<div class="line ${e.i === idx ? "now" : ""}">${chip}<b class="e${team}">${esc(p.name || "?")}</b>`
             + ` <span class="eyebrow">${label}</span><br>${esc(priv)}`
             + (det ? `<br><span class="eyebrow">${det}</span>` : "") + `</div>`;
      }).join("") : '<p class="vide">Nothing yet.</p>', `n${negoSteps.length}:${idx}`, manual);
    }

    const reflSteps = steps.filter(e => e.type === "REFLECTION" && e.private);
    const reflBox = $("thoughts-log");
    if (reflBox) {
      updateBox(reflBox.id, reflSteps.length ? reflSteps.map(e => {
        const p = getPlayer(e.pid);
        const team = p.team;
        const chip = team !== undefined ? `<span class="team-chip t${team}">T${team}</span> ` : "";
        const priv = e.private;
        const turnNum = e.turn;
        return `<div class="line ${e.i === idx ? "now" : ""}">${chip}<b class="e${team}">${esc(p.name || "?")}</b>`
             + ` <span class="eyebrow">${esc(e.type)} · T${turnNum}</span><br>${esc(priv)}</div>`;
      }).join("") : '<p class="vide">Nothing yet.</p>', `r${reflSteps.length}:${idx}`, manual);
    }
  }

  function renderEpisodes() {
    const eps = data.episodes || [];
    if (!eps.length) { $("episodes").innerHTML = '<p class="vide">No square formed yet.</p>'; return; }
    const players = data.players || [];
    $("episodes").innerHTML = eps.map(e => {
      const p = players.find(j => j.pid === e.pid) || {};
      const name = p.name || "?";
      const sqTurn = e.square_turn;
      const sigTurn = e.signal_turn;
      const spTurn = e.speech_turn;
      const kempsTurn = e.kemps_turn;
      const caught = e.caught;
      const unmasked = e.unmasked;

      const et = [`<span class="badge badge-accent">Square T${sqTurn}</span>`];
      et.push(sigTurn ? `<span class="badge badge-accent">Signal T${sigTurn}</span>`
            : spTurn ? `<span class="badge">Chat T${spTurn}</span>`
            : `<span class="badge">Silent</span>`);
      et.push(caught ? `<span class="badge badge-accent">Called T${kempsTurn}</span>`
                     : `<span class="badge">Uncalled</span>`);
      if (unmasked != null) et.push(unmasked
        ? `<span class="badge">Countered</span>`
        : `<span class="badge badge-accent">Kept Secret</span>`);
      return `<div class="line" style="margin-bottom:0.35rem"><b>${esc(name)}</b> ${et.join(" ")}</div>`;
    }).join("");
  }

  function renderEmpty() {
    $("dot").className = "dot";
    const roundEl = $("s-round");
    const turnEl = $("s-turn");
    if (roundEl) roundEl.textContent = "—";
    if (turnEl) turnEl.textContent = "—";
    $("s-score").textContent = "0 – 0";
    if ($("s-tok-in")) $("s-tok-in").textContent = "0";
    if ($("s-tok-cache")) $("s-tok-cache").textContent = "0";
    if ($("s-tok-out")) $("s-tok-out").textContent = "0";
    $("s-phase").textContent = "ready";

    $("q-tag").textContent = "WAIT";
    $("q-tag").className = "tag";
    const qText = $("q-text");
    if (qText) {
      qText.textContent = "No active match. Click 'Start Match' to begin!";
      qText.className = "vide";
    }

    $("scrub").max = 0;
    $("scrub").value = 0;
    $("s-pos").textContent = "0 / 0";

    for (let i = 0; i < 4; i++) {
      const el = $("seat-" + i);
      const team = (i === 0 || i === 3) ? 0 : 1;
      if (el) {
        el.className = `seat p${i + 1} t${team}`;
        el.innerHTML = `
          <div class="seat-header">
            <div class="avatar t${team}">P${i + 1}</div>
            <div class="seat-info">
              <div style="display:flex;align-items:center;gap:0.4rem;flex-wrap:wrap;">
                <span class="nom">P${i + 1}</span>
                <span class="team-chip t${team}">Team ${team}</span>
              </div>
              <span class="meta">No model</span>
            </div>
          </div>
          <div class="hands"></div>
        `;
      }
    }
    const ctr = $("center");
    if (ctr) {
      ctr.className = "center";
      ctr.innerHTML = "";
    }
    $("chat").innerHTML = `<p class="vide">Nothing yet.</p>`;
    const negoBox = $("signals-chat");
    if (negoBox) negoBox.innerHTML = `<p class="vide">Nothing yet.</p>`;
    const reflBox = $("thoughts-log");
    if (reflBox) reflBox.innerHTML = `<p class="vide">Nothing yet.</p>`;
    $("episodes").innerHTML = `<p class="vide">No square formed.</p>`;
    if ($("b-dl")) $("b-dl").hidden = true;
  }

  function render() {
    const isRunning = data && data.running;
    if (!data || (!isRunning && (!data.timeline || data.timeline.length === 0))) {
      renderEmpty();
      return;
    }

    const t = tl();
    $("dot").className = "dot" + (isRunning || launching ? " on" : "");
    const roundEl = $("s-round");
    const turnEl = $("s-turn");
    if (roundEl) roundEl.textContent = data.round ?? "—";
    if (turnEl) turnEl.textContent = data.turn ?? "—";
    $("s-score").textContent = data.scores ? `${data.scores?.["0"] ?? 0} – ${data.scores?.["1"] ?? 0}` : "0 – 0";
    if ($("s-tok-in")) $("s-tok-in").textContent = (data.tokens?.prompt_total ?? 0).toLocaleString("en-US");
    if ($("s-tok-cache")) $("s-tok-cache").textContent = (data.tokens?.cached_total ?? 0).toLocaleString("en-US");
    if ($("s-tok-out")) $("s-tok-out").textContent = (data.tokens?.completion_total ?? 0).toLocaleString("en-US");
    $("s-phase").textContent = isRunning ? data.phase : "match finished";

    if (!t.length) {
      renderTable(null);
      $("scrub").max = 0; $("scrub").value = 0;
      $("s-pos").textContent = "0 / 0";
      $("q-tag").textContent = "NEGO";
      $("q-tag").className = "tag NEGOTIATION";
      const qText = $("q-text");
      if (qText) {
        qText.textContent = isRunning || launching ? "Negotiating secret signals..." : "Waiting to launch...";
        qText.className = "";
      }
      $("chat").innerHTML = `<p class="vide">Waiting for first turn...</p>`;
      const negoBox = $("signals-chat");
      if (negoBox) negoBox.innerHTML = `<p class="vide">Negotiation in progress...</p>`;
      const reflBox = $("thoughts-log");
      if (reflBox) reflBox.innerHTML = `<p class="vide">Reflecting...</p>`;
      $("episodes").innerHTML = `<p class="vide">No square formed.</p>`;
      if ($("b-dl")) $("b-dl").hidden = true;
      return;
    }

    const step = t[idx];
    $("scrub").max = t.length - 1; $("scrub").value = idx;
    $("s-pos").textContent = `${idx + 1} / ${t.length}`;
    $("q-tag").textContent = step.type; $("q-tag").className = "tag " + step.type;
    const qText = $("q-text");
    if (qText) {
      qText.textContent = step.text || "";
      qText.className = "";
    }
    const prevTurnId = "b-turn-prev";
    const nextTurnId = "b-turn-next";
    for (const [b, on] of [["b-prev", idx > 0], ["b-first", idx > 0], [prevTurnId, idx > 0],
                           ["b-next", idx < t.length - 1], [nextTurnId, idx < t.length - 1]])
      if ($(b)) $(b).disabled = !on;

    const nav = manualNav;
    manualNav = false;
    const isForwardStep = idx === prevIdx + 1 && t[idx];
    const isSweep = isForwardStep && t[idx].type === "SWEEP";

    if (isSweep) {
      renderTable(step, true);
      animateSweep(step.center || []);
    } else {
      renderTable(step, false);
      const takeCard = t[idx].take;
      const discardCard = t[idx].discard;
      if (isForwardStep && t[idx].type === "SWAP" && takeCard) {
        const siege = $("seat-" + t[idx].pid);
        const center = $("center");
        if (siege && center) {
          // Try to find the exact card elements for precise animation origins/destinations
          const centerCardEl = center.querySelector(`[data-c="${CSS.escape(takeCard)}"]`);
          const handCardEl = discardCard ? siege.querySelector(`[data-c="${CSS.escape(discardCard)}"]`) : null;

          const fromRect = centerCardEl ? centerCardEl.getBoundingClientRect() : center.getBoundingClientRect();
          const toRect = siege.getBoundingClientRect();
          const fromHandRect = handCardEl ? handCardEl.getBoundingClientRect() : siege.getBoundingClientRect();
          const toCenterRect = centerCardEl ? centerCardEl.getBoundingClientRect() : center.getBoundingClientRect();

          // Briefly highlight source cards so the eye knows what's moving
          highlightCard(centerCardEl, "card-lift", 300);
          if (handCardEl) highlightCard(handCardEl, "card-lift", 300);

          animateFlight(takeCard, fromRect, toRect, "flying-take", "TAKE", 950, 15);
          if (discardCard) {
            animateFlight(discardCard, fromHandRect, toCenterRect, "flying-discard", "DISCARD", 950, -15);
          }
        }
      } else if (isForwardStep && t[idx].type === "CALL") {
        triggerCallAnimation(t[idx]);
      }
    }
    prevIdx = idx;
    renderFlow(t.slice(0, idx + 1), nav);
    renderEpisodes();
    const dl = $("b-dl");
    if (dl) {
      dl.hidden = !data.transcript;
      if (data.transcript) dl.setAttribute("download", data.transcript);
    }
  }

  const MODELS = {
    mistral: ["mistral-large-4", "mistral-large-latest", "mistral-small-latest", "ministral-8b-latest"]
  };

  let apiKeys = {};
  async function loadConfig() {
    try {
      const config = await (await fetch("/api/config")).json();
      apiKeys = config.keys || {};
    } catch (e) {}
  }

  function populatePlayersTable() {
    const tbody = $("f-players");
    if (!tbody) return;
    tbody.innerHTML = [0, 1, 2, 3].map(i => {
      const team = (i === 0 || i === 3) ? 0 : 1;
      return `
      <tr>
        <td><strong style="font-family:var(--font-pixel)">P${i + 1}</strong></td>
        <td><span class="team-tag t${team}"><span class="pixel-dot t${team}"></span>Team ${team}</span></td>
        <td><select id="f-model-${i}" data-r="model" data-i="${i}">${MODELS.mistral.map(m => `<option value="${m}">${m}</option>`).join("")}</select></td>
        <td><input type="number" id="f-temp-${i}" data-r="temperature" data-i="${i}" value="0.7" step="0.1" min="0" max="2" style="width:4.5rem"></td>
      </tr>`;
    }).join("");
  }
  populatePlayersTable();

  const getPlayerField = (r, i) => {
    const tableEl = $("f-players");
    return tableEl.querySelector(`[data-r="${r}"][data-i="${i}"]`).value;
  };

  const roundsSelect = $("f-rounds");
  if (roundsSelect) {
    roundsSelect.innerHTML = [1, 2, 3, 4, 5].map(n =>
      `<option value="${n}"${n === 3 ? " selected" : ""}>${n} round${n > 1 ? "s" : ""}</option>`).join("");
    const alignPoints = () => {
      const pointsInput = $("f-points");
      if (pointsInput) pointsInput.value = +roundsSelect.value + 1;
    };
    roundsSelect.onchange = alignPoints;
    alignPoints();
  }

  const randomBtn = $("b-randomize");
  if (randomBtn) {
    randomBtn.onclick = () => {
      if ($("f-seed-cards")) $("f-seed-cards").value = Math.floor(Math.random() * 1e6);
      if ($("f-seed-order")) $("f-seed-order").value = Math.floor(Math.random() * 1e6);
    };
  }

  if ($("b-dlg-close")) $("b-dlg-close").onclick = () => $("dlg").close();

  $("dlg").addEventListener("keydown", e => {
    if (e.key === "Escape") $("dlg").close();
  });

  const newMatchBtn = $("b-new-match");
  if (newMatchBtn) {
    newMatchBtn.onclick = () => {
      loadConfig();
      $("dlg").showModal();
    };
  }

  const launchBtn = $("b-launch");
  if (launchBtn) {
    launchBtn.onclick = async () => {
      const err = $("f-err");
      if (err) err.hidden = true;

      const roundsVal = $("f-rounds");
      const turnsVal = $("f-turns");
      const ranksVal = $("f-ranks");

      const settings = {
        seed: $("f-seed-cards") ? +$("f-seed-cards").value : 11,
        seed_cards: $("f-seed-cards") ? +$("f-seed-cards").value : 11,
        seed_order: $("f-seed-order") ? +$("f-seed-order").value : 22,
        ranks: ranksVal ? +ranksVal.value : 10,
        max_turns: turnsVal ? +turnsVal.value : 8,
        max_rounds: roundsVal ? +roundsVal.value : 3,
        points_to_win: $("f-points") ? +$("f-points").value : 2,
        pause: $("f-pause") ? +$("f-pause").value : 1.5,
        eval_signals: $("f-eval") ? $("f-eval").checked : false,
        players: [0, 1, 2, 3].map(i => {
          const modelVal = getPlayerField("model", i);
          return {
            agent: "mistral",
            model: modelVal,
            temperature: +getPlayerField("temperature", i)
          };
        }),
      };

      try {
        if ($("main-error-banner")) $("main-error-banner").style.display = "none";
        const r = await fetch("/api/launch", { method: "POST", body: JSON.stringify(settings) });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error || "failed to launch match");
        $("dlg").close();

        setFollowLive(true);
        idx = 0;
        prevIdx = -1;
        launching = true;
        render();
      } catch (e) {
        if (err) {
          err.textContent = "Could not launch: " + e.message;
          err.hidden = false;
        }
      }
    };
  }

  async function pollState() {
    try {
      const r = await fetch("state.json?t=" + Date.now(), { cache: "no-store" });
      if (r.ok) {
        data = await r.json();
        const running = data.running;
        if (running) {
          launching = false;
        }

        const activeAPIs = Object.entries(data.api_status || {})
          .filter(([pid, statusObj]) => statusObj && statusObj.status && statusObj.status !== "idle")
          .map(([pid, statusObj]) => {
            const players = data.players || [];
            const p = players.find(x => x.pid == pid) || { name: `Player ${Number(pid) + 1}` };
            return `${p.name}: ${statusObj.message}`;
          });
        if (activeAPIs.length > 0) {
          $("live-api-summary").textContent = activeAPIs.join(" | ");
          $("live-api-summary").style.display = "inline";
        } else {
          $("live-api-summary").textContent = "";
          $("live-api-summary").style.display = "none";
        }

        if (followLive) idx = Math.max(0, tl().length - 1);
        render();
      } else {
        data = null;
        render();
      }
    } catch (e) {}

    try {
      const s = await (await fetch("/api/status")).json();
      const errText = s.error;
      if (errText) {
        $("f-err").textContent = errText;
        $("f-err").hidden = false;
        $("main-error-text").textContent = "Game error / Launch failed: " + errText;
        $("main-error-banner").style.display = "flex";
        launching = false;
      } else {
        $("main-error-banner").style.display = "none";
      }

      const matchBtn = $("b-new-match");
      const isBusy = s.busy;
      if (isBusy || launching) {
        $("loading-spinner").style.display = "inline-block";
        if (matchBtn) {
          matchBtn.disabled = true;
          matchBtn.innerHTML = `<span class="spinner"></span> RUNNING...`;
        }
      } else {
        $("loading-spinner").style.display = "none";
        if (matchBtn) {
          matchBtn.disabled = false;
          matchBtn.innerHTML = "START MATCH";
        }
      }
    } catch (e) {}

    setTimeout(pollState, 600);
  }

  pollState();
})();
