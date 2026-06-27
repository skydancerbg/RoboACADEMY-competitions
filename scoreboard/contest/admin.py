from django.contrib import admin
from .models import Run, Competition, Contest, Result, Team
from django.forms import TextInput, Textarea, NumberInput
import django.db


class Admin(admin.ModelAdmin):
    formfield_overrides = {
        django.db.models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 40})},
    }


class Inline(admin.TabularInline):
    show_change_link = True
    formfield_overrides = {
        django.db.models.TextField:   {'widget': TextInput(attrs={'style': 'width: 10em'})},
        django.db.models.CharField:   {'widget': TextInput(attrs={'style': 'width: 10em'})},
        django.db.models.FloatField:  {'widget': NumberInput(attrs={'style': 'width: 3em'})},
        django.db.models.IntegerField:{'widget': NumberInput(attrs={'style': 'width: 3em'})},
    }
    extra = 1


class ResultInline(Inline):
    model = Result


class RunInline(Inline):
    model = Run
    fields = ('team', 'start_time', 'duration', 'score', 'judge_comment', 'state', 'time_ms', 'penalty_time_ms', 'is_best')


class TeamInline(Inline):
    model = Team


class CompetitionAdmin(Admin):
    list_display  = ('name', 'contest', 'competition_type', 'state', 'status', 'num_runs', 'num_laps', 'timeout_seconds', 'lap_timer')
    list_filter   = ('competition_type', 'state', 'status')
    fields        = ('name', 'description', 'contest', 'competition_type', 'state', 'status',
                     'num_runs', 'num_laps', 'timeout_seconds', 'lap_timer', 'token')
    inlines       = [ResultInline, RunInline]


class ContestAdmin(Admin):
    list_display = ('name', 'status')
    fields       = ('name', 'description', 'status', 'points_table')
    inlines      = [TeamInline]


admin.site.register(Contest, ContestAdmin)
admin.site.register(Competition, CompetitionAdmin)
