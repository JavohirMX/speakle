// Keeps a partner's local time ("their time 14:05 (UTC+9)") current while the page stays open.
// The server renders the first value; if Intl is unavailable the server text just stays.
(function () {
  function fmt(tz) {
    var now = new Date();
    var t = new Intl.DateTimeFormat('en-GB', {timeZone: tz, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).format(now);
    var off = new Intl.DateTimeFormat('en-US', {timeZone: tz, timeZoneName: 'shortOffset'}).formatToParts(now)
      .filter(function (p) { return p.type === 'timeZoneName'; })[0];
    off = off ? off.value.replace('GMT', 'UTC') : '';
    if (off === 'UTC') off = 'UTC+0';
    return t + (off ? ' (' + off + ')' : '');
  }
  function tick() {
    document.querySelectorAll('.partner-time[data-tz]').forEach(function (el) {
      try { el.textContent = 'their time ' + fmt(el.getAttribute('data-tz')); } catch (e) { /* keep server text */ }
    });
  }
  tick();
  setInterval(tick, 30000);
})();
