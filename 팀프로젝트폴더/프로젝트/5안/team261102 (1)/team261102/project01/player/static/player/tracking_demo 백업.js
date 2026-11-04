"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const canvas = document.getElementById("pitch");
  const ctx = canvas.getContext("2d");

  const playButton = document.getElementById("playButton");
  const resetButton = document.getElementById("resetButton");
  const timeline = document.getElementById("timeline");
  const speedSelect = document.getElementById("speed");
  const timeText = document.getElementById("timeText");
  const eventText = document.getElementById("eventText");

  const frames = data.frames;
  const duration = data.duration_sec;

  const margin = 50;
  const scale = Math.min(
    (canvas.width - margin * 2) / data.pitch.length,
    (canvas.height - margin * 2) / data.pitch.width
  );

  const fieldWidth = data.pitch.length * scale;
  const fieldHeight = data.pitch.width * scale;
  const left = (canvas.width - fieldWidth) / 2;
  const top = (canvas.height - fieldHeight) / 2;

  const playerInfo = new Map(
    data.players.map(player => [player.player_id, player])
  );

  let currentTime = 0;
  let playing = false;
  let previousTimestamp = null;
  let previousEventText = "";

  timeline.max = duration;

// 데이터의 왼쪽 아래 원점을 화면의 왼쪽 위 원점으로 변환합니다.
  function screen(point) {
    return {
      x: left + point.x * scale,
      y: top + (data.pitch.width - point.y) * scale
    };
  }

  function line(x1, y1, x2, y2) {
    const start = screen({ x: x1, y: y1 });
    const end = screen({ x: x2, y: y2 });

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
  }

  function fieldRect(x, y, width, height) {
    const corner = screen({ x, y: y + height });

    ctx.strokeRect(
      corner.x,
      corner.y,
      width * scale,
      height * scale
    );
  }

  function drawField() {
    ctx.fillStyle = "#123723";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < 10; i++) {
      ctx.fillStyle = i % 2 === 0 ? "#238b4d" : "#207e46";
      ctx.fillRect(
        left + i * fieldWidth / 10,
        top,
        fieldWidth / 10,
        fieldHeight
      );
    }

    ctx.strokeStyle = "#ffffffbb";
    ctx.lineWidth = 2;

    fieldRect(0, 0, 105, 68);
    line(52.5, 0, 52.5, 68);

    const center = screen({ x: 52.5, y: 34 });

    ctx.beginPath();
    ctx.arc(center.x, center.y, 9.15 * scale, 0, Math.PI * 2);
    ctx.stroke();

    fieldRect(0, 13.84, 16.5, 40.32);
    fieldRect(88.5, 13.84, 16.5, 40.32);

    fieldRect(0, 24.84, 5.5, 18.32);
    fieldRect(99.5, 24.84, 5.5, 18.32);

    ctx.lineWidth = 4;
    line(0, 30.34, 0, 37.66);
    line(105, 30.34, 105, 37.66);
  }

  function interpolate(start, end, ratio) {
    return {
      x: start.x + (end.x - start.x) * ratio,
      y: start.y + (end.y - start.y) * ratio
    };
  }

  function drawPass() {
    const pass = data.events.find(event =>
      event.type === "pass" &&
      currentTime >= event.time_sec &&
      currentTime < event.end_time_sec
    );

    if (!pass) return;

    ctx.strokeStyle = "#ffe168";
    ctx.lineWidth = 3;
    ctx.setLineDash([8, 6]);

    line(
      pass.start.x,
      pass.start.y,
      pass.end.x,
      pass.end.y
    );

    ctx.setLineDash([]);
  }

  function clock(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainder = Math.floor(seconds % 60);

    return (
      String(minutes).padStart(2, "0") +
      ":" +
      String(remainder).padStart(2, "0")
    );
  }

  function updateEvent() {
    const events = data.events.filter(
      event => event.time_sec <= currentTime
    );

    const latest = events[events.length - 1];
    let text = "홈팀이 공을 소유하고 있습니다.";

    if (latest) {
      if (latest.type === "pass") {
        text =
          `${clock(latest.time_sec)} · ` +
          `${latest.player_id} → ${latest.receiver_id} 패스`;
      } else if (latest.type === "reception") {
        text =
          `${clock(latest.time_sec)} · ` +
          `${latest.player_id} 패스 수신`;
      }
    }

    if (text !== previousEventText) {
      eventText.textContent = text;
      previousEventText = text;
    }
  }

  function render() {
    drawField();
    drawPass();

    // 현재 시각을 둘러싼 두 기록 사이를 부드럽게 연결합니다.
    let index = Math.floor(
      currentTime / data.sample_interval_sec
    );

    index = Math.min(index, frames.length - 2);

    const first = frames[index];
    const second = frames[index + 1];

    const ratio = Math.max(
      0,
      Math.min(
        1,
        (currentTime - first.time_sec) /
        (second.time_sec - first.time_sec)
      )
    );

    const nextPlayers = new Map(
      second.players.map(player => [player.player_id, player])
    );

    for (const player of first.players) {
      const next = nextPlayers.get(player.player_id);
      const point = screen(interpolate(player, next, ratio));
      const info = playerInfo.get(player.player_id);

      ctx.fillStyle =
        info.team_id === "HOME" ? "#ed5353" : "#468df0";

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;

      ctx.beginPath();
      ctx.arc(point.x, point.y, 14, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(info.number, point.x, point.y);

      ctx.font = "bold 11px sans-serif";
      ctx.fillText(info.role, point.x, point.y + 25);
    }

    const ball = screen(
      interpolate(first.ball, second.ball, ratio)
    );

    ctx.fillStyle = "#fff";
    ctx.strokeStyle = "#18221b";
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.arc(ball.x, ball.y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    timeline.value = currentTime;
    timeText.textContent =
      `${clock(currentTime)} / ${clock(duration)}`;

    updateEvent();
  }

function setPlaying(value) {
  playing = value;
  previousTimestamp = null;
  playButton.textContent = playing ? "⏸ 일시정지" : "▶ 재생";
}

  playButton.addEventListener("click", () => {
    if (currentTime >= duration) {
      currentTime = 0;
    }

    setPlaying(!playing);
  });

  resetButton.addEventListener("click", () => {
    setPlaying(false);
    currentTime = 0;
    render();
  });

  timeline.addEventListener("input", () => {
    currentTime = Number(timeline.value);
    previousTimestamp = null;
    render();
  });

  function tick(timestamp) {
    if (playing) {
      if (previousTimestamp !== null) {
        // 탭 전환 후 한꺼번에 시간이 뛰는 현상을 제한합니다.
        const elapsed = Math.min(
          (timestamp - previousTimestamp) / 1000,
          0.1
        );

        currentTime = Math.min(
          duration,
          currentTime + elapsed * Number(speedSelect.value)
        );

        if (currentTime >= duration) {
          setPlaying(false);
        }
      }

      previousTimestamp = timestamp;
      render();
    }

    requestAnimationFrame(tick);
  }

  render();
  requestAnimationFrame(tick);
})();