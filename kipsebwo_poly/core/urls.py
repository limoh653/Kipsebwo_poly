from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # --- Authentication & Redirection ---
    # UPDATED: Using views.CustomLoginView instead of auth_views.LoginView
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # This is the "Traffic Controller" URL
    path('check-user/', views.redirect_after_login, name='redirect_after_login'),
    
    # Use the register_view (which locks accounts by default)
    path('register/', views.register_view, name='register'),
    
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

    # --- CUSTOM ADMIN PANEL (User Management & Logs) ---
    path('admin-panel/', views.admin_management_view, name='admin_management'),
    path('admin-panel/approve/<int:user_id>/', views.approve_user, name='approve_user'),
    path('admin-panel/delete/<int:user_id>/', views.delete_user, name='delete_user'),
]