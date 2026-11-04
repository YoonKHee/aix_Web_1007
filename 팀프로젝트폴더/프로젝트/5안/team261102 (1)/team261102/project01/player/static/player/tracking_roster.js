"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const playerSelect = document.getElementById("playerSelect");

  const players = new Map(
    data.players.map(player => [player.player_id, player])
  );

  // 선수 선택창에 실제 이름과 등번호를 표시합니다.
  for (const option of playerSelect.options) {
    const player = players.get(option.value);

    if (!player || !player.real_player_id) continue;

    option.textContent =
      `${player.name} · 실제 등번호 ${player.real_number} · ` +
      `가상 ${player.player_id}(${player.role})`;
  }

  // 전체 선수 기록표의 첫 번째 칸에 이름을 표시합니다.
  const tableBody = document.getElementById("trackingStatsBody");

  if (tableBody) {
    for (const row of tableBody.rows) {
      const nameCell = row.cells[0];

      if (!nameCell) continue;

      const slotId = nameCell.textContent.trim();
      const player = players.get(slotId);

      if (!player || !player.real_player_id) continue;

      nameCell.textContent =
        `${player.name} (${player.player_id})`;

      nameCell.title =
        `${player.real_team_name} · ` +
        `실제 등번호 ${player.real_number} · ` +
        `등록 포지션 ${player.real_position}`;

      nameCell.style.whiteSpace = "nowrap";
    }
  }

  // 명단 버튼을 누르면 기존 분석 대상도 함께 변경합니다.
  for (const button of document.querySelectorAll(
    ".demo-roster-button"
  )) {
    button.addEventListener("click", () => {
      playerSelect.value = button.dataset.slot;

      playerSelect.dispatchEvent(
        new Event("change", { bubbles: true })
      );

      document.getElementById("pitch").scrollIntoView({
        block: "center"
      });
    });
  }
})();