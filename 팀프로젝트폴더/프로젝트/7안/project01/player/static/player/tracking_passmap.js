"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const canvas = document.getElementById("passMapCanvas");
  const ctx = canvas.getContext("2d");

  const playerSelect = document.getElementById("playerSelect");
  const timeline = document.getElementById("timeline");
  const summary = document.getElementById("passMapSummary");

  const scale = Math.min(
    (canvas.width - 100) / data.pitch.length,
    (canvas.height - 100) / data.pitch.width
  );

  const width = data.pitch.length * scale;
  const height = data.pitch.width * scale;

  const left = (canvas.width - width) / 2;
  const top = (canvas.height - height) / 2;

  let previousKey = "";
  let lastDraw = 0;

  function screen(point) {
    return {
      x: left + point.x * scale,
      y: top + (data.pitch.width - point.y) * scale
    };
  }

  function drawField() {
    ctx.setLineDash([]);

    ctx.fillStyle = "#123723";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "#207e46";
    ctx.fillRect(left, top, width, height);

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

    const boxWidth = 16.5 * scale;
    const boxHeight = 40.32 * scale;
    const boxTop = top + (height - boxHeight) / 2;

    ctx.strokeRect(left, boxTop, boxWidth, boxHeight);

    ctx.strokeRect(
      left + width - boxWidth,
      boxTop,
      boxWidth,
      boxHeight
    );
  }

  function drawPass(pass, number) {
    const start = screen(pass.start);
    const end = screen(pass.end);
    const failed = pass.outcome === "incomplete";

    const color = failed ? "#ff7070" : "#ffe168";

    const angle = Math.atan2(
      end.y - start.y,
      end.x - start.x
    );

    ctx.save();

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 4;

    // 성공은 실선, 실패는 점선으로 구분합니다.
    ctx.setLineDash(failed ? [10, 7] : []);

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();

    ctx.setLineDash([]);

    // 패스 시작 위치를 원으로 표시합니다.
    ctx.beginPath();
    ctx.arc(start.x, start.y, 7, 0, Math.PI * 2);
    ctx.fill();

    if (failed) {
      // 실제로 공을 빼앗긴 위치에 X를 표시합니다.
      const size = 9;

      ctx.beginPath();
      ctx.moveTo(end.x - size, end.y - size);
      ctx.lineTo(end.x + size, end.y + size);
      ctx.moveTo(end.x + size, end.y - size);
      ctx.lineTo(end.x - size, end.y + size);
      ctx.stroke();
    } else {
      // 성공 패스의 도착 위치를 화살표로 표시합니다.
      ctx.beginPath();
      ctx.moveTo(end.x, end.y);
      ctx.lineTo(
        end.x - 16 * Math.cos(angle - Math.PI / 6),
        end.y - 16 * Math.sin(angle - Math.PI / 6)
      );
      ctx.lineTo(
        end.x - 16 * Math.cos(angle + Math.PI / 6),
        end.y - 16 * Math.sin(angle + Math.PI / 6)
      );
      ctx.closePath();
      ctx.fill();
    }

    let label;

    if (failed) {
      label = `${number}. ${pass.player_id} 패스 실패`;

      if (pass.actual_receiver_id) {
        label += ` · ${pass.actual_receiver_id} 가로채기`;
      }
    } else {
      label =
        `${number}. ${pass.player_id} → ${pass.receiver_id}`;
    }

    ctx.fillStyle = "#fff";
    ctx.font = "bold 15px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";

    // 짧은 패스도 설명이 화면 좌우 밖으로 나가지 않게 조정합니다.
    const halfText = ctx.measureText(label).width / 2;

    const labelX = Math.max(
      halfText + 12,
      Math.min(
        canvas.width - halfText - 12,
        (start.x + end.x) / 2
      )
    );

    ctx.fillText(
      label,
      labelX,
      Math.max(24, (start.y + end.y) / 2 - 16)
    );

    ctx.restore();
  }

  function draw() {
    const playerId = playerSelect.value;
    const time = Number(timeline.value);
    const key = `${playerId}|${time}`;

    if (key === previousKey) return;
    previousKey = key;

    drawField();

    if (!playerId) {
      summary.textContent =
        "위의 선수 선택창에서 선수를 선택하세요.";
      return;
    }

    // 현재 재생 시점까지 결과가 확정된 패스만 표시합니다.
    const passes = data.events.filter(event =>
      event.type === "pass" &&
      event.player_id === playerId &&
      event.end_time_sec <= time &&
      (
        event.outcome === "complete" ||
        event.outcome === "incomplete"
      )
    );

    passes.forEach((pass, index) => {
      drawPass(pass, index + 1);
    });

    const successful = passes.filter(
      pass => pass.outcome === "complete"
    ).length;

    const failed = passes.filter(
      pass => pass.outcome === "incomplete"
    ).length;

    const player = data.players.find(
      item => item.player_id === playerId
    );

    const team =
      player.team_id === "HOME" ? "홈팀" : "원정팀";

    summary.textContent =
      `${team} ${player.number}번 (${playerId}) · ` +
      `결과가 확정된 패스 ${passes.length}회 · ` +
      `성공 ${successful}회 · 실패 ${failed}회` +
      (
        passes.length === 0
          ? " · 해당 시점까지 기록이 없습니다."
          : ""
      );
  }

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