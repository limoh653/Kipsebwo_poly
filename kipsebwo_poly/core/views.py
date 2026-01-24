from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db import transaction, models
from decimal import Decimal
from .models import *
from .forms import *
from django.contrib import messages

# --- AUTH & REDIRECT LOGIC ---

class CustomLoginView(LoginView):
    """
    Checks if an account exists but is inactive, showing a warning
    message specifically for users waiting for admin approval.
    """
    template_name = 'registration/login.html'
    
    def form_invalid(self, form):
        username = form.cleaned_data.get('username')
        user = User.objects.filter(username=username).first()
        
        if user and not user.is_active:
            messages.warning(self.request, "Your account is pending administrator approval. Please wait until it is activated.")
        return super().form_invalid(form)

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

@login_required
def redirect_after_login(request):
    """
    Traffic controller: Now sends EVERYONE (Admins and Staff) 
    directly to the custom dashboard instead of the Django backend.
    """
    return redirect('dashboard')

def register_view(request):
    """
    Registers users as 'Inactive' (is_active=False).
    Shows a success message directing them to wait for approval.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  
            user.save()
            AuditTrail.objects.create(user=user, action="Registered (Pending Approval)")
            messages.success(request, "Registration successful! Please wait for Admin approval before logging in.")
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

# --- ADMISSIONS DEPT ---

@login_required
def admissions_view(request):
    students_list = Student.objects.all()
    search_query = request.GET.get('search', '')
    gender_filter = request.GET.get('gender', '')
    
    if search_query:
        students_list = students_list.filter(
            models.Q(name__icontains=search_query) | 
            models.Q(admission_number__icontains=search_query)
        )
    if gender_filter:
        students_list = students_list.filter(sex=gender_filter)

    courses = Student.objects.values_list('course', flat=True).distinct()
    grouped_students = {course: students_list.filter(course=course) for course in courses}

    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            AuditTrail.objects.create(user=request.user, action=f"Admitted student: {student.name}")
            return redirect('admissions')
    else:
        form = StudentForm()
    
    context = {'grouped_students': grouped_students, 'form': form, 'search_query': search_query}
    return render(request, 'admissions.html', context)

# --- FINANCE DEPT ---

@login_required
def finance_view(request):
    if request.method == 'POST' and 'add_structure' in request.POST:
        form = FeeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance')
    else:
        form = FeeForm()

    search_query = request.GET.get('search', '')
    students_list = Student.objects.all().select_related('feebalance')
    
    if search_query:
        students_list = students_list.filter(
            models.Q(name__icontains=search_query) | 
            models.Q(admission_number__icontains=search_query)
        )

    courses = FeeStructure.objects.values_list('course', flat=True).distinct()
    finance_grouped = {course: students_list.filter(course=course) for course in courses}
    recent_payments = Payment.objects.all().order_by('-date')[:10]
    structures = FeeStructure.objects.all()
    
    context = {
        'finance_grouped': finance_grouped,
        'structures': structures,
        'form': form,
        'search_query': search_query,
        'recent_payments': recent_payments 
    }
    return render(request, 'finance.html', context)

@login_required
def process_payment(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    balance, created = FeeBalance.objects.get_or_create(student=student)
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        semester = request.POST.get('semester')
        transaction_id = request.POST.get('transaction_id', '') 
        
        with transaction.atomic():
            new_payment = Payment.objects.create(
                student=student, amount=amount, semester=semester, transaction_id=transaction_id
            )
            if semester == '1': balance.sem1_bal -= amount
            elif semester == '2': balance.sem2_bal -= amount
            elif semester == '3': balance.sem3_bal -= amount
            balance.save()
            
            AuditTrail.objects.create(user=request.user, action=f"Payment {amount} for {student.name}")
            return redirect('print_receipt', payment_id=new_payment.id)
        
    return render(request, 'make_payment.html', {'student': student, 'balance': balance})

@login_required
def print_receipt(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    return render(request, 'receipt_print.html', {'payment': payment})

@login_required
def payment_history(request):
    payments = Payment.objects.all().order_by('-date')
    return render(request, 'payment_history.html', {'payments': payments})

@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    payments = Payment.objects.filter(student=student).order_by('-date')
    return render(request, 'student_detail.html', {'student': student, 'payments': payments})

@login_required
def delete_student(request, pk):
    if request.user.is_superuser:
        student = get_object_or_404(Student, pk=pk)
        AuditTrail.objects.create(user=request.user, action=f"Deleted student: {student.name}")
        student.delete()
    return redirect('admissions')

# --- EXAMINATIONS ---

# --- EXAMINATIONS ---

@login_required
def examinations_view(request):
    query = request.GET.get('q')
    student = None
    if query:
        student = Student.objects.filter(admission_number=query).first()
        exams = Examination.objects.filter(student=student).order_by('year_of_study', 'semester', 'subject_name') if student else Examination.objects.none()
    else:
        exams = Examination.objects.all().select_related('student').order_by('student__course', 'year_of_study', 'semester', 'student__name')

    if request.method == 'POST':
        # 1. Handle Deletion Logging
        if 'delete_id' in request.POST:
            exam_to_delete = get_object_or_404(Examination, id=request.POST.get('delete_id'))
            student_name = exam_to_delete.student.name
            subject = exam_to_delete.subject_name
            
            exam_to_delete.delete()
            
            # Create Audit Log for deletion
            AuditTrail.objects.create(
                user=request.user, 
                action=f"Deleted marks for {student_name} (Subject: {subject})"
            )
            
            messages.success(request, "Record deleted successfully.")
            return redirect('examinations')

        # 2. Handle Saving/Editing Logging
        instance_id = request.POST.get('instance_id')
        instance = Examination.objects.filter(id=instance_id).first() if instance_id else None
        form = ExaminationForm(request.POST, instance=instance)
        
        if form.is_valid():
            exam = form.save()
            
            # Create Audit Log for adding/editing
            action_type = "Updated" if instance_id else "Recorded"
            AuditTrail.objects.create(
                user=request.user, 
                action=f"{action_type} marks for {exam.student.name} (Subject: {exam.subject_name})"
            )
            
            messages.success(request, "Marks saved successfully.")
            return redirect('examinations')
    else:
        edit_id = request.GET.get('edit')
        instance = Examination.objects.filter(id=edit_id).first() if edit_id else None
        form = ExaminationForm(instance=instance)

    return render(request, 'examinations.html', {'form': form, 'exams': exams, 'student': student, 'query': query})
# --- STORES ---
@login_required
def stores_view(request):
    consumables = Consumable.objects.all()
    equipment = PermanentEquipment.objects.all()
    
    # Initialize forms
    c_form = ConsumableForm()
    e_form = EquipmentForm()

    if request.method == 'POST':
        # Handle Consumable Submission
        if 'add_consumable' in request.POST:
            c_form = ConsumableForm(request.POST)
            if c_form.is_valid():
                item = c_form.save(commit=False)
                item.added_by = request.user
                item.save()
                AuditTrail.objects.create(user=request.user, action=f"Added Consumable: {item.item_name}")
                messages.success(request, "Consumable added successfully")
                return redirect('stores')

        # Handle Equipment Submission
        elif 'add_equipment' in request.POST:
            e_form = EquipmentForm(request.POST)
            if e_form.is_valid():
                item = e_form.save(commit=False)
                item.added_by = request.user
                item.save()
                AuditTrail.objects.create(user=request.user, action=f"Added Equipment: {item.item_name}")
                messages.success(request, "Equipment added successfully")
                return redirect('stores')

    context = {
        'consumables': consumables,
        'equipment': equipment,
        'c_form': c_form,
        'e_form': e_form,
    }
    return render(request, 'stores.html', context)

# --- CRUD FUNCTIONALITIES ---

@login_required
def delete_store_item(request, item_type, pk):
    if item_type == 'consumable':
        item = get_object_or_404(Consumable, pk=pk)
    else:
        item = get_object_or_404(PermanentEquipment, pk=pk)
    
    item_name = item.item_name
    item.delete()
    AuditTrail.objects.create(user=request.user, action=f"Deleted {item_type}: {item_name}")
    messages.warning(request, f"{item_name} removed from inventory.")
    return redirect('stores')
# --- USER MANAGEMENT ---

@user_passes_test(lambda u: u.is_staff)
def admin_management_view(request):
    pending_users = User.objects.filter(is_active=False)
    active_users = User.objects.filter(is_active=True).exclude(id=request.user.id)
    logs = AuditTrail.objects.all().order_by('-timestamp')[:20]
    return render(request, 'admin_management.html', {
        'pending_users': pending_users,
        'active_users': active_users,
        'recent_logs': logs
    })

@user_passes_test(lambda u: u.is_staff)
def approve_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()
    AuditTrail.objects.create(user=request.user, action=f"Approved user: {user.username}")
    messages.success(request, f"{user.username} is now active.")
    return redirect('admin_management')

@user_passes_test(lambda u: u.is_staff)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    name = user.username
    user.delete()
    AuditTrail.objects.create(user=request.user, action=f"Deleted user: {name}")
    messages.warning(request, f"User {name} deleted.")
    return redirect('admin_management')