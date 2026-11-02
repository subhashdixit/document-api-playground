import {
  validateDocument,
  validateRows,
  upsert,
  endpointURL,
} from "./engine.js";
import { $, announce, download } from "./ui.js";
const KEY = "document-playground.v1";
let local = [],
  rows = [],
  editing = null,
  connection = null;
function render() {
  const visible = rows.filter((r) =>
    JSON.stringify(r).toLowerCase().includes($("filter").value.toLowerCase()),
  );
  $("documents").replaceChildren();
  for (const row of visible) {
    const section = document.createElement("section"),
      pre = document.createElement("pre"),
      title = document.createElement("h3");
    title.textContent = row.id;
    pre.textContent = JSON.stringify(row.document, null, 2);
    section.append(title, pre);
    for (const action of ["Edit", "Delete"]) {
      const button = document.createElement("button");
      button.textContent = action;
      button.addEventListener("click", async () => {
        try {
          if (action === "Edit") {
            editing = row.id;
            $("document").value = JSON.stringify(row.document, null, 2);
            $("save").textContent = "Update document";
          } else if (
            window.confirm("Delete this document from the active store?")
          ) {
            if (connection) {
              await request("DELETE", "/" + row.id);
              await refresh();
            } else persist(local.filter((r) => r.id !== row.id));
            if (editing === row.id) cancel();
            announce("Document deleted from the active store.");
          }
        } catch (error) {
          announce(error.message);
        }
      });
      section.append(button);
    }
    $("documents").append(section);
  }
  $("mode").textContent = connection
    ? "Connected MongoDB API · owner-controlled collection"
    : "Local demo store · browser JSON, not MongoDB";
}
function persist(next) {
  next = validateRows(next);
  localStorage.setItem(KEY, JSON.stringify(next));
  local = next;
  rows = local;
  render();
}
function cancel() {
  editing = null;
  $("save").textContent = "Create document";
}
async function request(method, path = "", body) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(connection.origin + "/api/documents" + path, {
      method,
      headers: {
        Authorization: "Bearer " + connection.token,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      credentials: "omit",
      signal: controller.signal,
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || "Backend request failed.");
    return result;
  } finally {
    clearTimeout(timer);
  }
}
async function refresh() {
  rows = validateRows((await request("GET")).documents);
  render();
}
$("save").addEventListener("click", async () => {
  try {
    const document = validateDocument(JSON.parse($("document").value));
    if (connection) {
      await request(editing ? "PUT" : "POST", editing ? "/" + editing : "", {
        document,
      });
      await refresh();
    } else persist(upsert(local, editing || crypto.randomUUID(), document));
    cancel();
    announce("Document saved to the labelled active store.");
  } catch (error) {
    announce("Not saved: " + error.message);
  }
});
$("cancel").addEventListener("click", cancel);
$("filter").addEventListener("input", render);
$("export").addEventListener("click", () =>
  download(
    "local-documents.json",
    JSON.stringify({ schema: 1, documents: local }, null, 2),
    "application/json",
  ),
);
$("import").addEventListener("change", async (e) => {
  try {
    if (connection)
      throw Error("Disconnect first: backups are local-mode only.");
    const f = e.target.files[0];
    if (!f || f.size > 16 * 1024 * 1024)
      throw Error("Use a backup up to 16 MiB.");
    const value = JSON.parse(await f.text());
    if (value.schema !== 1) throw Error("Unsupported backup format.");
    const next = validateRows(value.documents);
    if (window.confirm("Replace local documents with this validated backup?")) {
      persist(next);
      cancel();
      announce("Imported local backup.");
    }
  } catch (error) {
    announce("Import rejected: " + error.message);
  }
});
$("demo").addEventListener("click", () => {
  try {
    if (connection) throw Error("Disconnect before loading local demo data.");
    if (
      local.length &&
      !window.confirm("Replace local documents with fictional examples?")
    )
      return;
    persist([
      {
        id: "demo-1",
        document: {
          name: "Example Learner",
          city: "Kolkata",
          course: "Python",
        },
      },
      {
        id: "demo-2",
        document: {
          name: "Fictional Analyst",
          city: "Pune",
          skills: ["SQL", "Python"],
        },
      },
    ]);
    announce("Fictional browser documents loaded.");
  } catch (error) {
    announce(error.message);
  }
});
$("connect").addEventListener("click", async () => {
  try {
    const origin = endpointURL($("endpoint").value);
    const token = $("token").value;
    if (token.length < 32)
      throw Error("Use your backend's access token (at least 32 characters).");
    connection = { origin, token };
    await refresh();
    $("token").value = "";
    cancel();
    announce(
      "Connected to your explicit backend. CRUD now affects its configured MongoDB collection.",
    );
  } catch (error) {
    connection = null;
    rows = local;
    render();
    announce("Connection failed: " + error.message);
  }
});
$("disconnect").addEventListener("click", () => {
  connection = null;
  rows = local;
  $("token").value = "";
  cancel();
  render();
  announce(
    "Returned to local mode; the backend token was discarded from app state.",
  );
});
try {
  const data = localStorage.getItem(KEY);
  if (data) local = validateRows(JSON.parse(data));
} catch (error) {
  announce("Stored local data could not be read: " + error.message);
}
rows = local;
render();
