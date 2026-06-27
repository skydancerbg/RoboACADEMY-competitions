from django.urls import path

from contest.consumers import CompetitionConsumer

websocket_urlpatterns = [
    path('ws/competition/<int:competition_id>/', CompetitionConsumer.as_asgi()),
]
