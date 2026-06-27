from contest.models import Result, Run, RunState
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

    _update_best_result(run)
    return True


def _update_best_result(run):
    """Mark is_best on the fastest completed run for this team+competition and upsert Result."""
    completed = list(
        Run.objects.filter(
            team=run.team,
            competition=run.competition,
            state=RunState.COMPLETED,
            time_ms__isnull=False,
        )
    )

    Run.objects.filter(
        team=run.team, competition=run.competition
    ).update(is_best=False)

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
