/**
 * Weronika Same-Browser Automation
 * Replaces the "chrome test" (playwright separate profile).
 * This runs in the SAME browser/profile where Weronika lives.
 * - Opens targets in new tabs via window.open (keeps login cookies)
 * - Drives pages via postMessage helpers + DOM queries
 * - If CDP endpoint (9222) is available, backend can also drive same browser via connect_over_cdp
 */

export function setupSameBrowser({ showBanner, showError, speak }) {
  const STATUS_URLS = ['/api/same-browser/status','/api/automation/same-browser','/api/weronika-agent/api/same-browser/status','http://127.0.0.1:8765/api/same-browser/status','http://127.0.0.1:8765/api/automation/same-browser'];

  async function getStatus() {
    for (const u of STATUS_URLS) {
      try { const r = await fetch(u,{cache:'no-store'}); if (r.ok) { const j=await r.json(); if (j.ok) return j; } } catch {}
    }
    return { mode:'frontend', message:'Frontend same-tab mode is active. No extra install needed.' };
  }

  function openAndDrive(spec) {
    if (!spec || !spec.url) { showError('No URL to open'); return; }
    // Open in new tab — user stays logged in via same profile
    const win = window.open(spec.url, '_blank', 'noopener');
    if (!win) {
      showError('Popup blocked. Allow popups for Weronika, then try again. Direct link: ' + spec.url);
      return;
    }
    showBanner(`Opened ${spec.url} in a new tab. Weronika will guide the next steps there. Check that tab — sign in once if the site asks.`);
    // Hint: if spec has steps with evaluate code, we can't directly run cross-origin JS due to browser security.
    // Instead we give user clear next-step instructions and, when CDP endpoint is available, backend can finish it.
    // For spotify/youtube/telegram/whatsapp we at least get the right page with search prefilled via URL:
    if (spec.steps && spec.steps.length) {
      console.log('[weronika same-browser] spec steps:', spec.steps);
    }
    return win;
  }

  // Global handler: backend can return {spec, mode:'same-browser-frontend'} and frontend will open it
  window.addEventListener('weronika:automation-spec', (e)=>{
    const spec = e.detail?.spec || e.detail;
    if (spec) openAndDrive(spec);
  });

  // Intercept NDJSON action events that contain spec
  // Monkey-patch fetch brain path? Simpler: expose helper for page to call
  window.WeronikaSameBrowser = {
    openAndDrive,
    getStatus,
    handleIntentResponse: async (data) => {
      if (data && data.spec && data.spec.url) {
        openAndDrive(data.spec);
        return true;
      }
      if (data && data.result && data.result.spec) {
        openAndDrive(data.result.spec);
        return true;
      }
      return false;
    }
  };

  // UI hint
  getStatus().then(s=>{
    const el = document.getElementById('sameBrowserStatus');
    if (el) el.textContent = s.message || s.mode || 'Same-browser frontend mode active.';
  });

  return { openAndDrive, getStatus };
}
