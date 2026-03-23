// Keep preload minimal for security. UI talks to Flask via HTTP.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("HREC", {
  version: "1.0.0",
});

