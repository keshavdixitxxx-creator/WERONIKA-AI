/**
 * Weronika Google Connector UI
 * - Gmail / Calendar / Drive connect via OAuth
 * - Plan my day, recognize me, organize drive, storage etc
 * - Works with same-browser backend (no separate chrome test)
 */
export function setupGooglePanel({ showError, showBanner, speak, logVoice }) {
  const panel = document.getElementById('googlePanel');
  if (!panel) return;

  const statusEl = document.getElementById('googleStatus');
  const connectBtn = document.getElementById('googleConnectBtn');
  const disconnectBtn = document.getElementById('googleDisconnectBtn');
  const authAllBtn = document.getElementById('googleAuthAllBtn');
  const saveConfigBtn = document.getElementById('googleSaveConfigBtn');
  const clientIdInput = document.getElementById('googleClientId');
  const clientSecretInput = document.getElementById('googleClientSecret');
  const redirectInput = document.getElementById('googleRedirectUri');
  const gmailTestBtn = document.getElementById('googleGmailTest');
  const calPlanBtn = document.getElementById('googleCalPlan');
  const calRecBtn = document.getElementById('googleCalRecognize');
  const driveListBtn = document.getElementById('googleDriveList');
  const driveOrganizeBtn = document.getElementById('googleDriveOrganize');
  const driveStorageBtn = document.getElementById('googleDriveStorage');

  const AGENT = location.port === '8765' ? '' : '/api/weronika-agent';
  // When hosted, /api/weronika-agent proxies to local agent if available
  function agentUrl(path) {
    if (location.port === '8765') return path;
    // try same-origin proxy, fallback to localhost
    return path;
  }

  async function fetchJson(url, opts = {}) {
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.message || `HTTP ${res.status}`);
    return data;
  }

  async function refreshStatus() {
    try {
      const s = await fetch(agentUrl('/api/google/status'), { cache: 'no-store' }).then(r=>r.json()).catch(()=>null);
      if (!s || !s.ok) {
        statusEl.innerHTML = `Not connected yet. Add OAuth Client ID/Secret below (Google Cloud → APIs & Services → Credentials → OAuth 2.0 Client).`;
        statusEl.className = 'settings-status warn';
        return;
      }
      const con = s.connected;
      const cfg = s.has_client_config;
      let html = '';
      if (!cfg) html += '<b>Setup needed:</b> Paste your Google OAuth client ID/secret below.<br>';
      else if (!con) html += '<b>Ready to connect.</b> Click <em>Connect Google</em> to authorize Gmail/Calendar/Drive.<br>';
      else html += '<b>Connected.</b> Gmail • Calendar • Drive are live.<br>';
      if (s.scopes) html += `<small style="opacity:.7">Scopes: ${s.scopes.slice(0,120)}</small><br>`;
      html += `<small>Services: ${JSON.stringify(s.connected_services || {})}</small>`;
      statusEl.innerHTML = html;
      statusEl.className = con ? 'settings-status ok' : 'settings-status warn';
      if (connectBtn) connectBtn.disabled = !cfg;
    } catch (e) {
      statusEl.textContent = 'Google status: local agent not running. Start with python weronika_agent.py';
      statusEl.className = 'settings-status warn';
    }
  }

  async function doAuth(service='all') {
    try {
      // prefer backend that can give auth url
      const base = location.port === '8765' ? '' : '';
      let data;
      try {
        data = await fetchJson(`${base}/api/google/auth?service=${service}`);
      } catch {
        data = await fetchJson(`/api/google/auth?service=${service}`);
      }
      if (!data.ok && data.requires_config) {
        showError(data.error);
        return;
      }
      if (data.auth_url) {
        window.open(data.auth_url, '_blank','width=520,height=640');
        showBanner('Google authorization opened in a new tab. After allowing, return here and the status will update.');
        setTimeout(refreshStatus, 3000);
      } else {
        showError('No auth URL. Check OAuth config.');
      }
    } catch (e) {
      showError(e.message || 'Auth failed');
    }
  }

  if (connectBtn) connectBtn.addEventListener('click', () => doAuth('all'));
  if (authAllBtn) authAllBtn.addEventListener('click', ()=> doAuth('all'));
  if (disconnectBtn) disconnectBtn.addEventListener('click', async ()=>{
    if (!confirm('Disconnect Google? You can reconnect later.')) return;
    try {
      await fetchJson(agentUrl('/api/google/disconnect'), {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      showBanner('Google disconnected.');
      refreshStatus();
    } catch(e){ showError(e.message)}
  });
  if (saveConfigBtn) saveConfigBtn.addEventListener('click', async ()=>{
    const cid = clientIdInput?.value.trim();
    const csec = clientSecretInput?.value.trim();
    const redir = redirectInput?.value.trim();
    if (!cid || !csec) { showError('Client ID and Secret are required. Create them in Google Cloud Console.'); return; }
    try {
      await fetchJson(agentUrl('/api/google/config'), {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({client_id: cid, client_secret: csec, redirect_uri: redir || undefined})});
      showBanner('Google OAuth config saved. Now click Connect Google.');
      refreshStatus();
    } catch(e){ showError(e.message)}
  });

  async function googleAction(service, action, params={}) {
    const url = agentUrl('/api/google/action');
    try {
      const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({service, action, params})});
      const data = await res.json();
      if (!data.ok && data.requires_auth) {
        showError('Google not connected. Opening auth…');
        doAuth(service);
        return data;
      }
      return data;
    } catch(e){ showError(e.message); return {ok:false, error:e.message}}
  }

  // Gmail quick test
  if (gmailTestBtn) gmailTestBtn.addEventListener('click', async ()=>{
    const data = await googleAction('gmail','list',{q:'', max_results:5});
    if (data.ok) {
      const lines = (data.messages||[]).map(m=>`• ${(m.subject||'(no subject)')} — ${m.from||''} — ${ (m.snippet||'').slice(0,80)}`).join('\n');
      const txt = lines || 'No messages found (or inbox empty).';
      showBanner(txt);
      speak('Here are your latest emails: ' + (lines ? lines.slice(0,300) : 'nothing unread'));
    } else {
      showError(data.error||'Gmail fetch failed');
    }
  });

  if (calPlanBtn) calPlanBtn.addEventListener('click', async ()=>{
    const data = await googleAction('calendar','plan',{});
    if (data.ok) {
      showBanner(data.plan);
      speak(data.plan.slice(0,500));
    } else showError(data.error);
  });
  if (calRecBtn) calRecBtn.addEventListener('click', async ()=>{
    const data = await googleAction('calendar','recognize',{});
    if (data.ok) {
      showBanner(data.recognition);
      speak(data.recognition);
    } else showError(data.error);
  });
  if (driveListBtn) driveListBtn.addEventListener('click', async ()=>{
    const data = await googleAction('drive','list',{page_size:12});
    if (data.ok) {
      const txt = (data.files||[]).map(f=>`• ${f.name} (${f.mimeType})`).join('\n') || 'Drive empty or no files.';
      showBanner(txt);
    } else showError(data.error);
  });
  if (driveOrganizeBtn) driveOrganizeBtn.addEventListener('click', async ()=>{
    if (!confirm('Organize Drive by type? This will create Images/Videos/Docs folders and move files (dry-run first). Continue?')) return;
    let data = await googleAction('drive','organize',{dry_run:true});
    if (!data.ok) { showError(data.error); return; }
    const s = data.suggestions ? data.suggestions.join('\n') : JSON.stringify(data.groups);
    if (!confirm(`Dry-run preview:\n${s}\n\nDo the actual move?`)) { showBanner('Dry-run: '+s); return; }
    data = await googleAction('drive','organize',{dry_run:false});
    showBanner(data.ok ? (data.results||[]).join('\n').slice(0,1200) : data.error);
  });
  if (driveStorageBtn) driveStorageBtn.addEventListener('click', async ()=>{
    const data = await googleAction('drive','storage',{});
    showBanner(data.ok ? JSON.stringify(data.quota,null,2) : data.error);
  });

  refreshStatus();
  // poll occasionally when panel open
  setInterval(refreshStatus, 20000);

  // expose for global usage
  window.WeronikaGoogle = { refreshStatus, googleAction, doAuth };
}
