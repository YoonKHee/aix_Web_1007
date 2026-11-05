"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const canvas = document.getElementById("heatmapCanvas");
  const ctx = canvas.getContext("2d");

  const playerSelect = document.getElementById("playerSelect");
  const timeline = document.getElementById("timeline");
  const modeSelect = document.getElementById("heatmapMode");
  const summary = document.getElementById("heatmapSummary");

  const columns = 21;
  const rows = 14;

  const margin = 50;

  const scale = Math.min(
    (canvas.width - margin * 2) / data.pitch.length,
    (canvas.height - margin * 2) / data.pitch.width
  );

  const width = data.pitch.length * scale;
  const height = data.pitch.width * scale;

  const left = (canvas.width - width) / 2;
  const top = (canvas.height - height) / 2;

  let previousKey = "";
  let lastDraw = 0;

  // 좌표가 속한 경기장 구역에 값을 더합니다.
  function addPoint(grid, point, value) {
    if (!point) return;

    const column = Math.max(
      0,
      Math.min(
        columns - 1,
        Math.floor(point.x / data.pitch.length * columns)
      )
    );

    const row = Math.max(
      0,
      Math.min(
        rows - 1,
        Math.floor(point.y / data.pitch.width * rows)
      )
    );

    grid[row * columns + column] += value;
  }

  // 경기장 외곽선, 중앙선, 중앙 원, 페널티 구역을 그립니다.
  function drawLines() {
    ctx.strokeStyle = "#ffffffbb";
    ctx.lineWidth = 2;

    ctx.strokeRect(left, top, width, height);

    ctx.beginPath();
    ctx.moveTo(left + width / 2, top);
    ctx.lineTo(left + width / 2, top + height);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(
      left + width / 2,
      top + height / 2,
      9.15 * scale,
      0,
      Math.PI * 2
    );
    ctx.stroke();

    const boxHeight = 40.32 * scale;
    const boxWidth = 16.5 * scale;
    const boxTop = top + (height - boxHeight) / 2;

    ctx.strokeRect(
      left,
      boxTop,
      boxWidth,
      boxHeight
    );

    ctx.strokeRect(
      left + width - boxWidth,
      boxTop,
      boxWidth,
      boxHeight
    );
  }

  function draw() {
    const playerId = playerSelect.value;
    const time = Number(timeline.value);
    const mode = modeSelect.value;

    const key = `${playerId}|${time}|${mode}`;

    // 선수, 시간, 분석 종류가 같으면 다시 그리지 않습니다.
    if (key === previousKey) return;
    previousKey = key;

    const grid = new Array(columns * rows).fill(0);

    let total = 0;

    // 활동 위치: 각 구역에 머문 시간을 계산합니다.
    if (playerId && mode === "activity") {
      for (let i = 0; i < data.frames.length - 1; i++) {
        const frame = data.frames[i];

        if (frame.time_sec >= time) break;

        const next = data.frames[i + 1];

        // 각 기록에서 다음 기록까지의 시간을 더합니다.
        // 현재 재생 시점 이후의 시간은 포함하지 않습니다.
        const seconds = Math.max(
          0,
          Math.min(time, next.time_sec) - frame.time_sec
        );

        const player = frame.players.find(
          item => item.player_id === playerId
        );

        if (player) {
          addPoint(grid, player, seconds);
          total += seconds;
        }
      }
    }

    // 터치 이벤트: 기록된 패스와 수신 위치를 계산합니다.
    if (playerId && mode === "touch") {
      for (const event of data.events) {
        if (
          event.player_id !== playerId ||
          event.time_sec > time
        ) {
          continue;
        }

        let point = null;

        if (event.type === "pass") {
          point = event.start;
        } else if (event.type === "reception") {
          point = event.position;
        }

        if (point) {
          addPoint(grid, point, 1);
          total += 1;
        }
      }
    }

    // 이전 그림을 지우고 경기장 배경을 그립니다.
    ctx.fillStyle = "#123723";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#207e46";
    ctx.fillRect(left, top, width, height);

    const maximum = Math.max(...grid);
    const cellWidth = width / columns;
    const cellHeight = height / rows;

    if (maximum > 0) {
      for (let row = 0; row < rows; row++) {
        for (let column = 0; column < columns; column++) {
          const value = grid[row * columns + column];

          if (value <= 0) continue;

          const strength = value / maximum;

          // 값이 작은 구역은 노란색, 큰 구역은 빨간색입니다.
          const hue = 60 * (1 - strength);

          ctx.fillStyle = `hsla(${hue}, 100%, 50%, 0.8)`;

          // 원본의 y=0은 아래쪽이므로 화면에서는 위아래를 뒤집습니다.
          ctx.fillRect(
            left + column * cellWidth,
            top + (rows - 1 - row) * cellHeight,
            cellWidth,
            cellHeight
          );
        }
      }
    }

    drawLines();

    if (!playerId) {
      summary.textContent =
        "위의 선수 선택창에서 선수를 선택하세요.";
      return;
    }

    const player = data.players.find(
      item => item.player_id === playerId
    );

    const team =
      player.team_id === "HOME" ? "홈팀" : "원정팀";

    if (mode === "activity") {
      summary.textContent =
        `${team} ${player.number}번 (${playerId}) · ` +
        `활동 위치 · 누적 ${total.toFixed(1)}초 · ` +
        `가장 오래 머문 한 구역 ${maximum.toFixed(1)}초`;
    } else {
      summary.textContent =
        `${team} ${player.number}번 (${playerId}) · ` +
        `기록된 패스·수신 ${total}회` +
        (
          total === 0
            ? " · 해당 시점까지 기록이 없습니다."
            : ""
        );
    }
  }

  // 기존 재생 화면의 선수 선택과 재생 시간을 따라갑니다.
  // 약 0.2초 간격으로 변경 여부를 확인합니다.
  function tick(timestamp) {
    if (timestamp - lastDraw >= 200) {
      draw();
      lastDraw = timestamp;
    }

    requestAnimationFrame(tick);
  }

  draw();
  requestAnimationFrame(tick);
})();