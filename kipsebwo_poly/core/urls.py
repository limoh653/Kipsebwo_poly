from django.urls import path
from django.contrib.auth import views as auth_views # Added for login/logout
from . import views

urlpatterns = [
    # --- Authentication ---
    # We define 'login/' so that LOGOUT_REDIRECT_URL = 'login' works
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
    
    # --- General ---
    path('', views.dashboard, name='dashboard'),
    
    # --- Admissions Department ---
    path('admissions/', views.admissions_view, name='admissions'),
    path('admissions/student/<int:pk>/', views.student_detail, name='student_detail'),
    path('admissions/delete/<int:pk>/', views.delete_student, name='delete_student'),
    
    # --- Finance Department ---
    path('finance/', views.finance_view, name='finance'),
    path('finance/pay/<int:student_id>/', views.process_payment, name='process_payment'),
    path('finance/receipt/<int:payment_id>/', views.print_receipt, name='print_receipt'),
    path('finance/history/', views.payment_history, name='payment_history'),
    
    # --- Examinations Department ---
    path('examinations/', views.examinations_view, name='examinations'),
    
    # --- Stores Department ---
    path('stores/', views.stores_view, name='stores'),
]