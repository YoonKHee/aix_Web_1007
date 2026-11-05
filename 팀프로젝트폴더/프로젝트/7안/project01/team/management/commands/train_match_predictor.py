from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from team.train_prediction import train_model


class Command(BaseCommand):
    help = (
        '경기 전 기록만 사용해 승무패 모델을 학습하고 '
        '시간순으로 성능을 검증합니다.'
    )

    def handle(self, *args, **options):
        try:
            bundle = train_model()

        except (
            ImportError,
            ValueError,
            OSError,
        ) as exc:
            raise CommandError(
                str(exc)
            ) from exc

        evaluation = bundle['evaluation']

        self.stdout.write(
            f"학습 {evaluation['train_count']}경기"
            f" / 평가 {evaluation['test_count']}경기"
        )

        self.stdout.write(
            f"학습 기간: "
            f"{evaluation['train_start']}"
            f" ~ {evaluation['train_end']}"
        )

        self.stdout.write(
            f"평가 기간: "
            f"{evaluation['test_start']}"
            f" ~ {evaluation['test_end']}"
        )

        for key, title in [
            (
                'model',
                '승무패 예측 모델',
            ),
            (
                'frequency_baseline',
                '학습 결과 비율 기준',
            ),
        ]:
            metrics = evaluation[key]

            self.stdout.write('')
            self.stdout.write(title)

            self.stdout.write(
                f"정확도: {metrics['accuracy']:.1%}"
            )

            self.stdout.write(
                f"정밀도: "
                f"{metrics['precision_macro']:.3f}"
            )

            self.stdout.write(
                f"재현율: "
                f"{metrics['recall_macro']:.3f}"
            )

            self.stdout.write(
                f"F1: {metrics['f1_macro']:.3f}"
            )

            self.stdout.write(
                f"확률 오차: "
                f"{metrics['log_loss']:.3f}"
            )

        self.stdout.write('')

        self.stdout.write(
            self.style.SUCCESS(
                '모델 JSON 저장 완료'
            )
        )

        self.stdout.write(
            f"최종 학습 경기 수: "
            f"{bundle['training_match_count']}경기"
        )

        self.stdout.write(
            f"학습 기준일: "
            f"{bundle['trained_through']}"
        )

        self.stdout.write(
            '위 성능은 시간순으로 분리한 평가 결과입니다.'
        )

        self.stdout.write(
            '저장된 최종 모델은 평가 후 전체 사용 가능 '
            '경기로 다시 학습한 모델입니다.'
        )