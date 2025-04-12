from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views
from django.contrib.auth import views as auth_views

app_name = 'puzzle'
urlpatterns = [
    path('', views.index, name='index'),
    path('puzzles/', views.puzzles, name='puzzles'),
    path('puzzle/<int:puzzle_id>/', views.puzzle_detail, name='detail'),
    path('puzzle/<int:puzzle_id>/solve/', views.solve_puzzle, name='solve'),
    path('puzzle/<int:puzzle_id>/submit/', views.submit_solution, name='submit'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
    path('process-voice-input/', views.process_voice_input, name='process_voice_input'),
    path('save-session-history/', views.save_session_history, name='save_session_history'),
    path('chat/', views.chat, name='chat'),
    path('ai-chat/', views.chat, name='ai_chat'),
    path('roadmap/', views.roadmap_view, name='roadmap'),  # Single view for roadmap network
]