import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from players.models import Player, Team

REQUIRED = ["팀", "이름", "포지션"]
PROFILE = {
    "등번호": "number",
    "키": "height_cm",
    "몸무게": "weight_kg",
    "생년월일": "birth_date",
}
NUMBER_RE = re.compile(r"^-?\d[\d,]*(\.\d+)?$")


def is_empty(value):
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


def clean_text(value):
    return "" if is_empty(value) else str(value).strip()


def extract_int(value):
    """'190Cm' -> 190, '1,381' -> 1381, 숫자가 없으면 None"""
    match = re.search(r"\d+", str(value).replace(",", ""))
    return int(match.group()) if match else None


def clean_value(value):
    """기록 값을 DB에 저장할 수 있는 형태로 정리"""
    if hasattr(value, "item"):  # numpy 숫자를 파이썬 숫자로
        value = value.item()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, str):
        text = value.strip()
        if NUMBER_RE.match(text):
            number = float(text.replace(",", ""))
            return int(number) if number.is_integer() else number
        return text
    return value


class Command(BaseCommand):
    help = "엑셀/CSV 파일의 선수 데이터를 DB에 반영합니다."

    def add_arguments(self, parser):
        parser.add_argument("path", help="엑셀(.xlsx) 또는 CSV 파일 경로")
        parser.add_argument("--league", default="K리그1", help="리그 이름 (기본: K리그1)")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="DB의 팀·선수를 모두 지우고 파일 내용으로 교체 (실행 전 DB 백업)",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"파일을 찾을 수 없습니다: {path}")

        df = self.read_file(path)
        missing = [col for col in REQUIRED if col not in df.columns]
        if missing:
            raise CommandError(f"필수 열이 없습니다: {', '.join(missing)}")

        if options["replace"]:
            self.backup_db()

        league = options["league"]
        created_count, updated_count, errors = 0, 0, []

        with transaction.atomic():
            if options["replace"]:
                Team.objects.all().delete()  # 소속 선수도 함께 삭제됨

            for line, row in enumerate(df.to_dict("records"), start=2):
                team_name = clean_text(row["팀"])
                name = clean_text(row["이름"])
                position = clean_text(row["포지션"])

                if not team_name or not name:
                    errors.append(f"{line}행: 팀 또는 이름이 비어 있습니다")
                    continue
                if position not in Player.Position.values:
                    allowed = ", ".join(Player.Position.values)
                    errors.append(f"{line}행({name}): 포지션 '{position}'은(는) {allowed} 중 하나여야 합니다")
                    continue

                team, _ = Team.objects.get_or_create(league=league, name=team_name)
                player, was_created = Player.objects.get_or_create(
                    team=team, name=name, defaults={"position": position}
                )
                player.position = position

                for column, field in PROFILE.items():
                    value = row.get(column)
                    if is_empty(value):
                        continue
                    if field == "birth_date":
                        parsed = pd.to_datetime(value, errors="coerce")
                        if pd.isna(parsed):
                            errors.append(f"{line}행({name}): 생년월일 '{value}'을(를) 읽을 수 없습니다")
                            continue
                        value = parsed.date()
                    else:
                        value = extract_int(value)
                        if value is None:
                            errors.append(f"{line}행({name}): '{column}' 값에서 숫자를 찾을 수 없습니다")
                            continue
                    setattr(player, field, value)

                # 나머지 열은 전부 stats에 병합: 같은 열은 덮어쓰고, 새 열은 추가
                new_stats = {
                    str(column): clean_value(value)
                    for column, value in row.items()
                    if column not in REQUIRED and column not in PROFILE and not is_empty(value)
                }
                player.stats = {**player.stats, **new_stats}
                player.save()

                if was_created:
                    created_count += 1
                else:
                    updated_count += 1

            if errors:  # 에러가 있으면 전체 취소 (DB는 그대로)
                shown = "\n".join(errors[:20])
                more = f"\n... 외 {len(errors) - 20}건" if len(errors) > 20 else ""
                raise CommandError(f"문제가 있어 중단했습니다. DB는 변경되지 않았습니다.\n{shown}{more}")

        self.stdout.write(self.style.SUCCESS(f"완료: 새로 {created_count}명, 갱신 {updated_count}명"))

    def read_file(self, path):
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path, encoding="utf-8-sig")
        elif suffix in (".xlsx", ".xlsm"):
            df = pd.read_excel(path)
        else:
            raise CommandError("지원하는 형식은 .xlsx, .csv 입니다.")
        df.columns = [str(col).strip() for col in df.columns]
        return df

    def backup_db(self):
        db_path = Path(settings.DATABASES["default"]["NAME"])
        if db_path.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = db_path.with_name(f"{db_path.stem}_backup_{stamp}{db_path.suffix}")
            shutil.copy2(db_path, backup)
            self.stdout.write(f"백업 완료: {backup.name}")