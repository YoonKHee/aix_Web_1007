"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const tbody = document.getElementById("trackingStatsBody");
  const timeline = document.getElementById("timeline");
  const playerSelect = document.getElementById("playerSelect");

  const frames = data.frames.map(frame => ({
    time: frame.time_sec,
    positions: new Map(
      frame.players.map(player => [player.player_id, player])
    )
  }));

  const tableRows = new Map();

  let previousKey = "";
  let lastDraw = 0;

  // 선수별로 9개 항목을 표시할 행을 만듭니다.
  for (const player of data.players) {
    const row = document.createElement("tr");

    row.style.cursor = "pointer";
    row.style.borderBottom = "1px solid #ffffff22";

    const cells = [];

    for (let i = 0; i < 9; i++) {
      const cell = document.createElement("td");
      cell.style.padding = "12px";
      row.appendChild(cell);
      cells.push(cell);
    }

    cells[0].textContent = player.player_id;
    cells[1].textContent =
      player.team_id === "HOME" ? "홈팀" : "원정팀";
    cells[2].textContent = player.role;

    row.addEventListener("click", () => {
      playerSelect.value = player.player_id;

      playerSelect.dispatchEvent(
        new Event("change", { bubbles: true })
      );
    });

    tbody.appendChild(row);

    tableRows.set(player.player_id, {
      row,
      cells
    });
  }

  function calculate(time) {
    const stats = new Map(
      data.players.map(player => [
        player.player_id,
        {
          distance: 0,
          passes: 0,
          failedPasses: 0,
          receptions: 0,
          interceptions: 0,
          touches: 0
        }
      ])
    );

    // 현재 재생 시점까지 이동한 거리만 계산합니다.
    for (let i = 0; i < frames.length - 1; i++) {
      const first = frames[i];
      const second = frames[i + 1];

      if (first.time >= time) break;

      const interval = second.time - first.time;

      if (interval <= 0) continue;

      const fraction = Math.max(
        0,
        Math.min(1, (time - first.time) / interval)
      );

      for (const player of data.players) {
        const start = first.positions.get(player.player_id);
        const end = second.positions.get(player.player_id);

        if (!start || !end) continue;

        stats.get(player.player_id).distance +=
          Math.hypot(
            end.x - start.x,
            end.y - start.y
          ) * fraction;
      }
    }

    for (const event of data.events) {
      const record = stats.get(event.player_id);

      if (!record || event.time_sec > time) continue;

      if (event.type === "pass") {
        // 패스를 시작한 순간 터치 1회로 집계합니다.
        record.touches += 1;

        // 공이 도착하기 전에는 성공·실패를 집계하지 않습니다.
        if (event.end_time_sec > time) continue;

        if (event.outcome === "complete") {
          record.passes += 1;
        } else if (event.outcome === "incomplete") {
          record.failedPasses += 1;
        }
      } else if (event.type === "reception") {
        record.touches += 1;

        // 같은 수신 사건을 두 항목에 중복 집계하지 않습니다.
        if (event.acquisition === "interception") {
          record.interceptions += 1;
        } else {
          record.receptions += 1;
        }
      }
    }

    return stats;
  }

  function update() {
    const time = Number(timeline.value);
    const selected = playerSelect.value;
    const key = `${time}|${selected}`;

    if (key === previousKey) return;
    previousKey = key;

    const stats = calculate(time);

    for (const player of data.players) {
      const record = stats.get(player.player_id);
      const { row, cells } = tableRows.get(player.player_id);

      row.style.background =
        player.player_id === selected ? "#52632b" : "#1d3b2d";

      cells[3].textContent = `${record.distance.toFixed(1)}m`;
      cells[4].textContent = record.passes;
      cells[5].textContent = record.failedPasses;
      cells[6].textContent = record.receptions;
      cells[7].textContent = record.interceptions;
      cells[8].textContent = record.touches;
    }
  }

  function tick(timestamp) {
    if (timestamp - lastDraw >= 200) {
      update();
      lastDraw = timestamp;
    }

    requestAnimationFrame(tick);
  }

  update();
  requestAnimationFrame(tick);
})();