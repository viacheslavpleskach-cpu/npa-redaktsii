// zbir.js — збирання карток і текстів редакцій НПА з zakon.rada.gov.ua у браузері.
// Автор: В'ячеслав Плескач. Джерело даних: zakon.rada.gov.ua (© Верховна Рада України, CC BY 4.0).
//
// Виконується на сторінці https://zakon.rada.gov.ua/ (той самий домен, тому запити дозволені).
// Сайт віддає дані лише на запити з України, тому скрипт працює в браузері користувача.
//
// Використання (у консолі або через інструмент виконання JS):
//   zbirStart([{nreg:"1798-19", rezhym:"povna", chastyna:40}, ...], {vidomi:{"1798-19":["20161221", ...]}, chastyna:40});
//   zbirStan()   // перебіг: скільки актів і редакцій зібрано, які файли завантажено
//
// rezhym: "povna"  — усі редакції;
//         "chynna" — лише редакція, чинна на сьогодні;
//         "odyn"   — один текст (документ без редакцій або без потреби в історії).
// chastyna: скільки редакцій в одному файлі (для акта або для всіх через opts).
// tilky: завантажити лише ці редакції (щотижневе оновлення; картка завантажується завжди).
// vidomi: редакції, які вже є в архіві (їх не завантажувати; для щотижневого оновлення).
// Результат: файли npa_<nreg>_pNN.json у теці завантажень браузера.

