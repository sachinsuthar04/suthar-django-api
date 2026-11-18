from django.urls import path
from .views import DashboardAPI, HomeContentAPI, HomeSummaryAPI
from .views import VillageListAPI, AdminVillageListCreateAPI, AdminVillageDetailAPI

urlpatterns = [
    path('dashboard/', DashboardAPI.as_view(), name='dashboard'),
    path('home-content/', HomeContentAPI.as_view(), name='home-content'),
    path('summary/', HomeSummaryAPI.as_view(), name='home-summary'),
    path("villages/", VillageListAPI.as_view(), name="village-list"),
    path("admin/villages/", AdminVillageListCreateAPI.as_view(), name="admin-village-list"),
    path("admin/villages/<int:pk>/", AdminVillageDetailAPI.as_view(), name="admin-village-detail"),
    
]
