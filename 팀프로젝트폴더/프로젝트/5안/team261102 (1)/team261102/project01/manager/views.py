import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connections
from django.db.models import Count, Q
from django.core.exceptions import TooManyFilesSent
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from player.models import Player, PlayerStats
from team.models import Team

from . import backup as bk
from . import config
from .importer import STAT_FIELDS, apply_plan, build_plan
from .models import (BestExclusion, ImportBatch, ScoreConfig, ScoreConfigLog, StatColumn)


def db_path():
    return settings.DATABASES['default']['NAME']


def backup_dir():
    return Path(settings.BASE_DIR) / 'manager_backups'


def is_admin(user):
    return user.is_active and user.is_superuser


admin_only = user_passes_test(is_admin, login_url='/admin/login/')


@admin_only
def dashboard(request):
    teams = Team.objects.annotate(
        total=Count('player', distinct=True),
        with_stats=Count('player', filter=Q(player__playerstats__season=2026), distinct=True),
        no_photo=Count('player', filter=Q(player__photo=''), distinct=True),
        no_birth=Count('player', filter=Q(player__birth_date__isnull=True), distinct=True),
    ).order_by('team_name')
    rows = []
    for t in teams:
        t.no_stats = t.total - t.with_stats
        rows.append(t)
    sums = {k: sum(getattr(t, k) for t in rows)
            for k in ('total', 'with_stats', 'no_stats', 'no_photo', 'no_birth')}
    return render(request, 'manager/dashboard.html', {'rows': rows, 'sums': sums,
                                                      'columns': StatColumn.objects.all()})


def build_existing(season):
    """DB의 선수 + 현재 값 (파일과 비교해서 '변경 전'을 보여주기 위함)"""
    stats = {s['player_id']: s for s in
             PlayerStats.objects.filter(season=season).values('player_id', *STAT_FIELDS)}
    out = []
    for p in Player.objects.select_related('team'):
        bd = p.birth_date.isoformat() if p.birth_date else None
        s = stats.get(p.id)
        out.append(dict(
            id=p.id, team=p.team.team_name, name=p.name, birth_date=bd,
            age=p.age or None, has_photo=bool(p.photo),
            cur=dict(number=p.number, position=p.position, height=p.height,
                     weight=p.weight, birth_date=bd, age=p.age),
            stats={str(season): {k: v for k, v in s.items() if k != 'player_id'}} if s else {}))
    return out


@admin_only
def import_upload(request):
    if request.method == 'POST':
        try:
            files = request.FILES.getlist('files')
        except TooManyFilesSent:
            messages.error(request, '한 번에 보낼 수 있는 파일 개수 제한(기본 100개)에 걸렸습니다. '
                                    'settings.py 에 DATA_UPLOAD_MAX_NUMBER_FILES = None 을 추가하거나 ZIP 으로 묶어 올려주세요.')
            return redirect('manager:import_upload')
        if not files:
            messages.error(request, '파일을 선택해주세요.')
            return redirect('manager:import_upload')
        try:                                   # 폴더 구조(팀 폴더 등)를 살리기 위해 브라우저가 보낸 상대경로 사용
            paths = json.loads(request.POST.get('paths') or '[]')
        except ValueError:
            paths = []
        names = []
        for i, f in enumerate(files):
            p = paths[i] if len(paths) == len(files) and isinstance(paths[i], str) else f.name
            p = '/'.join(x for x in p.replace('\\', '/').split('/') if x not in ('', '.', '..'))
            names.append(p or f.name)
        try:
            season = int(request.POST.get('season') or 2026)
        except ValueError:
            season = 2026
        registered = list(StatColumn.objects.values_list('name', flat=True))
        plan, blobs = build_plan(
            [(n, f.read()) for n, f in zip(names, files)],
            list(Team.objects.values_list('team_name', flat=True)),
            build_existing(season), default_season=season, registered_columns=registered)
        batch = ImportBatch.objects.create(
            created_by=request.user.get_username(),
            filenames=', '.join(names)[:2000], season=season, plan=plan)
        for key, data in blobs.items():                    # 사진은 승인 전까지 임시 보관
            default_storage.save(f'import_tmp/{batch.pk}/{key}', ContentFile(data))
        return redirect('manager:import_report', pk=batch.pk)
    return render(request, 'manager/upload.html')


