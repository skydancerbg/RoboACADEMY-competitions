from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Competition, CompetitionType, Contest, ItemStates, Run, RunState, Team


def _panel_context(competition):
    """Compute current panel state for a competition."""
    active_run = (
        Run.objects
        .filter(competition=competition, state__in=[RunState.PENDING, RunState.ACTIVE])
        .select_related('team')
        .first()
    )

    teams      = Team.objects.filter(contest=competition.contest).order_by('name')
    run_counts = {t.id: Run.objects.filter(team=t, competition=competition).count() for t in teams}
    available_teams = [t for t in teams if run_counts[t.id] < competition.num_runs]

    return {
        'competition':     competition,
        'active_run':      active_run,
        'available_teams': available_teams,
        'run_counts':      run_counts,
        'all_done':        not available_teams and active_run is None,
    }


@login_required
def judge_select(request):
    """Category selector — list of all OPEN categories across OPEN competitions."""
    categories = (
        Competition.objects
        .filter(contest__status=ItemStates.OPEN, status=ItemStates.OPEN)
        .select_related('contest')
        .order_by('contest__name', 'name')
    )
    return render(request, 'contest/judge_mobile/select.html', {'categories': categories})


@login_required
def judge_panel(request, competition_id):
    """Full panel page for one category."""
    competition = get_object_or_404(Competition, pk=competition_id)
    return render(request, 'contest/judge_mobile/panel.html', _panel_context(competition))


@login_required
def judge_panel_state(request, competition_id):
    """State fragment only — fetched by AJAX on WebSocket push."""
    competition = get_object_or_404(Competition, pk=competition_id)
    return render(request, 'contest/judge_mobile/state_fragment.html', _panel_context(competition))


@login_required
def judge_score(request, competition_id, run_id):
    """Score entry screen for JUDGED runs."""
    competition = get_object_or_404(Competition, pk=competition_id)
    run         = get_object_or_404(Run, pk=run_id, competition=competition)

    if competition.competition_type != CompetitionType.JUDGED:
        return redirect('contest:judge_panel', competition_id=competition_id)
    if run.state not in (RunState.ACTIVE, RunState.PENDING):
        return redirect('contest:judge_panel', competition_id=competition_id)

    if request.method == 'POST':
        score_raw = request.POST.get('score', '')
        try:
            score = int(score_raw)
        except (ValueError, TypeError):
            return render(request, 'contest/judge_mobile/score.html', {
                'competition': competition, 'run': run, 'error': 'Invalid score.'
            })
        if not 1 <= score <= 100:
            return render(request, 'contest/judge_mobile/score.html', {
                'competition': competition, 'run': run, 'error': 'Score must be 1–100.'
            })
        comment = request.POST.get('comment', '').strip()[:200]
        from scoring.engine import score_judged_run
        score_judged_run(run, score, comment)
        return redirect('contest:judge_panel', competition_id=competition_id)

    return render(request, 'contest/judge_mobile/score.html', {
        'competition': competition,
        'run':         run,
    })
