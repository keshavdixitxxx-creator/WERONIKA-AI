/**
 * Weronika Persistent Memory
 * - Conversation survives shutdown/refresh
 * - Syncs between localStorage and backend disk file
 */
export function setupMemory({ getConversation, setConversation, getAddressName }) {
  const AGENT_BASE = location.port === '8765' ? '' : '/api/weronika-agent';
  // also try same-origin direct
  const CANDIDATES = ['/api/memory/history', '/api/weronika-agent/api/memory/history', 'http://127.0.0.1:8765/api/memory/history'];
  const LS_KEY = 'weronika.conversationHistory.v2';
  const LS_ADDR = 'weronika_address_name';

  async function loadFromDisk() {
    for (const url of CANDIDATES) {
      try {
        const res = await fetch(url, { cache:'no-store' });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.history) && data.history.length) {
            // merge with local
            try {
              const local = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
              const merged = [...local];
              // dedup: prefer disk if longer
              if (data.history.length >= local.length) {
                localStorage.setItem(LS_KEY, JSON.stringify(data.history.slice(-40)));
                if (typeof setConversation === 'function') setConversation(data.history);
                return data.history;
              }
            } catch {}
            localStorage.setItem(LS_KEY, JSON.stringify(data.history.slice(-40)));
            if (typeof setConversation === 'function') setConversation(data.history);
            return data.history;
          }
          if (data.history) {
            if (typeof setConversation === 'function') setConversation(data.history);
            return data.history;
          }
        }
      } catch {}
    }
    // fallback localStorage
    try {
      const local = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      if (Array.isArray(local) && local.length) {
        if (typeof setConversation === 'function') setConversation(local);
        return local;
      }
    } catch {}
    return [];
  }

  async function saveToDisk(history) {
    const payload = { history: (history || getConversation?.() || []).slice(-40) };
    // local
    try { localStorage.setItem(LS_KEY, JSON.stringify(payload.history)); } catch {}
    // backend
    for (const url of CANDIDATES) {
      try {
        const postUrl = url.replace('/history','/history');
        await fetch(postUrl, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        break;
      } catch {}
    }
  }

  async function appendTurn(role, content) {
    try {
      const hist = getConversation?.() || JSON.parse(localStorage.getItem(LS_KEY)||'[]');
      hist.push({ role, content });
      if (hist.length > 40) hist.splice(0, hist.length-40);
      if (typeof setConversation === 'function') setConversation(hist);
      await saveToDisk(hist);
    } catch {}
  }

  // Hook into page's conversationHistory global if exists
  function wireGlobal() {
    if (!window.__weronikaMemoryWired) {
      window.__weronikaMemoryWired = true;
      // periodic sync
      setInterval(()=> {
        try {
          const hist = window.conversationHistory || getConversation?.() || [];
          if (hist && hist.length) localStorage.setItem(LS_KEY, JSON.stringify(hist.slice(-40)));
        } catch {}
      }, 3000);
    }
  }

  // Expose
  window.WeronikaMemory = { loadFromDisk, saveToDisk, appendTurn, LS_KEY };

  // Auto-load on next tick so page's conversationHistory is initialized
  setTimeout(async ()=>{
    await loadFromDisk();
    wireGlobal();
  }, 600);

  return { loadFromDisk, saveToDisk, appendTurn };
}
