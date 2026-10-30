from datetime import date, timedelta

from django import forms
from django.shortcuts import render
from django.utils import timezone

from team.match_prediction import (
    PredictionUnavailable,
    forecast,
    load_bundle,
    load_matches,
    team_options,
)


class MatchPredictionForm(forms.Form):
    home = forms.ChoiceField(
        label='홈팀',
    )

    away = forms.ChoiceField(
        label='원정팀',
    )

    date = forms.DateField(
        label='예상 경기일',
        widget=forms.DateInput(
            attrs={
                'type': 'date',
            }
        ),
    )

    def __init__(
        self,
        *args,
        teams,
        last_day,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        choices = [
            (
                team['id'],
                team['name'],
            )
            for team in teams
        ]

        self.fields['home'].choices = choices
        self.fields['away'].choices = choices

        self.last_day = last_day

        self.fields['date'].widget.attrs.update({
            'min': (
                last_day + timedelta(days=1)
            ).isoformat(),
            'max': '2026-12-31',
        })

    def clean(self):
        cleaned = super().clean()

        home = cleaned.get('home')
        away = cleaned.get('away')
        day = cleaned.get('date')

        if home and home == away:
            raise forms.ValidationError(
                '서로 다른 두 팀을 선택하세요.'
            )

        if day and (
            day <= self.last_day
            or day.year != 2026
        ):
            raise forms.ValidationError(
                f'{self.last_day} 이후의 2026년 날짜를 선택하세요.'
            )

        return cleaned


def predict_match(request):
    context = {
        'prediction': None,
        'form': None,
    }

    try:
        matches, digest = load_matches()
        bundle = load_bundle(digest)
        teams = team_options(matches)

        last_day = date.fromisoformat(
            bundle['trained_through']
        )

        initial = {
            'home': teams[0]['id'],
            'away': teams[1]['id'],
            'date': max(
                timezone.localdate(),
                last_day + timedelta(days=1),
            ),
        }

        form = MatchPredictionForm(
            request.GET if request.GET else None,
            teams=teams,
            last_day=last_day,
            initial=initial,
        )

        context.update({
            'form': form,
            'last_day': last_day,
            'training_count': (
                bundle['training_match_count']
            ),
        })

        if form.is_bound and form.is_valid():
            try:
                context['prediction'] = forecast(
                    matches,
                    bundle,
                    form.cleaned_data['home'],
                    form.cleaned_data['away'],
                    form.cleaned_data['date'],
                )

            except PredictionUnavailable as exc:
                form.add_error(
                    None,
                    str(exc),
                )

        evaluation = bundle['evaluation']

        context['evaluation'] = evaluation

        context['metrics'] = [
            {
                'name': name,
                'accuracy': (
                    evaluation[key]['accuracy'] * 100
                ),
                'precision': (
                    evaluation[key]['precision_macro']
                ),
                'recall': (
                    evaluation[key]['recall_macro']
                ),
                'f1': (
                    evaluation[key]['f1_macro']
                ),
                'log_loss': (
                    evaluation[key]['log_loss']
                ),
            }
            for name, key in [
                (
                    '첫 예측 모델',
                    'model',
                ),
                (
                    '학습 결과 비율 기준',
                    'frequency_baseline',
                ),
            ]
        ]

        context['beats_baseline'] = (
            evaluation['model']['accuracy']
            > evaluation['frequency_baseline']['accuracy']

            and evaluation['model']['log_loss']
            < evaluation['frequency_baseline']['log_loss']
        )

    except PredictionUnavailable as exc:
        context['unavailable'] = str(exc)

    return render(
        request,
        'team/predict_match.html',
        context,
    )