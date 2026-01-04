from django.urls import path
from .views import DashboardAPI, HomeContentAPI
from .views import VillageListAPI

urlpatterns = [
    path('dashboard/', DashboardAPI.as_view(), name='dashboard'),
    path('home-content/', HomeContentAPI.as_view(), name='home-content'),
    path("villages/", VillageListAPI.as_view(), name="village-list"),
    
]
