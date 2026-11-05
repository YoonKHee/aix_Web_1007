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

  const playerSelect = document.getElementById("playerSelect");
const playerSummary = document.getElementById("playerSummary");

let selectedPlayerId = "";

for (const player of data.players) {
  const option = document.createElement("option");

  option.value = player.player_id;
  option.textContent =
    `${player.team_id === "HOME" ? "홈팀" : "원정팀"} · ` +
    `${player.number}번 · ${player.role} · ${player.player_id}`;

  playerSelect.appendChild(option);
}

// 선택한 선수의 누적 이동 경로와 거리를 계산합니다.
function drawSelectedTrail(first, second, ratio, index) {
  if (!selectedPlayerId) {
    playerSummary.textContent =
      "선수를 선택하면 현재 재생 시점까지의 이동 경로와 거리를 보여줍니다.";
    return;
  }

  const points = [];

  // 현재 시점 이전의 좌표만 사용합니다.
  for (let i = 0; i <= index; i++) {
    const player = frames[i].players.find(
      item => item.player_id === selectedPlayerId
    );

    points.push({ x: player.x, y: player.y });
  }

  const start = first.players.find(
    item => item.player_id === selectedPlayerId
  );

  const end = second.players.find(
    item => item.player_id === selectedPlayerId
  );

  const current = interpolate(start, end, ratio);
  points.push(current);

  let distance = 0;

  for (let i = 1; i < points.length; i++) {
    distance += Math.hypot(
      points[i].x - points[i - 1].x,
      points[i].y - points[i - 1].y
    );
  }

  // 선택한 선수의 이동 경로를 노란 실선으로 표시합니다.
  ctx.strokeStyle = "#ffe168";
  ctx.lineWidth = 4;
  ctx.setLineDash([]);
  ctx.beginPath();

  points.forEach((point, i) => {
    const pixel = screen(point);

    if (i === 0) {
      ctx.moveTo(pixel.x, pixel.y);
    } else {
      ctx.lineTo(pixel.x, pixel.y);
    }
  });

  ctx.stroke();

  // 선택한 선수 주변에 강조 원을 그립니다.
  const pixel = screen(current);

  ctx.beginPath();
  ctx.arc(pixel.x, pixel.y, 20, 0, Math.PI * 2);
  ctx.stroke();

  const info = playerInfo.get(selectedPlayerId);
  const team = info.team_id === "HOME" ? "홈팀" : "원정팀";

  playerSummary.textContent =
    `${team} ${info.number}번 (${info.player_id}) · ` +
    `역할: ${info.role} · ` +
    `재생 시각: ${clock(currentTime)} · ` +
    `누적 이동 거리: ${distance.toFixed(1)}m · ` +
    `현재 위치: x ${current.x.toFixed(1)}m, ` +
    `y ${current.y.toFixed(1)}m · 가상 데이터`;
}

playerSelect.addEventListener("change", () => {
  selectedPlayerId = playerSelect.value;
  render();
});

// 화면 크기가 줄어들어도 클릭 위치를 정확히 변환합니다.
canvas.addEventListener("click", event => {
  const rect = canvas.getBoundingClientRect();

  const clickX =
    (event.clientX - rect.left) * canvas.width / rect.width;

  const clickY =
    (event.clientY - rect.top) * canvas.height / rect.height;

  const index = Math.min(
    Math.floor(currentTime / data.sample_interval_sec),
    frames.length - 2
  );

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

  let nearestId = "";
  let nearestDistance = 22;

  for (const player of first.players) {
    const next = nextPlayers.get(player.player_id);
    const point = screen(interpolate(player, next, ratio));

    const distance = Math.hypot(
      clickX - point.x,
      clickY - point.y
    );

    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestId = player.player_id;
    }
  }

  if (nearestId) {
    selectedPlayerId = nearestId;
    playerSelect.value = nearestId;
    render();
  }
});

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
  const events = data.events
    .filter(event => event.time_sec <= currentTime)
    .sort((a, b) => a.time_sec - b.time_sec);

  const latest = events[events.length - 1];

  let text = "홈팀 H05가 공을 소유하고 있습니다.";

  if (latest) {
    const time = clock(latest.time_sec);

    if (latest.type === "pass") {
      if (currentTime < latest.end_time_sec) {
        // 공이 도착하기 전에는 성공·실패를 미리 표시하지 않습니다.
        text =
          `${time} · ${latest.player_id} → ` +
          `${latest.receiver_id} 패스 진행 중`;
      } else if (latest.outcome === "complete") {
        text =
          `${clock(latest.end_time_sec)} · ` +
          `${latest.player_id} → ${latest.receiver_id} 패스 성공`;
      } else {
        text =
          `${clock(latest.end_time_sec)} · ` +
          `${latest.player_id} 패스 실패`;
      }
    } else if (latest.type === "reception") {
      if (latest.acquisition === "interception") {
        const interceptedPass = data.events.find(event =>
          event.type === "pass" &&
          event.outcome === "incomplete" &&
          event.actual_receiver_id === latest.player_id &&
          event.end_time_sec === latest.time_sec
        );

        text =
          `${time} · ${latest.player_id}이 상대 패스를 가로챘습니다.`;

        if (interceptedPass) {
          text += ` (${interceptedPass.player_id}의 패스 실패)`;
        }
      } else {
        text =
          `${time} · ${latest.player_id} 패스 수신`;
      }
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

drawSelectedTrail(first, second, ratio, index);

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

ctx.save();

ctx.font = "bold 12px sans-serif";
ctx.textAlign = "center";
ctx.textBaseline = "middle";

const playerLabel = info.real_player_id
  ? `${info.name} · ${info.role}`
  : info.role;

// 이름이 잔디 위에서도 잘 보이도록 어두운 테두리를 넣습니다.
ctx.strokeStyle = "#123723";
ctx.lineWidth = 3;
ctx.lineJoin = "round";

ctx.strokeText(
  playerLabel,
  point.x,
  point.y + 27,
  110
);

ctx.fillStyle = "#fff";

ctx.fillText(
  playerLabel,
  point.x,
  point.y + 27,
  110
);

ctx.restore();
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