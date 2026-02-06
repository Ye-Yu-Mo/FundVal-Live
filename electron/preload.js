// Preload script for Electron
// This script runs before the renderer process loads

const { contextBridge } = require('electron');

// Expose safe APIs to renderer process
contextBridge.exposeInMainWorld('electron', {
  // Add any APIs you want to expose here
});
