/* shellquest GUI — read-only renderer driven by Server-Sent Events. */
"use strict";
const SQ = (() => {
  let es = null, prev = null, manualTab = "howto", manualData = null, firstRun = true;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => (s ?? "").toString()
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function connect() {
    if (es) es.close();
    es = new EventSource("/api/stream");
    es.addEventListener("state", (e) => {
      try { render(JSON.parse(e.data)); } catch (_) {}
    });
    es.onopen = () => showApp(true);
    es.onerror = () => { /* EventSource auto-retries; show offline if never opened */
      if (!prev) showApp(false);
    };
    // initial fetch so we don't wait for the first change
    fetch("/api/state").then(r => r.json()).then(s => { if (s.ready) render(s); else showApp(false); })
      .catch(() => showApp(false));
    fetch("/api/manual").then(r => r.json()).then(d => { manualData = d; renderManual(); });
  }

  function showApp(ok) {
    $("app").classList.toggle("hidden", !ok);
    $("offline").classList.toggle("hidden", ok);
  }

  function render(s) {
    if (!s || !s.ready) { showApp(false); return; }
    showApp(true);
    const L = s.level;
    // top bar
    $("lvl").innerHTML = `УР. ${L.id} — <b>${esc(L.name)}</b>`;
    const pct = Math.min(100, 100 * L.xp / Math.max(1, L.xp_required));
    $("xpfill").style.width = pct + "%";
    $("xplabel").textContent = `${L.xp} / ${L.xp_required} XP`;
    $("cmdsmini").textContent = `команды ${L.commands_open}/${L.commands_target}`;
    // coins (+ delta animation)
    if (prev && s.coins !== prev.coins) flashCoins(s.coins - prev.coins);
    $("coins").firstChild.textContent = `◈ ${s.coins}`;
    renderBoss(s.boss);
    renderRing(s);
    renderChips(s.commands);
    renderMap(s);
    renderQuests(s);
    prev = s;
    firstRun = false;
  }

  function renderBoss(b) {
    const el = $("boss");
    el.className = "boss-badge " + b.state;
    const txt = { locked: "Босс закрыт", unlocked: "⚔ Босс доступен",
      in_fight: `Бой идёт — фаза ${b.phase}/${b.phases_total}`, defeated: "✓ Босс повержен" };
    el.textContent = txt[b.state] || "Босс";
    el.onclick = (b.state === "unlocked" || b.state === "in_fight")
      ? () => bossInfo(b) : null;
  }
  function bossInfo(b) {
    const cmd = b.state === "unlocked" ? "sq boss start" : "sq boss resume";
    copy(cmd, `Скопировано: ${cmd}`);
    if (b.brief) toast(b.name + ": " + b.brief, 3200);
  }

  function renderRing(s) {
    const L = s.level, R = 78, C = 2 * Math.PI * R;
    const frac = Math.min(1, L.xp / Math.max(1, L.xp_required));
    const fg = $("ringfg");
    fg.setAttribute("stroke-dasharray", C.toFixed(1));
    fg.setAttribute("stroke-dashoffset", (C * (1 - frac)).toFixed(1));
    $("ringxp").textContent = L.xp;
    const left = Math.max(0, L.xp_required - L.xp);
    $("ringgoal").textContent = left > 0 ? `до босса: ${left} XP` : "порог опыта взят";
    setCond("cond-xp", s.xp_conditions.xp_ok);
    setCond("cond-cmd", s.xp_conditions.commands_ok);
  }
  function setCond(id, ok) {
    const el = $(id); el.classList.toggle("ok", ok);
    el.querySelector(".box").textContent = ok ? "☑" : "☐";
  }

  function renderChips(cmds) {
    $("chips").innerHTML = cmds.map(c =>
      `<span class="chip ${c.open ? "open" : ""}" ${c.open ? `onclick="SQ.openCodex('${esc(c.name)}')"` : ""}
        title="${c.open ? "открыть карточку" : "ещё не открыта"}">${esc(c.name)}</span>`).join("");
  }

  function renderMap(s) {
    const cur = s.current_level_index, done = new Set(s.defeated_levels || []);
    let html = "";
    s.acts.forEach((a, ai) => {
      html += `<div class="act-label">АКТ ${a.act === 1 ? "I" : "II"}</div>`;
      a.levels.forEach((lid) => {
        let cls = "locked";
        if (done.has(lid)) cls = "done";
        else if (lid === cur) cls = "current";
        else if (lid < cur) cls = "done";
        const line = (lid !== a.levels[0] || ai > 0) ? '<span class="line"></span>' : "";
        html += `<div class="node ${cls}">${line}<div class="dot">${lid}</div>
          <div class="nm">Уровень ${lid}${lid === cur ? " ◂ ты здесь" : (cls === "locked" ? " 🔒" : "")}</div></div>`;
      });
    });
    $("map").innerHTML = html;
  }

  function renderQuests(s) {
    const box = $("quests");
    const prevDone = prev ? new Set(prev.quests.filter(q => q.status === "done").map(q => q.id)) : new Set();
    const active = s.quests.filter(q => q.status === "available");
    const blocked = s.quests.filter(q => q.status === "blocked");
    const done = s.quests.filter(q => q.status === "done");
    let html = "";
    active.forEach(q => html += questCard(q, prevDone));
    blocked.forEach(q => html += questCard(q, prevDone));
    if (done.length) {
      html += `<div class="done-group" onclick="SQ.toggleDone()">▾ Выполнено: ${done.length}</div>
        <div id="donebox" class="${doneCollapsed ? "hidden" : ""}">`;
      done.forEach(q => html += `<div class="q doneline"><span class="t">✓ ${esc(q.id)} — ${esc(q.title)}</span>
        <span class="r">+${q.xp} XP · +${q.coins} ◈</span></div>`);
      html += `</div>`;
    }
    box.innerHTML = html || `<div class="card" style="color:var(--muted)">Заданий нет.</div>`;
    // just-done animation
    s.quests.filter(q => q.status === "done" && !prevDone.has(q.id) && !firstRun)
      .forEach(q => toast(`✓ ${q.id} — ${q.title}  +${q.xp} XP`, 2600));
  }

  function questCard(q, prevDone) {
    const stText = q.status === "available" ? "доступно"
      : q.status === "blocked" ? `ждёт: ${q.blocked_by.join(", ")}` : "выполнено ✓";
    const dots = q.validators.map(v => `<span class="dot2 ${v.pass ? "pass" : ""}" title="${esc(v.name)}"></span>`).join("");
    const nPass = q.validators.filter(v => v.pass).length;
    let actions = `<button class="cpy" onclick="SQ.copy('sq quest ${q.id}',this)">sq quest ${q.id}</button>`;
    if (q.status !== "done" && q.hints_total > 0) {
      actions += `<button class="cpy" onclick="SQ.copy('sq hint ${q.id}',this)">sq hint ${q.id}</button>`;
      if (q.next_hint_cost != null) actions += `<span class="hintcost">${q.next_hint_cost} ◈</span>`;
    }
    if (q.type === "flag") actions += `<span class="hintcost" style="color:var(--muted)">флаг: sq flag …</span>`;
    return `<div class="q ${q.status}">
      <h3>${esc(q.id)} — ${esc(q.title)} <span class="tag ${q.type}">${q.type}</span></h3>
      <div class="status">${stText} <span class="dots">${dots}</span>
        <span class="mono" style="color:var(--dim)"> ${nPass}/${q.validators.length}</span></div>
      <div class="goal">${esc(q.goal)}</div>
      <div class="actions">${actions}</div></div>`;
  }

  // manual ------------------------------------------------------------
  let doneCollapsed = false;
  function toggleDone() { doneCollapsed = !doneCollapsed; const b = $("donebox"); if (b) b.classList.toggle("hidden", doneCollapsed); }

  function renderManual() {
    if (!manualData) return;
    const body = $("manualbody");
    if (manualTab === "howto") {
      body.innerHTML = `<div class="howto">` + manualData.howto.map(([k, v]) =>
        `<div class="h"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join("") + `</div>`;
    } else if (manualTab === "commands") {
      body.innerHTML = `<input class="search" id="cmdsearch" placeholder="поиск команды…" oninput="SQ.filterCmds(this.value)">
        <table class="cmds" id="cmdstable">` + manualData.commands.map(([c, d, ex]) =>
        `<tr><td class="c">${esc(c)}</td><td>${esc(d)}</td>
          <td class="ex">${esc(ex)}</td><td><button class="cpy" onclick="SQ.copy('${esc(ex)}',this)">копировать</button></td></tr>`).join("") + `</table>`;
    } else if (manualTab === "codex") {
      const open = (prev && prev.codex ? prev.codex.filter(c => c.open) : []);
      body.innerHTML = `<div class="codexlist">` + (open.length
        ? open.map(c => `<button class="cpy" onclick="SQ.openCodex('${esc(c.tool)}')">${esc(c.tool)}</button>`).join("")
        : `<span style="color:var(--muted)">Пока не открыто ни одной утилиты.</span>`)
        + `</div><div id="codexcard"></div>`;
    }
  }
  function tab(ev, name) { ev.stopPropagation(); manualTab = name;
    document.querySelectorAll(".manual .tab").forEach(t => t.classList.toggle("on", t.dataset.tab === name));
    if ($("manual").classList.contains("collapsed")) toggleManual();
    renderManual();
  }
  function toggleManual() { $("manual").classList.toggle("collapsed");
    $("chev").textContent = $("manual").classList.contains("collapsed") ? "▴ F1" : "▾ F1"; }
  function filterCmds(q) {
    q = q.toLowerCase();
    document.querySelectorAll("#cmdstable tr").forEach(tr =>
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none");
  }
  function openCodex(tool) {
    manualTab = "codex";
    document.querySelectorAll(".manual .tab").forEach(t => t.classList.toggle("on", t.dataset.tab === "codex"));
    if ($("manual").classList.contains("collapsed")) toggleManual();
    renderManual();
    fetch("/api/codex?tool=" + encodeURIComponent(tool)).then(r => r.json()).then(d => {
      const c = $("codexcard");
      if (c) c.innerHTML = d.card ? `<div class="codexcard">${esc(d.card)}</div>`
        : `<div class="codexcard">Карточка недоступна. Попробуй: man ${esc(tool)}</div>`;
    });
  }

  // utils -------------------------------------------------------------
  function copy(text, btnOrMsg) {
    const done = () => {
      if (btnOrMsg && btnOrMsg.classList) { btnOrMsg.classList.add("copied");
        const old = btnOrMsg.textContent; setTimeout(() => { btnOrMsg.classList.remove("copied"); btnOrMsg.textContent = old; }, 900);
      }
      toast("Скопировано: " + text);
    };
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
    else fallbackCopy(text, done);
  }
  function fallbackCopy(text, cb) {
    const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t);
    t.select(); try { document.execCommand("copy"); } catch (_) {} t.remove(); cb && cb();
  }
  let toastT = null;
  function toast(msg, ms = 1500) {
    const el = $("toast"); el.textContent = msg; el.classList.add("show");
    clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove("show"), ms);
  }
  function flashCoins(delta) {
    const d = $("coinsd"); d.textContent = (delta > 0 ? " +" : " ") + delta;
    d.style.color = delta > 0 ? "var(--ok)" : "var(--bad)"; d.style.opacity = "1";
    setTimeout(() => { d.style.opacity = "0"; }, 1200);
  }

  document.addEventListener("keydown", (e) => { if (e.key === "F1") { e.preventDefault(); toggleManual(); } });

  return { connect, reconnect: connect, copy, toggleManual, tab, filterCmds, openCodex, toggleDone,
           bossInfo: () => {} };
})();
window.addEventListener("DOMContentLoaded", SQ.connect);
