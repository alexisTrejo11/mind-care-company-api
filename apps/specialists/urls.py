from django.urls import path
from . import views

urlpatterns = [
    # Specialist Management
    path('specialists/', views.SpecialistListView.as_view(), name='specialist-list'),
    path('specialists/<int:specialist_id>/', views.SpecialistDetailView.as_view(), name='specialist-detail'),
    path('specialists/create/', views.SpecialistCreateView.as_view(), name='specialist-create'),
    path('specialists/<int:specialist_id>/update/', views.SpecialistUpdateView.as_view(), name='specialist-update'),
    
    
    # Disponibility
    path('specialists/<int:specialist_id>/availability/', views.AvailabilityListView.as_view(), name='availability-list'),
    path('specialists/<int:specialist_id>/available-slots/', views.AvailableSlotsView.as_view(), name='available-slots'),
    
    # Services
    path('services/', views.ServiceListView.as_view(), name='service-list'),
    path('services/create/', views.ServiceCreateView.as_view(), name='service-create'),
    path('specialists/<int:specialist_id>/services/', views.SpecialistServicesView.as_view(), name='specialist-services'),
    
    # Scpecialist Profile
    path('specialists/me/', views.MySpecialistProfileView.as_view(), name='my-specialist-profile'),
]