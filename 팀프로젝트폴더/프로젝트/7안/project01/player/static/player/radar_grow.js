/* 육각형(레이더) 그래프: 선수 팝업을 열 때 그래프가 가운데 점에서부터 각 지점까지 퍼지게 한다.
 * - 팝업이 숨겨진 상태에서 그래프가 만들어져 첫 애니메이션이 보이지 않는 문제를 보완한다.
 *   (팝업이 보이게 된 뒤에 Chart.js 의 reset() -> update() 로 처음 상태(가운데)에서 다시 퍼지게 함)
 * - 기존 best11.html 의 그래프 코드는 바꾸지 않는다. 움직임 줄이기 설정을 켠 사용자에게는 적용하지 않는다.
 */
(function () {
  'use strict';
  var modal = document.getElementById('playerModal');
  if (!modal || !window.MutationObserver) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) return;
  var DURATION = 1100;      // 퍼지는 시간(ms)
  var lastChart = null;

  function visible() { return window.getComputedStyle(modal).display !== 'none'; }

  function grow() {
    if (!window.Chart || typeof Chart.getChart !== 'function') return;
    var chart = Chart.getChart('playerRadarChart');
    if (!chart || chart === lastChart) return;       // 같은 그래프를 두 번 퍼뜨리지 않는다
    lastChart = chart;
    // 숨겨진 팝업에서 만든 그래프는 시작 좌표가 계산되지 않아(NaN) reset() 으로는 퍼지지 않는다.
    // 그래서 팝업이 보인 뒤 크기를 다시 잡고, 점수를 잠깐 0(가운데)으로 그렸다가 실제 점수로 바꿔 퍼지게 한다.
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        try {
          chart.stop();                                           // 숨겨진 상태에서 시작된(NaN) 애니메이션 멈춤
          chart.resize();
          var sets = chart.data.datasets;
          var real = sets.map(function (d) { return d.data.slice(); });
          sets.forEach(function (d) { d.data = d.data.map(function () { return 0; }); });
          chart.update('none');                                   // 가운데에 모두 모인 상태
          sets.forEach(function (d, i) { d.data = real[i]; });
          chart.options.animation = { duration: DURATION, easing: 'easeOutQuart' };
          chart.update();                                         // 가운데 → 각 점수까지 퍼짐
        } catch (e) { /* 그래프가 없어졌으면 무시 */ }
      });
    });
  }

  new MutationObserver(function () { if (visible()) grow(); })
    .observe(modal, { attributes: true, attributeFilter: ['style', 'class'] });
  var canvas = document.getElementById('playerRadarChart');
  if (canvas) new MutationObserver(function () { if (visible()) grow(); })
    .observe(canvas, { attributes: true, attributeFilter: ['width', 'height'] });
})();
