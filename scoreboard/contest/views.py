import collections
import json

from django.core.exceptions import BadRequest, PermissionDenied, ValidationError
from django.db.models import Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Competition, CompetitionType, Contest, ItemStates, Result, Run, RunState, Team,
)


def index(request):
    contests = list(Contest.objects.all())
    active_contests = filter(lambda x: x.status == ItemStates.OPEN, contests)
    past_contests   = filter(lambda x: x.status == ItemStates.CLOSED, contests)
    return render(request, 'contest/index.html', {
        'active_contests': active_contests,
        'past_contests': past_contests,
    })


def contest_competitions(request, contest_id):
    contest      = Contest.objects.get(pk=contest_id)
    competitions = Competition.objects.filter(contest_id=contest_id, status__in=['OPEN', 'CLOSED'])
    teams        = Team.objects.filter(contest_id=contest_id)

    over    = collections.defaultdict(dict)
    running = collections.defaultdict(dict)

    for team in teams:
        for result in team.result_set.all():
            over[team.id][result.competition.id] = result.score

    for competition in competitions:
        if competition.status != 'OPEN':
            continue
        pr = Run.objects.values('team_id').annotate(max_score=Max('score')).filter(competition_id=competition.id)
        for r in pr:
            running[r['team_id']][competition.id] = r['max_score']

    table = []
    for team in teams:
        line = []
        for competition in competitions:
            if competition.id in over[team.id] and competition.status == 'CLOSED':
                line.append(over[team.id][competition.id])
            elif competition.id in running[team.id] and competition.status == 'OPEN':
                line.append(running[team.id][competition.id])
            else:
                line.append(None)
        table.append({'team': team, 'results': line})

    return render(request, 'contest/competitions.html', {
        'contest': contest,
        'teams': teams,
        'competitions': competitions,
        'table': table,
    })


def contest_team(request, team_id):
    team = Team.objects.get(pk=team_id)
    return render(request, 'contest/teams.html', {
        'contest': team.contest,
        'team': team,
        'competitions': [],
    })


def competition_board(request, competition_id):
    try:
        competition = Competition.objects.get(pk=competition_id)
    except Competition.DoesNotExist:
        raise Http404('Competition does not exist')

    results = Result.objects.filter(competition_id=competition_id).order_by('score').select_related('team')
    runs    = Run.objects.filter(competition_id=competition_id).order_by('team__name', 'start_time').select_related('team')

    if competition.competition_type == CompetitionType.TIMED:
        preliminary_results = _timed_preliminary(competition_id)
    else:
        preliminary_results = _judged_preliminary(competition_id)

    teams           = Team.objects.filter(contest=competition.contest)
    run_counts      = {t.id: runs.filter(team=t).count() for t in teams}
    available_teams = [t for t in teams if run_counts[t.id] < competition.num_runs]

    return render(request, 'contest/competition_board.html', {
        'contest': competition.contest,
        'competition': competition,
        'runs': runs,
        'preliminary_results': preliminary_results,
        'results': results,
        'available_teams': available_teams,
    })


def _timed_preliminary(competition_id):
    best_runs = Run.objects.filter(
        competition_id=competition_id,
        state=RunState.COMPLETED,
        is_best=True,
        time_ms__isnull=False,
    ).select_related('team').order_by('time_ms')
    results = []
    for run in best_runs:
        total = (run.time_ms or 0) + run.penalty_time_ms
        results.append({'team_id': run.team.id, 'team_name': run.team.name, 'best_time_ms': total})
    return results


def _judged_preliminary(competition_id):
    pr = (
        Run.objects
        .filter(competition_id=competition_id, state=RunState.COMPLETED, score__isnull=False)
        .values('team_id')
        .annotate(max_score=Max('score'))
        .order_by('-max_score')
    )
    results = []
    for r in pr:
        tn = Team.objects.get(id=r['team_id'])
        results.append({'team_id': r['team_id'], 'team_name': tn.name, 'max_score': r['max_score']})
    return results


# ── Judge run actions ──────────────────────────────────────────────────────────

