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
    path('student/<int:pk>/', views.student_profile_view, name='student_profile'),
    path('student/<int:pk>/edit/', views.edit_student_view, name='edit_student'),
    # --- Finance Department ---
  

    # ... your other urls ...
    path('finance/', views.finance_view, name='finance'),
    path('finance/structure/add/', views.edit_fee_structure, name='add_fee_structure'),
    path('finance/structure/edit/<int:structure_id>/', views.edit_fee_structure, name='edit_fee_structure'),
    path('finance/download/<int:structure_id>/', views.download_fee_structure, name='download_fee_structure'),
    path('finance/history/', views.payment_history, name='payment_history'),
    path('finance/history/<int:student_id>/', views.payment_history, name='payment_history_student'),
    path('finance/fee-structure/', views.fee_structure_view, name='fee_structure'), 
    path('finance/record-payment/', views.record_payment, name='record_payment'),
    path('receipt/<int:payment_id>/', views.generate_receipt, name='generate_receipt'),
    path('finance/structure/print/<int:pk>/', views.print_fee_structure, name='print_fee_structure'),
    path('finance/print-transactions/', views.print_transactions, name='print_transactions'),


    # --- Examinations Department ---
    path('examinations/', views.examinations_view, name='examinations'),
    path('examinations/print-report/<int:student_id>/', views.print_student_report, name='print_student_report'),
    path('examinations/print-course/', views.print_course_results, name='print_course_results'),
    # --- Stores Department ---
    path('stores/', views.stores_view, name='stores'),
    path('stores/print/<str:report_type>/', views.print_inventory, name='print_inventory'),
   
    path('stores/edit/<str:item_type>/<int:pk>/', views.edit_store_item, name='edit_store_item'),
    # --- CUSTOM ADMIN PANEL (User Management & Logs) ---
    path('admin-panel/', views.admin_management_view, name='admin_management'),
    path('admin-panel/approve/<int:user_id>/', views.approve_user, name='approve_user'),
    path('admin-panel/delete/<int:user_id>/', views.delete_user, name='delete_user'),
]