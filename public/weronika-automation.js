/**
 * Weronika Unified Automation dispatcher
 * - Intercepts chat submit, tries universal intent before brain
 * - Handles spotify/youtube/telegram/whatsapp/instagram/gmail/calendar/drive
 * - Sends private text to local Ollama when needed (never cloud unless allowed)
 */
export function setupAutomation({ getConversation, showBanner, showError, speak, callBrain }) {
  const btn = document.getElementById('sendChatBtn');
  const input = document.getElementById('chatInput');
  if (!input) return;

  const AGENT_BASES = ['', '/api/weronika-agent', 'http://127.0.0.1:8765'];
  async function postUniversal(message) {
    for (const base of AGENT_BASES) {
      try {
        const url = `${base}/api/automation/universal`;
        const res = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message})});
        if (res.ok) {
          const data = await res.json();
          if (data.ok) return data;
          // if backend says unknown intent, return null to fallback to brain chat
          if (data.error && /could not understand/i.test(data.error)) return null;
          return data;
        }
      } catch {}
    }
    return null;
  }

  async function handleIfAutomation(text, options={}) {
    const trimmed = text.trim();
    if (!trimmed || trimmed.length < 3) return false;
    // Quick heuristics to avoid calling backend for plain chat
    const low = trimmed.toLowerCase();
    const automationHints = [
      'telegram','whatsapp','whats app','instagram','insta','youtube','yt','spotify','gmail','google calendar','gcal','drive','inbox','mail','email',
      'plan my day','plan today','organize drive','organise drive','recognize me','who am i','check my inbox','check inbox','read my mail',
      'play the','play a','play sahiba','play barsaat','barsaat','believer','beliver','techno gamer','gta 5',
      'make a comment','comment there','open telegram','open whatsapp','send message to','message to boss','on leave',
      'send him','dm ','tell him','tell her','open youtube','play song','open spotify'
    ];
    const looksLikeAutomation = automationHints.some(k=> low.includes(k)) || /\b(open|play|send|message|dm|comment|watch|organize|plan|recognize)\b/.test(low);
    if (!looksLikeAutomation && trimmed.split(/\s+/).length < 4) return false;

    let result = null;
    try { result = await postUniversal(trimmed); } catch {}
    if (!result || !result.ok) return false;

    // We have a valid automation intent
    const intent = result.intent;
    const spec = result.spec;
    const mode = result.mode;
    let banner = result.message || result.result?.message || '';
    if (!banner) {
      if (intent) {
        const p = intent.payload||{};
        banner = `Weronika: I'll open ${intent.app} for "${p.query||p.message||p.target||p.comment||trimmed}"`;
        if (spec && spec.url) banner += ` → ${spec.url}`;
      } else {
        banner = `Automation: ${JSON.stringify(result).slice(0,400)}`;
      }
    }
    // If native app check available, hint
    if (result.native_installed) banner += " (desktop app installed — I’ll prefer it, otherwise web tab)";
    // Show and speak
    showBanner(banner);
    // If spec needs new tab, open it
    if (spec && spec.url) {
      if (window.WeronikaSameBrowser && window.WeronikaSameBrowser.openAndDrive) {
        window.WeronikaSameBrowser.openAndDrive(spec);
      } else {
        const win = window.open(spec.url, '_blank');
        if (!win) showError('Popup blocked. Please allow popups: ' + spec.url);
      }
    }
    // If result has human-readable answer (like day plan), show it
    if (result.result && (result.result.plan || result.result.recognition)) {
      const txt = result.result.plan || result.result.recognition;
      showBanner(txt);
      if (speak) speak(txt.slice(0,600));
    } else if (typeof speak === 'function') {
      speak(banner.slice(0,400));
    }
    // Log to chat
    try {
      const chatLog = document.getElementById('chatLog');
      if (chatLog) {
        const userDiv = document.createElement('div');
        userDiv.className='chat-message user';
        userDiv.textContent = `You: ${trimmed}`;
        chatLog.appendChild(userDiv);
        const botDiv = document.createElement('div');
        botDiv.className='chat-message assistant';
        botDiv.textContent = banner;
        chatLog.appendChild(botDiv);
        chatLog.scrollTop = chatLog.scrollHeight;
      }
    } catch {}
    // Persist via memory helper
    try { window.WeronikaMemory?.appendTurn('user', trimmed); window.WeronikaMemory?.appendTurn('assistant', banner); } catch {}

    return true; // consumed
  }

  // Monkey-patch global chat handler? Instead, add capture on button/form
  // We'll intercept the existing sendChat handler by wrapping the input's Enter and button click at capture phase
  function installInterceptor() {
    const form = input.closest('form') || document.getElementById('chatForm');
    if (form) {
      form.addEventListener('submit', async (e)=>{
        const val = input.value ? input.value.trim() : '';
        if (!val) return;
        // Don't preventDefault yet; let automation check first
        // Use capture to run before default
      }, true);
    }
    // Add click interceptor on sendChatBtn that checks automation first
    if (btn) {
      btn.addEventListener('click', async (e)=>{
        const val = input.value ? input.value.trim() : '';
        if (!val) return;
        // Try automation quickly; if it consumes, prevent the default brain call duplicate
        // We set a flag so the brain handler can skip
        try {
          const consumed = await handleIfAutomation(val);
          if (consumed) {
            input.value='';
            e.stopImmediatePropagation();
            e.preventDefault();
          }
        } catch {}
      }, true);
    }
    input.addEventListener('keydown', async (e)=>{
      if (e.key === 'Enter' && !e.shiftKey) {
        const val = input.value ? input.value.trim() : '';
        if (!val) return;
        // quick check, but don't block typing
        // We'll do async check with small delay
      }
    });
  }

  installInterceptor();

  // Also expose global for manual trigger: Weronika will call backend for every message via NDJSON, so even if our interceptor misses,
  // the python _ask handler already returns automation hint. This helper ensures frontend opens tabs for those.
  // Listen for NDJSON action events on chatLog mutations? Simpler: when chat gets a new message containing a URL, hint to open
  window.WeronikaAutomation = { handleIfAutomation, postUniversal };
  return { handleIfAutomation, postUniversal };
}
