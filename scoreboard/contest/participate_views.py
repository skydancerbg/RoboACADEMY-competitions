from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Contest, ContestRegistration, ItemStates, Team


def _require_participant(request):
    return (
        request.user.is_authenticated
        and request.user.groups.filter(name='Participant').exists()
    )


@login_required
def participate_dashboard(request):
    if not _require_participant(request):
        return redirect('contest:index')

    profile    = getattr(request.user, 'profile', None)
    my_regs    = (
        ContestRegistration.objects
        .filter(user=request.user)
        .select_related('contest', 'team')
        .order_by('-registered_at')
    )
    joined_ids    = set(my_regs.values_list('contest_id', flat=True))
    open_contests = (
        Contest.objects
        .filter(status=ItemStates.OPEN)
        .exclude(id__in=joined_ids)
        .order_by('name')
    )
    return render(request, 'contest/participate/dashboard.html', {
        'profile':       profile,
        'my_regs':       my_regs,
        'open_contests': open_contests,
    })


@login_required
def participate_join(request, contest_id):
    if not _require_participant(request):
        return redirect('contest:index')
    if request.method != 'POST':
        return redirect('contest:participate_dashboard')

    contest   = get_object_or_404(Contest, pk=contest_id, status=ItemStates.OPEN)
    profile   = getattr(request.user, 'profile', None)
    team_name = (profile.team_name if profile and profile.team_name
                 else request.user.username)

    # Idempotent — do nothing if already registered
    if not ContestRegistration.objects.filter(user=request.user, contest=contest).exists():
        team = Team.objects.create(name=team_name, contest=contest)
        ContestRegistration.objects.create(
            user=request.user, contest=contest, team=team
        )
    return redirect('contest:participate_dashboard')


@login_required
def participate_leave(request, contest_id):
    if not _require_participant(request):
        return redirect('contest:index')
    if request.method != 'POST':
        return redirect('contest:participate_dashboard')

    contest = get_object_or_404(Contest, pk=contest_id)
    reg = ContestRegistration.objects.filter(
        user=request.user, contest=contest
    ).select_related('team').first()

    if reg:
        if contest.status == ItemStates.OPEN:
            reg.team.delete()   # cascades to ContestRegistration via OneToOne
    return redirect('contest:participate_dashboard')
