"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const container = document.getElementById("trackingEventList");
  const timeline = document.getElementById("timeline");
  const playButton = document.getElementById("playButton");

  const entries = [];

  let previousTime = null;
  let lastUpdate = 0;

  function clock(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainder = Math.floor(seconds % 60);

    return (
      String(minutes).padStart(2, "0") +
      ":" +
      String(remainder).padStart(2, "0")
    );
  }

  function describe(event) {
    if (event.type === "pass") {
      return `${event.player_id} → ${event.receiver_id} 패스 시작`;
    }

    if (
      event.type === "reception" &&
      event.acquisition === "interception"
    ) {
      return `${event.player_id} 상대 패스 가로채기`;
    }

    if (event.type === "reception") {
      return `${event.player_id} 패스 수신`;
    }

    return `${event.player_id} 경기 이벤트`;
  }

  const events = [...data.events].sort(
    (a, b) => a.time_sec - b.time_sec
  );

  for (const event of events) {
    const button = document.createElement("button");

    button.type = "button";
    button.style.textAlign = "left";
    button.style.padding = "12px 16px";
    button.style.border = "1px solid #ffffff33";
    button.style.color = "#fff";

    const label =
      `${clock(event.time_sec)} · ${describe(event)}`;

    button.addEventListener("click", () => {
      // 재생 중이면 기존 재생 버튼을 통해 일시정지합니다.
      if (playButton.textContent.includes("일시정지")) {
        playButton.click();
      }

      timeline.value = event.time_sec;

      // 기존 재생 화면과 연결된 분석 화면을 갱신합니다.
      timeline.dispatchEvent(
        new Event("input", { bubbles: true })
      );

      update();
    });

    container.appendChild(button);

    entries.push({
      button,
      label,
      time: event.time_sec
    });
  }

  function update() {
    const time = Number(timeline.value);

    if (time === previousTime) return;
    previousTime = time;

    let latestIndex = -1;

    entries.forEach((entry, index) => {
      if (entry.time <= time) {
        latestIndex = index;
      }
    });

    entries.forEach((entry, index) => {
      const reached = entry.time <= time;
      const current = index === latestIndex;

      entry.button.style.background =
        current ? "#52632b" : "#1d3b2d";

      entry.button.textContent =
        `${entry.label} · ` +
        (
          current
            ? "현재 이벤트"
            : reached
              ? "지나간 이벤트"
              : "이후 이벤트"
        );
    });
  }

  function tick(timestamp) {
    if (timestamp - lastUpdate >= 200) {
      update();
      lastUpdate = timestamp;
    }

    requestAnimationFrame(tick);
  }

  update();
  requestAnimationFrame(tick);
})();