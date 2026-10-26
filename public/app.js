(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const STORE_KEY = "cuaderno.v1";
  const BACKUP_KEY = "cuaderno.copia.v1";
  const OPEN_KEY = "cuaderno.abiertas.v1";
  const MAX_CONTENT = 10000;

  const state = {
    tree: null,
    byId: {},
    parentOf: {},
    selected: null,
    open: new Set(),
    query: "",
    results: [],
    saveTimer: null,
    saveId: null,
  };
  let statusEl = null;

  // ---------- Utilidades ----------

  const ICONS = {
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    note: '<path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M14 3v5h5"/>',
    chevron: '<path d="M9 6l6 6-6 6"/>',
  };

  function icon(name, extra = "") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", `icon ${extra}`.trim());
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = ICONS[name];
    return svg;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function button(label, className, onClick) {
    const node = el("button", className, label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
  }

  const isFolder = (node) => node.kind === "folder";

  function plural(count, one, many) {
    return `${count} ${count === 1 ? one : many}`;
  }

  function notesIn(node) {
    if (!isFolder(node)) return 1;
    return node.children.reduce((total, child) => total + notesIn(child), 0);
  }

  function countAll(node) {
    if (!isFolder(node)) return 1;
    return 1 + node.children.reduce((total, child) => total + countAll(child), 0);
  }

  function pathOf(id) {
    const nodes = [];
    for (let current = id; current; current = state.parentOf[current]) nodes.unshift(state.byId[current]);
    return nodes;
  }

  function currentFolderId() {
    const node = state.byId[state.selected];
    return isFolder(node) ? node.id : state.parentOf[node.id];
  }

  function uniqueName(base, folderId) {
    const taken = new Set(state.byId[folderId].children.map((child) => child.name.toLowerCase()));
    if (!taken.has(base.toLowerCase())) return base;
    for (let n = 2; ; n++) {
      if (!taken.has(`${base} ${n}`.toLowerCase())) return `${base} ${n}`;
    }
  }

  let toastTimer;
  function toast(message, isError = false) {
    const node = $("#toast");
    node.textContent = message;
    node.className = "toast" + (isError ? " error" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.add("hidden"), 3500);
  }

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (error) { /* sin almacenamiento */ }
  }

  function read(key) {
    try { return localStorage.getItem(key); } catch (error) { return null; }
  }

  // ---------- Comunicación con la API ----------

  async function call(path, body) {
    const response = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await response.json(); } catch (error) { /* respuesta vacía */ }
    if (!response.ok) throw new Error(data.error || "No se pudo completar la acción");
    return data;
  }

  const offline = (error) => error instanceof TypeError;

  async function run(action, payload) {
    try {
      await flushSave();
      const data = await call(`/api/${action}`, { tree: state.tree, ...payload });
      if (data.tree) setTree(data.tree);
      return data;
    } catch (error) {
      toast(offline(error) ? "No hay conexión con el servidor" : error.message, true);
      return null;
    }
  }

  // ---------- Estado ----------

  function reindex() {
    state.byId = {};
    state.parentOf = {};
    const stack = [[state.tree, null]];
    while (stack.length) {
      const [node, parent] = stack.pop();
      state.byId[node.id] = node;
      state.parentOf[node.id] = parent;
      (node.children || []).forEach((child) => stack.push([child, node.id]));
    }
  }

  function setTree(tree) {
    state.tree = tree;
    reindex();
    if (!state.byId[state.selected]) state.selected = tree.id;
    state.open.add(tree.id);
    store(STORE_KEY, JSON.stringify(tree));
    render();
  }

  function persistOpen() {
    store(OPEN_KEY, JSON.stringify([...state.open]));
  }

  function select(id) {
    state.selected = id;
    for (let parent = state.parentOf[id]; parent; parent = state.parentOf[parent]) state.open.add(parent);
    if (isFolder(state.byId[id])) state.open.add(id);
    persistOpen();
    render();
  }

  function render() {
    renderTree();
    renderContent();
    $("#stats").textContent = (() => {
      const total = countAll(state.tree) - 1;
      const notes = notesIn(state.tree);
      return `${plural(total - notes, "carpeta", "carpetas")} · ${plural(notes, "nota", "notas")}`;
    })();
    const folder = state.byId[currentFolderId()];
    const target = $("#target");
    target.replaceChildren(document.createTextNode("Se crea en: "), el("strong", "", folder.name));
  }

  // ---------- Árbol lateral ----------

  function renderTree() {
    const box = $("#tree");
    if (state.query) return renderResults(box);
    const list = el("ul", "tree-list");
    list.append(buildNode(state.tree, true));
    box.replaceChildren(list);
  }

  function buildNode(node, isRoot = false) {
    const item = el("li");
    const row = el("div", "row" + (node.id === state.selected ? " selected" : ""));
    const folder = isFolder(node);
    const expanded = folder && state.open.has(node.id);

    if (folder && node.children.length && !isRoot) {
      const toggle = el("button", "toggle" + (expanded ? " open" : ""));
      toggle.type = "button";
      toggle.setAttribute("aria-label", `${expanded ? "Contraer" : "Expandir"} ${node.name}`);
      toggle.setAttribute("aria-expanded", String(expanded));
      toggle.append(icon("chevron"));
      toggle.addEventListener("click", () => {
        if (state.open.has(node.id)) state.open.delete(node.id);
        else state.open.add(node.id);
        persistOpen();
        renderTree();
      });
      row.append(toggle);
    } else {
      row.append(el("span", "spacer"));
    }

    const main = el("button", "row-main");
    main.type = "button";
    if (node.id === state.selected) main.setAttribute("aria-current", "true");
    main.append(icon(node.kind, node.kind), el("span", "row-name", node.name));
    if (folder && node.children.length) main.append(el("span", "badge", String(notesIn(node))));
    main.addEventListener("click", () => select(node.id));
    row.append(main);

    if (!isRoot) {
      row.draggable = true;
      row.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/plain", node.id);
        event.dataTransfer.effectAllowed = "move";
      });
    }
    if (folder) {
      row.addEventListener("dragover", (event) => {
        event.preventDefault();
        row.classList.add("drop");
      });
      row.addEventListener("dragleave", () => row.classList.remove("drop"));
      row.addEventListener("drop", async (event) => {
        event.preventDefault();
        row.classList.remove("drop");
        const id = event.dataTransfer.getData("text/plain");
        if (!id || id === node.id || !state.byId[id]) return;
        const data = await run("move", { id, parent_id: node.id });
        if (data) {
          state.open.add(node.id);
          persistOpen();
          renderTree();
          toast(`Movido a «${node.name}»`);
        }
      });
    }

    item.append(row);
    if (expanded && node.children.length) {
      const children = el("ul");
      node.children.forEach((child) => children.append(buildNode(child)));
      item.append(children);
    }
    return item;
  }

  function renderResults(box) {
    const nodes = [el("p", "results-title", state.results.length
      ? plural(state.results.length, "resultado", "resultados")
      : `Sin resultados para «${state.query}»`)];
    state.results.forEach((result) => {
      const entry = el("button", "result");
      entry.type = "button";
      const head = el("div", "result-head");
      head.append(icon(result.kind, result.kind), el("span", "", result.name));
      entry.append(head, el("div", "result-sub", result.snippet || result.location));
      if (result.snippet) entry.append(el("div", "result-sub", `en ${result.location}`));
      entry.addEventListener("click", () => {
        $("#search").value = "";
        state.query = "";
        state.results = [];
        select(result.id);
      });
      nodes.push(entry);
    });
    box.replaceChildren(...nodes);
  }

  let searchTimer;
  $("#search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    const value = event.target.value.trim();
    searchTimer = setTimeout(async () => {
      state.query = value;
      if (!value) {
        state.results = [];
        return renderTree();
      }
      try {
        state.results = (await call("/api/search", { tree: state.tree, q: value })).results;
      } catch (error) {
        state.results = [];
        toast(offline(error) ? "No hay conexión con el servidor" : error.message, true);
      }
      renderTree();
    }, 250);
  });

  // ---------- Panel principal ----------

  function renderContent() {
    const node = state.byId[state.selected];
    const head = el("header", "content-head");

    const crumbs = el("nav", "crumbs");
    crumbs.setAttribute("aria-label", "Ubicación");
    const path = pathOf(node.id);
    path.forEach((part, index) => {
      if (index === path.length - 1) {
        crumbs.append(el("strong", "crumb-current", part.name));
      } else {
        crumbs.append(button(part.name, "crumb", () => select(part.id)), icon("chevron", "sep"));
      }
    });

    const actions = el("div", "head-actions");
    actions.append(button("Renombrar", "ghost small", renameSelected));
    if (node.id !== state.tree.id) {
      actions.append(button("Mover a…", "ghost small", moveSelected));
      actions.append(button("Eliminar", "danger-ghost small", deleteSelected));
    }
    head.append(crumbs, actions);

    $("#content").replaceChildren(head, isFolder(node) ? folderView(node) : noteView(node));
  }

  function folderView(folder) {
    const view = el("section", "folder-view");
    if (!folder.children.length) {
      const empty = el("div", "empty");
      empty.append(
        el("p", "", "Esta carpeta está vacía. Crea una nota o una carpeta, o arrastra aquí elementos desde la izquierda."),
        (() => {
          const actions = el("div", "empty-actions");
          actions.append(
            button("Nueva nota aquí", "primary", () => createItem("note")),
            button("Nueva carpeta aquí", "ghost", () => createItem("folder")),
          );
          return actions;
        })(),
      );
      view.append(empty);
      return view;
    }
    const list = el("div", "item-list");
    folder.children.forEach((child) => {
      const item = el("button", "item");
      item.type = "button";
      const text = el("div", "item-text");
      const meta = isFolder(child)
        ? plural(notesIn(child), "nota", "notas")
        : (child.content.split("\n").find((line) => line.trim()) || "Nota vacía");
      text.append(el("div", "item-name", child.name), el("div", "item-meta", meta));
      item.append(icon(child.kind, child.kind), text);
      item.addEventListener("click", () => select(child.id));
      list.append(item);
    });
    view.append(list);
    return view;
  }

  function noteView(note) {
    const view = el("section", "note-view");
    const editor = el("textarea", "editor");
    editor.value = note.content;
    editor.maxLength = MAX_CONTENT;
    editor.placeholder = "Escribe aquí…";
    editor.setAttribute("aria-label", `Contenido de ${note.name}`);

    const foot = el("div", "note-foot");
    statusEl = el("span", "status", "Guardado");
    const words = el("span", "", wordCount(note.content));
    foot.append(statusEl, words);

    editor.addEventListener("input", () => {
      note.content = editor.value;
      store(STORE_KEY, JSON.stringify(state.tree));
      words.textContent = wordCount(editor.value);
      setStatus("Guardando…");
      clearTimeout(state.saveTimer);
      state.saveId = note.id;
      state.saveTimer = setTimeout(doSave, 600);
    });

    view.append(editor, foot);
    return view;
  }

  function wordCount(text) {
    const count = text.trim() ? text.trim().split(/\s+/).length : 0;
    return plural(count, "palabra", "palabras");
  }

  function setStatus(text, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = "status" + (isError ? " error" : "");
  }

  async function doSave() {
    const id = state.saveId;
    state.saveTimer = null;
    const note = state.byId[id];
    if (!note) return;
    try {
      await call("/api/save", { tree: state.tree, id, content: note.content });
      setStatus("Guardado");
    } catch (error) {
      if (offline(error)) setStatus("Guardado en este navegador");
      else setStatus(error.message, true);
    }
  }

  async function flushSave() {
    if (state.saveTimer === null) return;
    clearTimeout(state.saveTimer);
    await doSave();
  }

  // ---------- Diálogos ----------

  function openDialog({ title, body, ok = "Aceptar", danger = false, result = () => true }) {
    return new Promise((resolve) => {
      const dialog = $("#dialog");
      const form = dialog.querySelector("form");
      const cancel = button("Cancelar", "ghost", () => dialog.close("cancel"));
      const accept = el("button", danger ? "danger" : "primary", ok);
      accept.type = "submit";
      accept.value = "ok";
      const actions = el("div", "dialog-actions");
      actions.append(cancel, accept);
      form.replaceChildren(el("h2", "", title), ...body, actions);
      dialog.returnValue = "";
      dialog.onclose = () => resolve(dialog.returnValue === "ok" ? result() : null);
      dialog.showModal();
      const input = form.querySelector("input[type=text]");
      if (input) {
        input.focus();
        input.select();
      }
    });
  }

  function askName(title, value, ok) {
    const input = el("input");
    input.type = "text";
    input.value = value;
    input.required = true;
    input.maxLength = 80;
    input.setAttribute("aria-label", "Nombre");
    return openDialog({ title, body: [input], ok, result: () => input.value });
  }

  function pickFolder(title, excludeId, currentId) {
    const list = el("div", "pick-list");
    (function walk(node, depth) {
      if (!isFolder(node) || node.id === excludeId) return;
      const label = el("label", "pick");
      label.style.paddingLeft = `${8 + depth * 18}px`;
      const radio = el("input");
      radio.type = "radio";
      radio.name = "folder";
      radio.value = node.id;
      radio.checked = node.id === currentId;
      label.append(radio, icon("folder", "folder"), el("span", "", node.name));
      list.append(label);
      node.children.forEach((child) => walk(child, depth + 1));
    })(state.tree, 0);
    return openDialog({
      title,
      body: [list],
      ok: "Mover aquí",
      result: () => (list.querySelector("input:checked") || {}).value || null,
    });
  }

  // ---------- Acciones ----------

  async function createItem(kind) {
    const parentId = currentFolderId();
    const isNote = kind === "note";
    const name = await askName(
      isNote ? "Nueva nota" : "Nueva carpeta",
      uniqueName(isNote ? "Nota sin título" : "Nueva carpeta", parentId),
      "Crear",
    );
    if (name === null) return;
    const data = await run("create", { parent_id: parentId, kind, name });
    if (!data) return;
    state.open.add(parentId);
    select(data.id);
    if (isNote) {
      const editor = $(".editor");
      if (editor) editor.focus();
    }
  }

  async function renameSelected() {
    const node = state.byId[state.selected];
    const name = await askName(`Renombrar «${node.name}»`, node.name, "Guardar");
    if (name === null || name === node.name) return;
    const data = await run("rename", { id: node.id, name });
    if (data) toast("Nombre actualizado");
  }

  async function moveSelected() {
    const node = state.byId[state.selected];
    const target = await pickFolder(`Mover «${node.name}» a…`, isFolder(node) ? node.id : null, state.parentOf[node.id]);
    if (!target || target === state.parentOf[node.id]) return;
    const data = await run("move", { id: node.id, parent_id: target });
    if (data) {
      state.open.add(target);
      persistOpen();
      select(node.id);
      toast(`Movido a «${state.byId[target].name}»`);
    }
  }

  async function deleteSelected() {
    const node = state.byId[state.selected];
    const inside = countAll(node) - 1;
    const message = isFolder(node) && inside
      ? `Se eliminará la carpeta «${node.name}» y ${plural(inside, "elemento", "elementos")} que contiene. No se puede deshacer.`
      : `Se eliminará «${node.name}». No se puede deshacer.`;
    const confirmed = await openDialog({
      title: "¿Eliminar?",
      body: [el("p", "", message)],
      ok: "Eliminar",
      danger: true,
    });
    if (!confirmed) return;
    const parent = state.parentOf[node.id];
    const data = await run("delete", { id: node.id });
    if (data) {
      select(parent);
      toast("Eliminado");
    }
  }

  $("#new-note").addEventListener("click", () => createItem("note"));
  $("#new-folder").addEventListener("click", () => createItem("folder"));

  // ---------- Arranque ----------

  async function start() {
    let tree = null;
    const saved = read(STORE_KEY);
    if (saved) {
      try {
        tree = (await call("/api/load", { tree: JSON.parse(saved) })).tree;
      } catch (error) {
        if (offline(error)) {
          try { tree = JSON.parse(saved); } catch (parseError) { tree = null; }
        } else {
          store(BACKUP_KEY, saved);
          toast("No se pudo leer tu cuaderno guardado; se guardó una copia y se cargó el ejemplo", true);
        }
      }
    }
    if (!tree) tree = (await call("/api/seed")).tree;

    try { state.open = new Set(JSON.parse(read(OPEN_KEY) || "[]")); } catch (error) { state.open = new Set(); }
    state.tree = tree;
    reindex();
    if (!saved) Object.keys(state.byId).forEach((id) => isFolder(state.byId[id]) && state.open.add(id));
    const welcome = Object.values(state.byId).find((node) => node.name === "Bienvenida");
    state.selected = welcome ? welcome.id : tree.id;
    setTree(tree);
  }

  start().catch((error) => {
    $("#content").replaceChildren(el("p", "", offline(error)
      ? "No se pudo conectar con el servidor. Revisa tu conexión y recarga la página."
      : error.message));
  });
})();
