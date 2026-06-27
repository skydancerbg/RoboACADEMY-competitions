from django.db import models
from django.utils.translation import gettext_lazy as _

from smart_selects.db_fields import ChainedForeignKey


class ItemStates(models.TextChoices):
    NEW     = 'NEW',     _('In preparation')
    OPEN    = 'OPEN',    _('Open')
    CLOSED  = 'CLOSED',  _('Closed')
    DELETED = 'DELETED', _('Deleted')


class CompetitionType(models.TextChoices):
    TIMED  = 'TIMED',  _('Timed (hardware lap timer)')
    JUDGED = 'JUDGED', _('Judged (manual score entry)')


class CompetitionState(models.TextChoices):
    WAITING  = 'WAITING',  _('Waiting')
    READY    = 'READY',    _('Ready to start')
    RUNNING  = 'RUNNING',  _('Run in progress')
    FINISHED = 'FINISHED', _('Finished')


class RunState(models.TextChoices):
    PENDING   = 'PENDING',   _('Pending')
    ACTIVE    = 'ACTIVE',    _('In progress')
    COMPLETED = 'COMPLETED', _('Completed')
    VOIDED    = 'VOIDED',    _('Voided (MQTT lost)')
    MANUAL    = 'MANUAL',    _('Manual entry (fallback)')


class Contest(models.Model):
    name        = models.CharField(max_length=200, help_text='Name of the contest.')
    description = models.TextField(default='', blank=True, help_text='Short description, e.g. time and place.')
    status      = models.CharField(max_length=24, choices=ItemStates.choices, default=ItemStates.NEW)
    points_table = models.JSONField(
        default=dict, blank=True,
        help_text='Position to points mapping, e.g. {1:10,2:8,3:6,4:4,5:2}.'
    )

    class Meta:
        verbose_name        = 'Competition'
        verbose_name_plural = 'Competitions'

    def __str__(self):
        return self.name


class Team(models.Model):
    name        = models.CharField(max_length=200, help_text='Identifier of the team.')
    description = models.TextField(default='', blank=True, help_text='Team members and affiliation.')
    contest     = models.ForeignKey(Contest, on_delete=models.CASCADE, help_text='A team belongs to a contest.')
    token       = models.CharField(unique=True, null=True, max_length=200, default='', blank=True,
                                   help_text='Token for run submissions.')

    def __str__(self):
        return 'Team:{}@{}'.format(self.name, self.contest.name)


class Competition(models.Model):
    name        = models.CharField(max_length=200, help_text='Name of the category.')
    description = models.TextField(default='', blank=True, help_text='Rules of the competition and description of the task.')
    status      = models.CharField(max_length=24, choices=ItemStates.choices, default=ItemStates.NEW)
    contest     = models.ForeignKey(Contest, on_delete=models.CASCADE, help_text='Parent competition event.')
    runs        = models.ManyToManyField(Team, through='Run', related_name='runs',
                                         help_text='Teams that have runs in this category.')
    token       = models.CharField(unique=True, max_length=200, default='', blank=True,
                                   help_text='Token for run submissions.')
    competition_type = models.CharField(
        max_length=8, choices=CompetitionType.choices, default=CompetitionType.JUDGED,
        help_text='TIMED: scored by hardware lap timer. JUDGED: scored manually by a judge.'
    )
    state = models.CharField(
        max_length=10, choices=CompetitionState.choices, default=CompetitionState.WAITING,
        help_text='Current operational state of this category.'
    )
    num_laps = models.PositiveSmallIntegerField(
        default=1, help_text='Number of laps per run (TIMED only).'
    )
    timeout_seconds = models.PositiveSmallIntegerField(
        default=120, help_text='Run timeout in seconds (TIMED only).'
    )
    num_runs = models.PositiveSmallIntegerField(
        default=3, help_text='Maximum number of runs allowed per team.'
    )

    class Meta:
        verbose_name        = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return 'Competition:{}@{}'.format(self.name, self.contest.name)


class Result(models.Model):
    score       = models.IntegerField()
    comment     = models.TextField(default='', blank=True, help_text='Comment to the participation.')
    team        = models.ForeignKey(Team, on_delete=models.CASCADE)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('team', 'competition'),)

    def __str__(self):
        return 'Result:{}@{}'.format(self.team.name, self.competition.name)


class Run(models.Model):
    start_time    = models.DateTimeField()
    duration      = models.IntegerField(blank=True,
                                        help_text='Duration in whole seconds (legacy, kept for compatibility).')
    score         = models.IntegerField(blank=True, null=True, help_text='Assigned by a judge (JUDGED runs).')
    judge_comment = models.CharField(max_length=200, blank=True, help_text='Comment by a judge.')
    team          = models.ForeignKey(Team, on_delete=models.CASCADE, help_text='Who performed the run.')
    competition   = models.ForeignKey(Competition, on_delete=models.CASCADE, help_text='Source category.')
    state         = models.CharField(
        max_length=10, choices=RunState.choices, default=RunState.PENDING,
        help_text='Lifecycle state of this run.'
    )
    time_ms = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Elapsed time in milliseconds from hardware LapEvents (TIMED runs).'
    )
    penalty_time_ms = models.PositiveIntegerField(
        default=0, help_text='Penalty time in milliseconds added to time_ms.'
    )
    is_best = models.BooleanField(
        default=False,
        help_text='True if this is the team\'s best run in this category (denormalised for display speed).'
    )

    def __str__(self):
        return 'Run:{}@{}'.format(self.start_time, self.team.name)
