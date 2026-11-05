"""학습 구간 내부에서 모형을 선택하고 이전 버전과 비교합니다."""

from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from team.match_prediction import (
    FEATURE_NAMES,
    MODEL_VERSION,
    chronological_split,
    load_matches,
    model_path,
    predict_probabilities,
    training_rows,
)


def train_model(output=None):
    import numpy as np
    import sklearn

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        precision_recall_fscore_support,
        log_loss,
        confusion_matrix,
    )
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    matches, digest = load_matches()
    rows = training_rows(matches)
    train, test = chronological_split(rows)

    classes = ['A', 'D', 'H']

    def fit(kind, data):
        if kind == 'poisson':
            return None

        columns = (
            7
            if kind == 'legacy'
            else len(FEATURE_NAMES)
        )

        pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.5 if kind == 'legacy' else 0.2,
                max_iter=2000,
                random_state=0,
            ),
        )

        pipeline.fit(
            [row['x'][:columns] for row in data],
            [row['y'] for row in data],
        )

        return pipeline

    def probabilities(kind, fitted, data):
        if kind == 'poisson':
            temporary_bundle = {
                'model': {
                    'kind': 'poisson',
                }
            }

            return np.array([
                [
                    predict_probabilities(
                        temporary_bundle,
                        row['x'],
                    )[key]
                    for key in classes
                ]
                for row in data
            ])

        columns = (
            7
            if kind == 'legacy'
            else len(FEATURE_NAMES)
        )

        return fitted.predict_proba([
            row['x'][:columns]
            for row in data
        ])

    def summarize(actual, predicted_probabilities):
        predicted = [
            classes[int(np.argmax(probability))]
            for probability in predicted_probabilities
        ]

        precision, recall, f1, _ = (
            precision_recall_fscore_support(
                actual,
                predicted,
                labels=classes,
                average='macro',
                zero_division=0,
            )
        )

        return {
            'accuracy': float(
                accuracy_score(actual, predicted)
            ),
            'precision_macro': float(precision),
            'recall_macro': float(recall),
            'f1_macro': float(f1),
            'log_loss': float(
                log_loss(
                    actual,
                    predicted_probabilities,
                    labels=classes,
                )
            ),
            'confusion_matrix': confusion_matrix(
                actual,
                predicted,
                labels=classes,
            ).tolist(),
            'prediction_counts': dict(
                Counter(predicted)
            ),
        }

    # 최종 평가 구간을 제외한 학습 구간 안에서만
    # 시간순으로 세 번 비교하여 모형을 선택합니다.
    dates = sorted({
        row['date']
        for row in train
    })

    start = len(dates) // 2
    folds = []

    for index in range(3):
        lo = start + (
            (len(dates) - start) * index // 3
        )

        hi = start + (
            (len(dates) - start) * (index + 1) // 3
        )

        prefix = [
            row for row in train
            if row['date'] < dates[lo]
        ]

        validation = [
            row for row in train
            if dates[lo] <= row['date'] <= dates[hi - 1]
        ]

        if (
            validation
            and set(row['y'] for row in prefix)
            == set(classes)
        ):
            folds.append((
                prefix,
                validation,
            ))

    if not folds:
        raise ValueError(
            '학습 구간 내부의 시간순 비교 자료가 부족합니다.'
        )

    selection = {}

    for kind in ('legacy', 'season', 'poisson'):
        actual = []
        predicted_probabilities = []

        for prefix, validation in folds:
            fitted = fit(kind, prefix)

            predicted_probabilities.extend(
                probabilities(
                    kind,
                    fitted,
                    validation,
                )
            )

            actual.extend(
                row['y']
                for row in validation
            )

        selection[kind] = summarize(
            actual,
            predicted_probabilities,
        )

    selected = min(
        selection,
        key=lambda key: selection[key]['log_loss'],
    )

    # 선택을 마친 뒤 같은 평가 구간에서 이전 버전과 비교합니다.
    actual = [
        row['y']
        for row in test
    ]

    selected_probabilities = probabilities(
        selected,
        fit(selected, train),
        test,
    )

    legacy_probabilities = probabilities(
        'legacy',
        fit('legacy', train),
        test,
    )

    counts = Counter(
        row['y']
        for row in train
    )

    majority = max(
        classes,
        key=lambda key: counts[key],
    )

    prior = [
        (counts[key] + 1)
        / (len(train) + len(classes))
        for key in classes
    ]

    evaluation = {
        'method': (
            'Train-only expanding time folds choose the method; '
            'same original date-based holdout compares versions.'
        ),
        'test_features_policy': (
            'Only earlier dates inform each match; '
            'earlier test-day outcomes may inform later test days.'
        ),
        'previously_seen_test_period': True,
        'selection_method': (
            'Minimum pooled log loss over three expanding '
            'training-only time folds.'
        ),
        'selection': selection,
        'selected_method': selected,
        'selection_folds': [
            {
                'train_end': prefix[-1]['date'],
                'validation_start': validation[0]['date'],
                'validation_end': validation[-1]['date'],
                'train_count': len(prefix),
                'validation_count': len(validation),
            }
            for prefix, validation in folds
        ],
        'train_count': len(train),
        'test_count': len(test),
        'train_start': train[0]['date'],
        'train_end': train[-1]['date'],
        'test_start': test[0]['date'],
        'test_end': test[-1]['date'],
        'classes': classes,
        'train_class_counts': dict(counts),
        'test_class_counts': dict(
            Counter(actual)
        ),
        'model': summarize(
            actual,
            selected_probabilities,
        ),
        'legacy_model': summarize(
            actual,
            legacy_probabilities,
        ),
        'frequency_baseline': summarize(
            actual,
            [prior for _ in test],
        ),
        'majority_baseline_accuracy': (
            sum(result == majority for result in actual)
            / len(test)
        ),
        'majority_label': majority,
        'equal_probability_log_loss': math.log(3),
        'limitations': [
            (
                'The original holdout was inspected during the '
                'earlier version: this is an exploratory comparison, '
                'not a new untouched test.'
            ),
            (
                'One season and a small sample; '
                'probability calibration is not established.'
            ),
            (
                'Poisson assumes independent scoring; '
                'low-scoring draws and tactical interactions '
                'can be misrepresented.'
            ),
            (
                'No forced home-win bonus. Venue goal rates '
                'are estimated using prior matches only.'
            ),
        ],
    }

    final = fit(selected, rows)

    if selected == 'poisson':
        exported = {
            'kind': 'poisson',
            'classes': classes,
            'max_goals': 25,
        }

    else:
        scaler = final.steps[0][1]
        classifier = final.steps[1][1]

        width = len(FEATURE_NAMES)

        coefficients = np.zeros((3, width))
        means = np.zeros(width)
        scales = np.ones(width)

        columns = len(scaler.mean_)

        coefficients[:, :columns] = classifier.coef_
        means[:columns] = scaler.mean_
        scales[:columns] = scaler.scale_

        exported = {
            'kind': 'logistic',
            'classes': list(classifier.classes_),
            'coef': coefficients.tolist(),
            'intercept': classifier.intercept_.tolist(),
            'mean': means.tolist(),
            'scale': scales.tolist(),
        }

    bundle = {
        'version': MODEL_VERSION,
        'algorithm': selected,
        'created_at': (
            datetime.now(timezone.utc).isoformat()
        ),
        'dataset_sha256': digest,
        'trained_through': matches[-1]['match_date'],
        'training_match_count': (
            len(matches)
            if selected == 'poisson'
            else len(rows)
        ),
        'feature_row_count': len(rows),
        'skipped_warmup_matches': (
            len(matches) - len(rows)
        ),
        'feature_names': FEATURE_NAMES,
        'min_previous_matches': 5,
        'sklearn_version': sklearn.__version__,
        'evaluation': evaluation,
        'model': exported,
    }

    expected = probabilities(
        selected,
        final,
        rows,
    )

    actual_probabilities = [
        [
            predict_probabilities(
                bundle,
                row['x'],
            )[key]
            for key in classes
        ]
        for row in rows
    ]

    if not np.allclose(
        expected,
        actual_probabilities,
        rtol=1e-10,
        atol=1e-12,
    ):
        raise RuntimeError(
            'JSON 확률 계산 검증 실패'
        )

    target = (
        Path(output)
        if output
        else model_path()
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = target.with_suffix('.tmp')

    temporary.write_text(
        json.dumps(
            bundle,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + '\n',
        encoding='utf-8',
    )

    temporary.replace(target)

    return bundle