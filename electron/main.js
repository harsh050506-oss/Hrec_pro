const { app, BrowserWindow } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let pyProc = null;

function spawnServer() {
  const projectRoot = path.join(__dirname, "..");
  const serverPath = path.join(projectRoot, "server", "app.py");

  const env = {
    ...process.env,
    HREC_HOST: process.env.HREC_HOST || "127.0.0.1",
    HREC_PORT: process.env.HREC_PORT || "5000",
    HREC_DEBUG: process.env.HREC_DEBUG || "0",
  };

  const cmd = process.env.HREC_PYTHON || "python";
  pyProc = spawn(cmd, [serverPath], { cwd: projectRoot, env });

  pyProc.stdout.on("data", (d) => console.log(`[server] ${d}`));
  pyProc.stderr.on("data", (d) => console.error(`[server] ${d}`));
  pyProc.on("close", (code) => console.log(`Server exited (${code})`));
}

async function waitForHealth(url, timeoutMs = 12000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 350));
  }
  return false;
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 780,
    backgroundColor: "#0b1220",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
    },
  });

  const host = process.env.HREC_HOST || "127.0.0.1";
  const port = process.env.HREC_PORT || "5000";
  const baseUrl = `http://${host}:${port}`;
  const ok = await waitForHealth(`${baseUrl}/api/health`);
  if (!ok) console.warn("Server health check timed out; loading anyway.");

  await win.loadURL(`${baseUrl}/`);
}

app.whenReady().then(async () => {
  spawnServer();
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (pyProc) {
    try {
      pyProc.kill();
    } catch {}
    pyProc = null;
  }
});