(function () {
  const ZATRYMKA = 350; // мс між запитами до сайту
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const st = (window.__zbir = window.__zbir || { aktiv: 0, gotovo: 0, redaktsii: 0, faily: [], pomylky: [], pratsiuie: false });

  function bezpechno(n) { return n.replace(/[\/\\:*?"<>|]/g, "_"); }

  async function otrymaty(url) {
    for (let sproba = 1; sproba <= 3; sproba++) {
      try {
        const r = await fetch(url);
        if (r.ok) return { url: r.url, html: await r.text() };
        if (r.status === 404) return null;
      } catch (e) { /* повтор */ }
      await sleep(1500 * sproba);
    }
    throw new Error("не вдалося отримати " + url);
  }

  // Текст редакції — масив рядків. Працює і з абзацами <p>, і з давніми редакціями,
  // де текст іде суцільним блоком із <br>. Клітинки таблиць розділяються « | ».
  const SHUM = new Set(["Eng", "Укр", "Зміст документа", "Пошук у тексті"]);
  function tekstRadky(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    doc.querySelectorAll("script, style, noscript").forEach((e) => e.remove());
    doc.querySelectorAll("br").forEach((b) => b.replaceWith("\n"));
    doc.querySelectorAll("td, th").forEach((e) => e.append(" | "));
    doc.querySelectorAll("p, div, pre, tr, li, h1, h2, h3, h4, h5, h6, table, blockquote").forEach((e) => e.append("\n"));
    return doc.body.textContent.split("\n")
      .map((s) => s.replace(/[ \t\u00a0\r\f\v]+/g, " ").replace(/(\s*\|\s*)+$/, "").replace(/^(\s*\|\s*)+/, "").trim())
      .filter((s) => s && !SHUM.has(s) && !/^((\d{2}\.\d{2}\.\d{4})\s*)+(•.*)?$/.test(s) && !/^•(\s*\d{2}\.\d{2}\.\d{4})*$/.test(s));
  }

  function rozibratyKartku(html, nreg) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const svii = (href) => { try { return decodeURIComponent(href).includes("/" + nreg + "/ed"); } catch (e) { return href.includes("/" + nreg + "/ed"); } };
    const nazva = ((doc.querySelector("h1") || {}).textContent || doc.title || "").replace(/\s+/g, " ").trim();
    const body = doc.body.textContent.replace(/\s+/g, " ");
    const stan = ((body.match(/Стан:\s*(.{0,60}?)(?:Ідентифікатор|Документи|$)/) || [])[1] || "").trim();
    const redaktsii = [], podii = [];
    doc.querySelectorAll("tr").forEach((tr) => {
      const a = [...tr.querySelectorAll('a[href*="/ed"]')].find((x) => svii(x.getAttribute("href") || ""));
      const dat = tr.querySelector("span.dat1, span.dat0"); // dat0 — рядок чинної редакції
      const tds = [...tr.children].map((c) => c.textContent.replace(/\s+/g, " ").trim());
      // чинна редакція: посилання веде на /show/<nreg> без /ed, дата — у span.dat1
      const vlasne = [...tr.querySelectorAll("a")].some((x) => { try { return /\/show\/[^#]*$/.test(x.getAttribute("href") || "") && decodeURIComponent(x.getAttribute("href")).replace(/#.*/, "").endsWith("/show/" + nreg); } catch (e) { return false; } });
      const dm = dat && dat.textContent.trim().match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
      if (!a && vlasne && dm && /^(Редакція|Прийняття|Нова редакція)/.test(tds[1] || "") && !/текст відсутній/.test(tr.textContent)) {
        const opys = tds[1] || "";
        const pidstava = ((opys.match(/підстава\s*-\s*(.+?)(?:\s+(?:поточна|наступна|попередня|остання|перша) редакція.*)?$/) || [])[1] || "").split(/\s*,\s*/).filter(Boolean);
        redaktsii.push({ ed: dm[3] + dm[2] + dm[1], data_na_saiti: tds[0] || "", opys, pidstava, bez_posylannia: true });
        return;
      }
      if (a) {
        const ed = ((a.getAttribute("href") || "").match(/\/ed(\d{8})/) || [])[1];
        if (!ed) return;
        const opys = tds[1] || "";
        const pidstava = ((opys.match(/підстава\s*-\s*(.+)$/) || [])[1] || "").split(/\s*,\s*/).filter(Boolean);
        redaktsii.push({ ed, data_na_saiti: tds[0] || "", opys, pidstava });
      } else if (dat) {
        podii.push({ data: dat.textContent.trim(), opys: tds.slice(1).join(" ").trim() });
      }
    });
    // унікальність і порядок
    const bachyly = new Set();
    const red = redaktsii.filter((r) => (bachyly.has(r.ed) ? false : (bachyly.add(r.ed), true))).sort((x, y) => (x.ed < y.ed ? -1 : 1));
    return { nazva, stan, redaktsii: red, podii };
  }

  function zavantazhyty(imia, obj) {
    const blob = new Blob([JSON.stringify(obj)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = imia;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    st.faily.push(imia);
  }

  // Картка акта: /laws/card, а якщо там немає переліку редакцій — /rada/card (підзаконні акти)
  async function kartkaAkta(nreg) {
    const k = await otrymaty("/laws/card/" + nreg);
    if (!k) throw new Error("картку " + nreg + " не знайдено");
    let prefiks = /\/rada\//.test(k.url) ? "rada" : "laws";
    let kartka = rozibratyKartku(k.html, nreg);
    // підзаконні акти: /laws/card перенаправляє на сторінку тексту — беремо /rada/card
    if (!kartka.redaktsii.length && (prefiks === "laws" || !/\/card\//.test(k.url))) {
      const r = await otrymaty("/rada/card/" + nreg);
      if (r) { const kr = rozibratyKartku(r.html, nreg); if (kr.redaktsii.length) { kartka = kr; prefiks = "rada"; } }
    }
    return { prefiks, kartka };
  }

  async function zibratyAkt(akt, vidomi, chastyna) {
    const nreg = akt.nreg;
    const { prefiks, kartka } = await kartkaAkta(nreg);
    const sohodni = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const realni = kartka.redaktsii.filter((r) => !r.ed.startsWith("3000") && r.ed <= sohodni);
    let potribni;
    if (akt.rezhym === "povna") potribni = kartka.redaktsii.map((r) => r.ed);
    else if (realni.length) potribni = [realni[realni.length - 1].ed];
    else potribni = [];
    const vid = new Set(vidomi[nreg] || []);
    potribni = potribni.filter((e) => !vid.has(e));
    if (Array.isArray(akt.tilky)) potribni = akt.tilky.filter((e) => kartka.redaktsii.some((r) => r.ed === e)); // лише ці редакції
    const zahalom = { nreg, prefiks, zibrano: new Date().toISOString(), dzherelo: "https://zakon.rada.gov.ua/" + prefiks + "/card/" + nreg, kartka };
    let teksty = {}, n = 0, chast = 1;
    const vyvantazhyty = (ostannia) => {
      zavantazhyty("npa_" + bezpechno(nreg) + "_p" + String(chast).padStart(2, "0") + ".json",
        Object.assign({}, zahalom, { chastyna: chast, ostannia, teksty }));
      teksty = {}; n = 0; chast++;
    };
    if (!kartka.redaktsii.length && !vid.has("bez_redaktsii") && !Array.isArray(akt.tilky)) {
      // документ без переліку редакцій — один чинний текст
      const f = await otrymaty("/" + prefiks + "/show/" + nreg + ".frame");
      if (f) { teksty["bez_redaktsii"] = tekstRadky(f.html); st.redaktsii++; n++; }
      await sleep(ZATRYMKA);
    }
    for (const ed of potribni) {
      const f = await otrymaty("/" + prefiks + "/show/" + nreg + "/ed" + ed + ".frame");
      teksty[ed] = f ? tekstRadky(f.html) : null;
      st.redaktsii++; n++;
      if (n >= chastyna) vyvantazhyty(false);
      await sleep(ZATRYMKA);
    }
    vyvantazhyty(true); // остання частина (завжди: несе актуальну картку)
  }

  window.zbirStart = function (akty, opts) {
    opts = opts || {};
    if (st.pratsiuie) return "уже працює";
    Object.assign(st, { aktiv: akty.length, gotovo: 0, redaktsii: 0, faily: [], pomylky: [], pratsiuie: true, pochatok: new Date().toISOString() });
    (async () => {
      for (const akt of akty) {
        st.potochnyi = akt.nreg;
        try { await zibratyAkt(akt, opts.vidomi || {}, akt.chastyna || opts.chastyna || 40); }
        catch (e) { st.pomylky.push(akt.nreg + ": " + e.message); }
        st.gotovo++;
      }
      st.pratsiuie = false; st.kinets = new Date().toISOString(); st.potochnyi = "";
    })();
    return "розпочато: " + akty.length + " акт(ів)";
  };

  window.zbirStan = function () {
    return JSON.stringify({ pratsiuie: st.pratsiuie, potochnyi: st.potochnyi, aktiv: st.aktiv, gotovo: st.gotovo,
      redaktsii: st.redaktsii, faily: st.faily, pomylky: st.pomylky, pochatok: st.pochatok, kinets: st.kinets });
  };

  // Лише картки (для щотижневої перевірки, без текстів): редакції, стан і кількість подій
  window.zbirKartky = async function (nregs) {
    const out = {};
    for (const nreg of nregs) {
      try {
        const { kartka: c } = await kartkaAkta(nreg);
        out[nreg] = { eds: c.redaktsii.map((r) => r.ed), stan: c.stan, podii: c.podii.length };
      } catch (e) { out[nreg] = "помилка"; }
      await sleep(ZATRYMKA);
    }
    window.__kartky = out;
    return out;
  };

  // Перевірити картки у фоні (виклик повертається одразу; результат — zbirKartkyStan())
  window.zbirKartkyStart = function (nregs) {
    window.__kartky = null;
    window.zbirKartky(nregs);
    return "перевірка карток: " + nregs.length;
  };
  window.zbirKartkyStan = function () { return window.__kartky ? "готово: " + Object.keys(window.__kartky).length : "ще триває"; };
  // Зберегти результат перевірки карток файлом npa_kartky_<дата>.json (для onovlennia.py porivniaty)
  window.zbirKartkyZberehty = function () {
    if (!window.__kartky) return "перевірка карток ще триває";
    const imia = "npa_kartky_" + new Date().toISOString().slice(0, 10) + ".json";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(window.__kartky)], { type: "application/json" }));
    a.download = imia; document.body.appendChild(a); a.click(); a.remove();
    return "збережено " + imia;
  };
})();