@require_POST
def run_create(request, competition_id):
    """Create a PENDING run for a team."""
    competition = get_object_or_404(Competition, pk=competition_id)
    team_id = request.POST.get('team_id')
    team    = get_object_or_404(Team, pk=team_id, contest=competition.contest)

    run_count = Run.objects.filter(team=team, competition=competition).count()
    if run_count >= competition.num_runs:
        return JsonResponse({'error': 'Run limit reached for this team'}, status=400)

    Run.objects.create(
        team=team,
        competition=competition,
        start_time=timezone.now(),
        duration=0,
        state=RunState.PENDING,
    )
    return redirect('contest:competition_board', competition_id=competition_id)


@require_POST
def run_start(request, run_id):
    """Activate a PENDING run. Publishes MQTT START for TIMED competitions only."""
    run = get_object_or_404(Run.objects.select_related('competition'), pk=run_id)

    if run.state != RunState.PENDING:
        return JsonResponse({'error': f'Run is {run.state}, expected PENDING'}, status=400)

    run.state      = RunState.ACTIVE
    run.start_time = timezone.now()
    run.save(update_fields=['state', 'start_time'])

    if run.competition.competition_type == CompetitionType.TIMED:
        try:
            from mqtt_bridge.publisher import publish_competition_command
            publish_competition_command(run.competition.id, 'START', run_id=run.id)
        except Exception:
            pass

    return JsonResponse({'status': 'started', 'run_id': run.id})


@require_POST
def run_stop(request, run_id):
    """Void an ACTIVE run. Publishes MQTT STOP for TIMED competitions only."""
    run = get_object_or_404(Run.objects.select_related('competition'), pk=run_id)

    if run.state != RunState.ACTIVE:
        return JsonResponse({'error': f'Run is {run.state}, expected ACTIVE'}, status=400)

    run.state = RunState.VOIDED
    run.save(update_fields=['state'])

    if run.competition.competition_type == CompetitionType.TIMED:
        try:
            from mqtt_bridge.publisher import publish_competition_command
            publish_competition_command(run.competition.id, 'STOP')
        except Exception:
            pass

    return JsonResponse({'status': 'voided', 'run_id': run.id})


@require_POST
def run_score(request, run_id):
    """Submit a judge's score for a JUDGED run. Marks it COMPLETED and updates best result."""
    run = get_object_or_404(Run.objects.select_related('competition'), pk=run_id)

    if run.competition.competition_type != CompetitionType.JUDGED:
        return JsonResponse({'error': 'Score entry is only for JUDGED runs'}, status=400)

    if run.state not in (RunState.PENDING, RunState.ACTIVE):
        return JsonResponse({'error': f'Run is {run.state}, cannot score'}, status=400)

    try:
        score = int(request.POST.get('score', ''))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid score value'}, status=400)

    if not 1 <= score <= 100:
        return JsonResponse({'error': 'Score must be between 1 and 100'}, status=400)

    comment = request.POST.get('comment', '').strip()[:200]

    from scoring.engine import score_judged_run
    score_judged_run(run, score, comment)

    return redirect('contest:competition_board', competition_id=run.competition.id)


# ── Legacy robot API ───────────────────────────────────────────────────────────

def robot_action(request):
    from datetime import datetime
    req = {}
    if request.method != 'POST':
        raise BadRequest()
    try:
        req = json.loads(request.body)
    except Exception:
        raise BadRequest()
    if 'teamtoken' not in req or 'competitiontoken' not in req or 'action' not in req:
        raise ValidationError()
    if req['action'] not in {'start', 'stop'}:
        raise ValidationError()

    team        = Team.objects.get(token=req['teamtoken'])
    competition = Competition.objects.get(token=req['competitiontoken'])
    if team is None or competition is None:
        raise PermissionDenied()

    runs       = Run.objects.filter(team_id=team.id, competition_id=competition.id).order_by('-start_time')[:1]
    is_running = False
    last_run   = None
    response   = 'error'

    if len(runs) == 1:
        last_run = runs[0]
        if last_run.duration == 0:
            is_running = True

    if req['action'] == 'start':
        if is_running:
            response = 'already_running'
        else:
            run = Run(start_time=datetime.now(), team=team, competition=competition, duration=0)
            run.save()
            response = 'started: ' + run.start_time.isoformat()
    if req['action'] == 'stop':
        if is_running:
            duration = (datetime.now() - last_run.start_time).total_seconds()
            last_run.duration = duration
            last_run.save()
            response = 'end: ' + str(duration)
        else:
            response = 'not_running'

    return JsonResponse({'result': response})