@admin_only
def import_report(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    plan = batch.plan
    changed = [p for p in plan['players'] if p['changes']]
    registered = list(StatColumn.objects.values_list('name', flat=True))
    new_names = [x['name'] for x in plan.get('proposals', [])]
    ctx = {
        'batch': batch, 'plan': plan,
        'errors': [i for i in plan['issues'] if i['level'] == 'error'],
        'warns': [i for i in plan['issues'] if i['level'] == 'warn'],
        'fixes': [i for i in plan['issues'] if i['level'] == 'fix'],
        'infos': [i for i in plan['issues'] if i['level'] == 'info'],
        'changed': changed[:80], 'changed_total': len(changed),
        'has_transfer': any(p['action'] == 'transfer' for p in plan['players']),
        'registered': registered, 'after_columns': registered + new_names,
    }
    return render(request, 'manager/report.html', ctx)


def write_schema_file(batch, approved, plan, registered):
    folder = Path(settings.BASE_DIR) / 'manager' / 'schema_log'
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = folder / f'schema_{batch.pk:04d}_{stamp}.json'
    props = {x['name']: x for x in plan.get('proposals', [])}
    content = {
        '업로드': batch.pk, '시각': datetime.now().isoformat(timespec='seconds'), '파일': batch.filenames,
        '변경 전 추가 컬럼': registered,
        '변경 후 추가 컬럼': registered + list(approved),
        '추가한 컬럼': [props[n] for n in approved if n in props],
        '승인하지 않은 컬럼': [n for n in props if n not in approved],
    }
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path.relative_to(settings.BASE_DIR))


