/* Recheck: plain-language replay of the recorded run. Animates existing evidence only; starts nothing. */
(function () {
  'use strict';
  const root = document.getElementById('story');
  if (!root) return;
  const steps = [...root.querySelectorAll('.story-step')];
  const button = document.getElementById('story-play');
  const tally = id => fetch('/recorded-state.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
  tally().then(state => {
    if (!state || !Array.isArray(state.stages)) return;
    state.stages.forEach(stage => {
      const node = document.getElementById('story-score-' + stage.id);
      if (!node || !Array.isArray(stage.checks) || !stage.checks.length) return;
      const pass = stage.checks.filter(c => c.passed === true && c.expected === c.actual).length;
      node.dataset.pass = pass; node.dataset.total = stage.checks.length;
      node.textContent = pass + '/' + stage.checks.length + ' tests pass';
    });
  });
  function count(node) {
    if (!node || !node.dataset.total) return;
    const pass = Number(node.dataset.pass), total = Number(node.dataset.total);
    let n = 0;
    const timer = setInterval(() => { n = Math.min(n + 1, pass); node.textContent = n + '/' + total + ' tests pass'; if (n >= pass) clearInterval(timer); }, 60);
  }
  let timers = [];
  button.addEventListener('click', () => {
    timers.forEach(clearTimeout); timers = [];
    root.classList.add('is-playing');
    steps.forEach(step => step.classList.remove('is-on'));
    steps.forEach((step, i) => timers.push(setTimeout(() => {
      step.classList.add('is-on');
      count(step.querySelector('.story-score'));
      if (i === steps.length - 1) timers.push(setTimeout(() => root.classList.remove('is-playing'), 2500));
    }, 400 + i * 2600)));
    button.textContent = '↻ Replay';
  });
})();
