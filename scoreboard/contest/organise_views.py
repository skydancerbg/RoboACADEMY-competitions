from django import forms
from django.shortcuts import get_object_or_404, redirect, render

from .models import Competition, Contest, ContestRegistration, ItemStates, Team
from .views import organiser_required


@organiser_required
def organise_dashboard(request):
    contests = Contest.objects.exclude(status=ItemStates.DELETED).order_by('-id')
    return render(request, 'contest/organise/dashboard.html', {'contests': contests})


class ContestForm(forms.ModelForm):
    class Meta:
        model  = Contest
        fields = ['name', 'description', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


@organiser_required
def organise_contest_new(request):
    form = ContestForm(request.POST or None)
    if form.is_valid():
        contest = form.save()
        return redirect('contest:organise_contest', contest_id=contest.id)
    return render(request, 'contest/organise/contest_form.html', {'form': form, 'action': 'Create'})


@organiser_required
def organise_contest(request, contest_id):
    contest       = get_object_or_404(Contest, pk=contest_id)
    categories    = Competition.objects.filter(contest=contest)
    teams         = Team.objects.filter(contest=contest)
    registrations = (
        ContestRegistration.objects
        .filter(contest=contest)
        .select_related('user', 'team')
        .order_by('registered_at')
    )
    return render(request, 'contest/organise/contest_detail.html', {
        'contest': contest, 'categories': categories, 'teams': teams,
        'registrations': registrations,
    })


@organiser_required
def organise_contest_edit(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    form    = ContestForm(request.POST or None, instance=contest)
    if form.is_valid():
        form.save()
        return redirect('contest:organise_contest', contest_id=contest.id)
    return render(request, 'contest/organise/contest_form.html', {'form': form, 'action': 'Edit', 'contest': contest})


class TeamForm(forms.ModelForm):
    class Meta:
        model  = Team
        fields = ['name', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


@organiser_required
def organise_team_new(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    form    = TeamForm(request.POST or None)
    if form.is_valid():
        team = form.save(commit=False)
        team.contest = contest
        team.save()
        return redirect('contest:organise_contest', contest_id=contest.id)
    return render(request, 'contest/organise/team_form.html', {
        'form': form, 'contest': contest, 'action': 'Add',
    })


@organiser_required
def organise_team_edit(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    form = TeamForm(request.POST or None, instance=team)
    if form.is_valid():
        form.save()
        return redirect('contest:organise_contest', contest_id=team.contest.id)
    return render(request, 'contest/organise/team_form.html', {
        'form': form, 'contest': team.contest, 'action': 'Edit',
    })


@organiser_required
def organise_team_delete(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    contest_id = team.contest.id
    if request.method == 'POST':
        team.delete()
        return redirect('contest:organise_contest', contest_id=contest_id)
    return render(request, 'contest/organise/confirm_delete.html', {
        'object': team, 'back_url': f'/contest/organise/competition/{contest_id}/',
    })


class CategoryForm(forms.ModelForm):
    class Meta:
        model  = Competition
        fields = ['name', 'description', 'competition_type', 'status',
                  'num_runs', 'num_laps', 'timeout_seconds', 'lap_timer']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}


@organiser_required
def organise_category_new(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    form    = CategoryForm(request.POST or None)
    if form.is_valid():
        cat = form.save(commit=False)
        cat.contest = contest
        cat.save()
        return redirect('contest:organise_contest', contest_id=contest.id)
    return render(request, 'contest/organise/category_form.html', {
        'form': form, 'contest': contest, 'action': 'Add',
    })


@organiser_required
def organise_category_edit(request, category_id):
    cat  = get_object_or_404(Competition, pk=category_id)
    form = CategoryForm(request.POST or None, instance=cat)
    if form.is_valid():
        form.save()
        return redirect('contest:organise_contest', contest_id=cat.contest.id)
    return render(request, 'contest/organise/category_form.html', {
        'form': form, 'contest': cat.contest, 'action': 'Edit',
    })
