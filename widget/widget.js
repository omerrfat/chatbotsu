/* Embeddable chat widget.
   <script src="https://YOUR-HOST/widget/widget.js" data-tenant="demo-bakery" defer></script>
   Optional: data-api="https://YOUR-HOST" (defaults to the script's own origin). */
(function () {
  var script = document.currentScript || document.querySelector('script[data-tenant]');
  var tenant = script.getAttribute('data-tenant');
  var api = (script.getAttribute('data-api') || new URL(script.src).origin).replace(/\/$/, '');
  var storeKey = 'chatbot:' + tenant;
  var convId = null;
  try { convId = sessionStorage.getItem(storeKey); } catch (e) {}

  var css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = new URL('widget.css', script.src).href;
  document.head.appendChild(css);

  var root = document.createElement('div');
  root.className = 'cbw-root';
  root.innerHTML =
    '<button class="cbw-fab" aria-label="Open chat">' +
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></button>' +
    '<section class="cbw-panel" role="dialog" aria-label="Chat" hidden>' +
    '<header class="cbw-head"><span class="cbw-title"></span><button class="cbw-close" aria-label="Close chat">&times;</button></header>' +
    '<div class="cbw-log" aria-live="polite"></div>' +
    '<form class="cbw-form"><input class="cbw-input" maxlength="1000" placeholder="Type your message..." autocomplete="off" aria-label="Message">' +
    '<button class="cbw-send" type="submit">Send</button></form>' +
    '<div class="cbw-foot">AI assistant. Your messages may be stored to help the business reply.</div></section>';
  document.body.appendChild(root);

  var fab = root.querySelector('.cbw-fab'), panel = root.querySelector('.cbw-panel'),
      log = root.querySelector('.cbw-log'), form = root.querySelector('.cbw-form'),
      input = root.querySelector('.cbw-input'), send = root.querySelector('.cbw-send');

  function add(role, text) {
    var d = document.createElement('div');
    d.className = 'cbw-msg cbw-' + role;
    d.textContent = text;          // textContent: never render model output as HTML
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  fetch(api + '/tenants/' + encodeURIComponent(tenant) + '/public')
    .then(function (r) { return r.json(); })
    .then(function (c) {
      root.querySelector('.cbw-title').textContent = c.business_name;
      root.style.setProperty('--cbw-color', c.brand_color);
      add('bot', c.greeting);
    })
    .catch(function () { add('bot', 'Chat is unavailable right now.'); });

  function toggle(open) {
    panel.hidden = !open;
    fab.hidden = open;
    if (open) input.focus();
  }
  fab.addEventListener('click', function () { toggle(true); });
  root.querySelector('.cbw-close').addEventListener('click', function () { toggle(false); });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    add('user', text);
    var typing = add('bot', '...');
    typing.classList.add('cbw-typing');
    send.disabled = true;
    fetch(api + '/chat/' + encodeURIComponent(tenant), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, conversation_id: convId })
    })
      .then(function (r) {
        if (r.status === 429) throw new Error('Too many messages. Please wait a moment.');
        if (!r.ok) throw new Error('Something went wrong. Please try again.');
        return r.json();
      })
      .then(function (d) {
        convId = d.conversation_id;
        try { sessionStorage.setItem(storeKey, convId); } catch (e) {}
        typing.remove();
        add('bot', d.reply);
      })
      .catch(function (err) { typing.remove(); add('bot', err.message || 'Connection problem.'); })
      .then(function () { send.disabled = false; input.focus(); });
  });
})();
