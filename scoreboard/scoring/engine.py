from contest.models import Competition, CompetitionType, Result, Run, RunState, Team
from devices.models import LapEvent


def crossings_needed(run):
    """Number of beam crossings to complete a run: start crossing + N lap completions."""
    return run.competition.num_laps + 1


def assign_lap_event_to_active_run(lap_event):
    """
    Find the ACTIVE Run whose competition has this device as lap_timer.
    Assigns the LapEvent to that run and competition. Returns the Run or None.
    """
    device = lap_event.device
    try:
        run = Run.objects.select_related('competition').get(
            competition__lap_timer=device,
            state=RunState.ACTIVE,
        )
    except Run.DoesNotExist:
        return None
    except Run.MultipleObjectsReturned:
        return None

    lap_event.competition = run.competition
    lap_event.run = run
    lap_event.save(update_fields=['competition', 'run'])
    return run


def try_finalize_run(run):
    """
    If enough crossings have been recorded, calculate time_ms, mark COMPLETED,
    and update the best result. Returns True if the run was finalized.
    """
    events = list(LapEvent.objects.filter(run=run).order_by('timestamp_utc'))
    needed = crossings_needed(run)
    if len(events) < needed:
        return False

    start_ts  = events[0].timestamp_utc
    finish_ts = events[needed - 1].timestamp_utc
    elapsed_ms = int((finish_ts - start_ts).total_seconds() * 1000)

    run.time_ms = elapsed_ms
    run.state   = RunState.COMPLETED
    run.save(update_fields=['time_ms', 'state'])

    for i, ev in enumerate(events[:needed]):
        ev.lap_number = i
    LapEvent.objects.bulk_update(events[:needed], ['lap_number'])

    _update_best_timed_result(run)
    return True


def score_judged_run(run, score, comment=''):
    """Record a judge's score for a JUDGED run and update best result."""
    run.score         = score
    run.judge_comment = comment
    run.state         = RunState.COMPLETED
    run.save(update_fields=['score', 'judge_comment', 'state'])
    _update_best_judged_result(run)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _update_best_timed_result(run):
    """Mark is_best on the fastest completed TIMED run, upsert Result, refresh overall ranking."""
    completed = list(
        Run.objects.filter(
            team=run.team,
            competition=run.competition,
            state=RunState.COMPLETED,
            time_ms__isnull=False,
        )
    )
    Run.objects.filter(team=run.team, competition=run.competition).update(is_best=False)

    best = min(completed, key=lambda r: (r.time_ms or 0) + r.penalty_time_ms, default=None)
    if best:
        best.is_best = True
        best.save(update_fields=['is_best'])
        total = (best.time_ms or 0) + best.penalty_time_ms
        Result.objects.update_or_create(
            team=run.team,
            competition=run.competition,
            defaults={'score': total},
        )

    _update_overall_ranking(run.competition)


def _update_best_judged_result(run):
    """Mark is_best on the highest-scoring completed JUDGED run, upsert Result, refresh overall ranking."""
    completed = list(
        Run.objects.filter(
            team=run.team,
            competition=run.competition,
            state=RunState.COMPLETED,
            score__isnull=False,
        )
    )
    Run.objects.filter(team=run.team, competition=run.competition).update(is_best=False)

    best = max(completed, key=lambda r: r.score, default=None)
    if best:
        best.is_best = True
        best.save(update_fields=['is_best'])
        Result.objects.update_or_create(
            team=run.team,
            competition=run.competition,
            defaults={'score': best.score},
        )

    _update_overall_ranking(run.competition)


def _lookup_points(points_map, position):
    """Return points for a given position from the contest's points_map."""
    key = str(position)
    if key in points_map:
        return int(points_map[key])
    if 'default' in points_map:
        return int(points_map['default'])
    return 1


def _update_overall_ranking(competition):
    """Recalculate OverallResult for every team in this competition's contest."""
    from scoring.models import OverallResult

    contest = competition.contest
    all_categories = list(Competition.objects.filter(contest=contest))
    teams = list(Team.objects.filter(contest=contest))

    if not all_categories or not teams:
        return

    points_map = contest.points_table or {}

    # Build ordered team_id list per category (rank order)
    category_rankings = {}
    for cat in all_categories:
        if cat.competition_type == CompetitionType.TIMED:
            ordered = list(
                Result.objects.filter(competition=cat)
                .order_by('score')
                .values_list('team_id', flat=True)
            )
        else:
            ordered = list(
                Result.objects.filter(competition=cat)
                .order_by('-score')
                .values_list('team_id', flat=True)
            )
        category_rankings[cat.id] = ordered

    max_positions = len(teams)
    team_data = {}
    for team in teams:
        is_eligible = all(team.id in category_rankings[cat.id] for cat in all_categories)

        total_points = 0
        position_counts = [0] * max_positions

        if is_eligible:
            for cat in all_categories:
                ranking = category_rankings[cat.id]
                try:
                    pos = ranking.index(team.id) + 1  # 1-based
                    total_points += _lookup_points(points_map, pos)
                    if pos <= max_positions:
                        position_counts[pos - 1] += 1
                except ValueError:
                    pass

        team_data[team.id] = {
            'total_points': total_points,
            'is_eligible': is_eligible,
            'position_counts': position_counts,
        }

    # Upsert all OverallResult rows (rank=None until assigned below)
    for team in teams:
        data = team_data[team.id]
        OverallResult.objects.update_or_create(
            contest=contest,
            team=team,
            defaults={
                'total_points': data['total_points'],
                'is_eligible': data['is_eligible'],
                'rank': None,
            },
        )

    # Sort eligible teams: most total_points first; tie-break by most 1st-place finishes, then 2nd, etc.
    eligible = [t for t in teams if team_data[t.id]['is_eligible']]
    eligible.sort(key=lambda t: (
        -team_data[t.id]['total_points'],
        *[-c for c in team_data[t.id]['position_counts']],
    ))

    for rank, team in enumerate(eligible, start=1):
        OverallResult.objects.filter(contest=contest, team=team).update(rank=rank)


# Keep old name as alias so existing callers (signals) still work
_update_best_result = _update_best_timed_result
