from django.urls import path

from . import views

app_name = 'contest'

urlpatterns = [
    path('', views.index, name='index'),
    path('contest/<int:contest_id>', views.contest_competitions, name='contest_competitions'),
    path('contest/<int:contest_id>/ranking/', views.contest_ranking, name='contest_ranking'),
    path('team/<int:team_id>', views.contest_team, name='contest_team'),
    path('competition_board/<int:competition_id>', views.competition_board, name='competition_board'),
    path('competition/<int:competition_id>/run/create', views.run_create, name='run_create'),
    path('run/<int:run_id>/start', views.run_start, name='run_start'),
    path('run/<int:run_id>/stop', views.run_stop, name='run_stop'),
    path('run/<int:run_id>/score', views.run_score, name='run_score'),
    path('robot_action', views.robot_action),
]