@admin_only
@require_POST
def import_apply(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    if batch.status == '반영됨':
        messages.error(request, '이미 반영된 업로드입니다.')
        return redirect('manager:import_report', pk=pk)
    try:                                   # 반영 직전 자동 백업 — 실패하면 반영하지 않는다
        backup_name = bk.make_backup(db_path(), backup_dir(), f'업로드 #{batch.pk} 반영 직전',
                                     batch_id=batch.pk, user=request.user.get_username())
    except Exception as e:
        messages.error(request, f'자동 백업에 실패해서 반영하지 않았습니다: {e}')
        return redirect('manager:import_report', pk=pk)
    registered = list(StatColumn.objects.values_list('name', flat=True))
    props = {x['name']: x for x in batch.plan.get('proposals', [])}
    approved = [n for n in request.POST.getlist('approve_col') if n in props]

    def read_blob(key):
        try:
            with default_storage.open(f'import_tmp/{batch.pk}/{key}') as f:
                return f.read()
        except Exception:
            return None

    result = apply_plan(batch.plan, allow_transfer=bool(request.POST.get('allow_transfer')),
                        approved_columns=approved, registered_columns=registered, read_blob=read_blob)
    for n in approved:
        StatColumn.objects.get_or_create(name=n, defaults=dict(kind=props[n]['kind'], batch=batch))
    if props:
        batch.schema_file = write_schema_file(batch, approved, batch.plan, registered)
    result['approved_columns'] = approved
    result['backup'] = backup_name
    batch.status = '반영됨'
    batch.result = result
    batch.save()
    messages.success(request, f'반영 완료: 새 선수 {result["created"]}명, 수정 {result["updated"]}명, '
                              f'이적 {result["transferred"]}명, 사진 {result["photos_linked"]}장, '
                              f'새 컬럼 {len(approved)}개')
    return redirect('manager:import_report', pk=pk)


@admin_only
def history(request):
    return render(request, 'manager/history.html', {'batches': ImportBatch.objects.all()[:100]})


# ---------------------------------------------------------------- 백업 / 되돌리기
@admin_only
def backups(request):
    return render(request, 'manager/backups.html', {'items': bk.list_backups(backup_dir()), 'keep': bk.KEEP})


@admin_only
@require_POST
def backup_now(request):
    try:
        name = bk.make_backup(db_path(), backup_dir(), request.POST.get('reason', '').strip() or '수동 백업',
                              user=request.user.get_username())
        messages.success(request, f'백업했습니다: {name}')
    except Exception as e:
        messages.error(request, f'백업 실패: {e}')
    return redirect('manager:backups')


@admin_only
def backup_restore(request, name):
    item = bk.get_backup(backup_dir(), name)
    if item is None:
        raise Http404('백업 파일이 없습니다.')
    later = [b for b in bk.list_backups(backup_dir()) if b['name'] > name]      # 이 백업 이후에 만들어진 것들
    later_batches = list(ImportBatch.objects.filter(status='반영됨', created_at__gt=_parse(item.get('created'))))
    if request.method == 'POST':
        if not request.POST.get('confirm'):
            messages.error(request, '확인 체크를 해야 복원됩니다.')
            return redirect('manager:backup_restore', name=name)
        try:
            safety = bk.restore_backup(db_path(), backup_dir(), name, user=request.user.get_username())
        except Exception as e:
            messages.error(request, f'복원 실패: {e}')
            return redirect('manager:backups')
        for c in connections.all():
            c.close()
        messages.success(request, f'{item["created"]} 시점으로 복원했습니다. (복원 직전 상태는 {safety} 로 백업됨)')
        return redirect('manager:backups')
    return render(request, 'manager/backup_restore.html', {'item': item, 'later': later, 'later_batches': later_batches})


def _parse(s):
    try:
        return timezone.make_aware(datetime.strptime(s, '%Y-%m-%d %H:%M:%S'))
    except Exception:
        return timezone.make_aware(datetime(1970, 1, 1))


# ---------------------------------------------------------------- 점수 기준
def _svc():
    from player import services
    return services


def _defaults():
    s = _svc()
    return {
        'min': {'best11': s.BEST11_MIN_MINUTES, 'formation': s.FORMATION_MIN_MINUTES},
        'weights': {'FW': dict(s.FW_WEIGHTS), 'MF': dict(s.MF_WEIGHTS), 'DF': dict(s.DF_WEIGHTS), 'GK': dict(s.GK_WEIGHTS)},
    }


def _current():
    d, saved = _defaults(), config.load_saved()
    cur = {'min': dict(d['min']), 'weights': {p: dict(w) for p, w in d['weights'].items()}}
    cur['min'].update({k: int(v) for k, v in saved.get('min', {}).items()})
    for p, w in saved.get('weights', {}).items():
        if p in cur['weights']:
            cur['weights'][p].update({k: float(v) for k, v in w.items() if k in cur['weights'][p]})
    return cur


def _parse_form(post, base):
    """폼 → 설정. (설정, 오류목록)"""
    errors, out = [], {'min': {}, 'weights': {}}
    for key, label in (('best11', 'BEST11 최소 출전시간'), ('formation', '포메이션 최소 출전시간')):
        try:
            v = int(post.get(f'min_{key}', ''))
            if not 0 <= v <= 5000:
                raise ValueError
            out['min'][key] = v
        except ValueError:
            errors.append(f'{label}은 0~5000 사이 정수여야 합니다.')
    if not errors and out['min']['best11'] < out['min']['formation']:
        errors.append('BEST11 최소 출전시간이 포메이션 최소 출전시간보다 작을 수 없습니다.')
    for p in config.POSITIONS:
        out['weights'][p] = {}
        for k in base['weights'][p]:
            raw = post.get(f'w_{p}_{k}', '').strip()
            try:
                v = float(raw)
                if v < 0:
                    raise ValueError
            except ValueError:
                errors.append(f'{p} · {config.METRIC_LABELS[p].get(k, k)}: 0 이상의 숫자를 넣어주세요. (입력값: "{raw}")')
                continue
            out['weights'][p][k] = v
        if not errors and sum(out['weights'][p].values()) <= 0:
            errors.append(f'{p}: 가중치 합이 0입니다. 하나 이상은 0보다 커야 합니다.')
    if not errors and post.get('normalize'):
        for p in config.POSITIONS:
            t = sum(out['weights'][p].values())
            out['weights'][p] = {k: round(v * 100 / t, 2) for k, v in out['weights'][p].items()}
    return out, errors


def _best11_names(cfg, formation):
    svc = _svc()
    with config.override(cfg):
        r = svc.get_filtered_best11(team_id='', formation=formation)
    return {pos: [(row['player'].id, row['player'].name, row['player'].team.team_name, row['score'])
                  for row in rows] for pos, rows in r['best11'].items()}


def _diff_best11(before, after):
    out = []
    for pos in ('FW', 'MF', 'DF', 'GK'):
        b = {x[0]: x for x in before.get(pos, [])}
        a = {x[0]: x for x in after.get(pos, [])}
        out.append(dict(pos=pos, rows=[dict(id=i, name=x[1], team=x[2], score=x[3], new=i not in b) for i, x in a.items()],
                        left=[dict(name=x[1], team=x[2]) for i, x in b.items() if i not in a]))
    return out


@admin_only
def scoring(request):
    d, cur = _defaults(), _current()
    patched = hasattr(_svc(), 'get_weights')
    formation = request.POST.get('formation') or request.GET.get('formation') or '4-3-3'
    ctx = dict(defaults=d, labels=config.METRIC_LABELS, patched=patched, formation=formation,
               formations=list(_svc().FORMATIONS.keys()), logs=ScoreConfigLog.objects.all()[:15])
    form = cur
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reset':
            before = config.load_saved()
            obj = ScoreConfig.objects.first()
            if obj:
                obj.data = {k: v for k, v in obj.data.items() if k not in ('min', 'weights')}
                obj.save()
            ScoreConfigLog.objects.create(created_by=request.user.get_username(), summary='점수 기준을 기본값으로 되돌림',
                                          before=before, after=config.load_saved())
            messages.success(request, '기본값으로 되돌렸습니다.')
            return redirect('manager:scoring')
        form, errors = _parse_form(request.POST, d)
        if errors:
            ctx['errors'] = errors
            c = _current()
            form = {'min': {**c['min'], **form['min']},
                    'weights': {p: {**c['weights'][p], **form['weights'].get(p, {})} for p in c['weights']}}
        else:
            before_names = _best11_names({k: v for k, v in config.load_saved().items() if k in ('min', 'weights')} or {}, formation)
            after_names = _best11_names(form, formation)
            if action == 'save':
                obj = ScoreConfig.objects.first() or ScoreConfig(data={})
                before = dict(obj.data)
                obj.data = {**obj.data, 'min': form['min'], 'weights': form['weights']}
                obj.save()
                changed = sum(1 for p in config.POSITIONS for k, v in form['weights'][p].items() if v != d['weights'][p][k])
                ScoreConfigLog.objects.create(created_by=request.user.get_username(),
                                              summary=f'최소시간 {form["min"]["best11"]}/{form["min"]["formation"]}분, 기본값과 다른 가중치 {changed}개',
                                              before=before, after=obj.data)
                messages.success(request, '저장했습니다. 지금부터 BEST11 화면에 적용됩니다.' if patched else
                                 '저장했습니다. 단, patch_services 를 아직 안 해서 BEST11 계산에는 반영되지 않습니다.')
                return redirect('manager:scoring')
            ctx['preview'] = _diff_best11(before_names, after_names)      # 미리보기
    ctx['form'] = form
    ctx['rows'] = [dict(pos=p, items=[dict(key=k, label=config.METRIC_LABELS[p].get(k, k), default=d['weights'][p][k],
                                           value=form['weights'][p][k]) for k in d['weights'][p]],
                        total=sum(form['weights'][p].values())) for p in config.POSITIONS]
    return render(request, 'manager/scoring.html', ctx)


# ---------------------------------------------------------------- 제외 선수
def _snap(p):
    return f'{p.team.team_name} {p.name}'


@admin_only
def exclusions(request):
    initialized = config.exclusions_initialized()
    if request.method == 'POST':
        act, who = request.POST.get('action'), request.user.get_username()
        if act == 'init':
            ids = _svc().EXCLUDED_PLAYER_IDS
            for p in Player.objects.filter(id__in=ids).select_related('team'):
                BestExclusion.objects.get_or_create(player=p, defaults=dict(
                    reason='기존 services.py 제외 목록', snapshot=_snap(p), created_by=who))
            obj = ScoreConfig.objects.first() or ScoreConfig(data={})
            obj.data = {**obj.data, 'exclusions_initialized': True}
            obj.save()
            messages.success(request, '기존 제외 목록을 DB로 옮겼습니다. 이제 이 화면에서 관리합니다.')
        elif not initialized:
            messages.error(request, '먼저 "기존 목록 가져오기"를 눌러주세요.')
        elif act == 'add':
            p = Player.objects.filter(pk=request.POST.get('player') or 0).select_related('team').first()
            if p is None:
                messages.error(request, '선수를 찾을 수 없습니다.')
            else:
                BestExclusion.objects.get_or_create(player=p, defaults=dict(
                    reason=request.POST.get('reason', '')[:200], snapshot=_snap(p), created_by=who))
                messages.success(request, f'{_snap(p)} 제외했습니다.')
        elif act == 'remove':
            n, _ = BestExclusion.objects.filter(pk=request.POST.get('pk') or 0).delete()
            messages.success(request, '제외를 해제했습니다.' if n else '대상을 찾지 못했습니다.')
        return redirect('manager:exclusions')

    q = request.GET.get('q', '').strip()
    found = []
    if q:
        found = list(Player.objects.filter(name__contains=q).select_related('team')
                     .exclude(bestexclusion__isnull=False).order_by('team__team_name', 'name')[:30])
    ids = config.excluded_ids(_svc().EXCLUDED_PLAYER_IDS)
    current = (list(BestExclusion.objects.select_related('player__team')) if initialized else
               [dict(pk=None, player=p, snapshot=_snap(p), reason='services.py 기존 목록') for p in
                Player.objects.filter(id__in=ids).select_related('team')])
    # 제안: 2026 기록은 있는데 생년월일·사진이 모두 없는 선수 (임시 데이터 의심)
    exc = set(ids)
    suspects = [p for p in Player.objects.filter(playerstats__season=2026, birth_date__isnull=True, photo='')
                .select_related('team').distinct() if p.id not in exc][:30]
    return render(request, 'manager/exclusions.html', dict(initialized=initialized, current=current, q=q,
                                                          found=found, suspects=suspects))
