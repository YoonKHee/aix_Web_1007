"use strict";

(() => {
  const data = JSON.parse(
    document.getElementById("tracking-data").textContent
  );

  const playerSelect = document.getElementById("playerSelect");

  const card = document.getElementById("selectedPlayerCard");
  const photo = document.getElementById("selectedPlayerPhoto");
  const photoEmpty = document.getElementById(
    "selectedPlayerPhotoEmpty"
  );

  const name = document.getElementById("selectedPlayerName");
  const details = document.getElementById("selectedPlayerDetails");
  const slot = document.getElementById("selectedPlayerSlot");
  const link = document.getElementById("selectedPlayerLink");

  const players = new Map(
    data.players.map(player => [player.player_id, player])
  );

  let expectedPhotoUrl = "";

  photo.addEventListener("load", () => {
    // 이전에 선택한 선수의 이미지 응답은 표시하지 않습니다.
    if (photo.getAttribute("src") !== expectedPhotoUrl) return;

    photo.hidden = false;
    photoEmpty.hidden = true;
  });

  photo.addEventListener("error", () => {
    if (photo.getAttribute("src") !== expectedPhotoUrl) return;

    photo.hidden = true;
    photoEmpty.hidden = false;
    photoEmpty.textContent = "사진을 불러올 수 없습니다.";
  });

  function update() {
    const player = players.get(playerSelect.value);

    if (!player) {
      card.hidden = true;
      expectedPhotoUrl = "";
      photo.removeAttribute("src");
      return;
    }

    card.hidden = false;

    photo.hidden = true;
    photoEmpty.hidden = false;
    photoEmpty.textContent = "사진 없음";

    expectedPhotoUrl = "";
    photo.removeAttribute("src");

    slot.textContent =
      `가상 슬롯: ${player.player_id} · ` +
      `가상 역할: ${player.role}`;

    if (player.real_player_id) {
      name.textContent = player.name;

      details.textContent =
        `${player.real_team_name} · ` +
        `실제 등번호: ${player.real_number} · ` +
        `등록 포지션: ${player.real_position}`;

      link.href = `/player/pview/${player.real_player_id}/`;
      link.hidden = false;

      if (player.real_photo_url) {
        photo.alt = `${player.name} 선수 사진`;
        photoEmpty.textContent = "사진 불러오는 중";

        expectedPhotoUrl = player.real_photo_url;
        photo.src = expectedPhotoUrl;
      }
    } else {
      name.textContent = player.name;

      details.textContent =
        `${player.team_id === "HOME" ? "홈팀" : "원정팀"} · ` +
        "실제 선수와 연결되지 않은 가상 선수";

      photo.alt = "";
      link.hidden = true;
      link.removeAttribute("href");
    }
  }

  playerSelect.addEventListener("change", update);

  // 경기장 클릭으로 선택한 경우에도 카드를 갱신합니다.
  const canvas = document.getElementById("pitch");

  canvas.addEventListener("click", update);

  update();
})();