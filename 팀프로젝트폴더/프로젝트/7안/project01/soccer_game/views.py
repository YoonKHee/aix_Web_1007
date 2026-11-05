from django.shortcuts import render


def game(request):
    return render(
        request,
        [
            'soccer_game.html',
            'soccer_game/pending.html',
        ],
    )