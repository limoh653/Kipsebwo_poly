from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from decimal import Decimal
from .models import *
from .forms import *
from django.contrib import messages

# --- AUTH & DASHBOARD ---

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})

# --- ADMISSIONS DEPT (GROUPED BY COURSE) ---

@login_required
def admissions_view(request):
    # Base queryset
    students_list = Student.objects.all()
    
    # Filtering Logic
    search_query = request.GET.get('search', '')
    gender_filter = request.GET.get('gender', '')
    
    if search_query:
        students_list = students_list.filter(
            models.Q(name__icontains=search_query) | 
            models.Q(admission_number__icontains=search_query)
        )
    if gender_filter:
        students_list = students_list.filter(sex=gender_filter)

    # Grouping students by course for the display
    # We get unique courses from the Student table
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
    
    context = {
        'grouped_students': grouped_students, 
        'form': form,
        'search_query': search_query
    }
    return render(request, 'admissions.html', context)

# --- FINANCE DEPT (FEE MANAGEMENT & PAYMENTS) ---


@login_required
def finance_view(request):
    # 1. Handle Fee Structure Creation
    if request.method == 'POST' and 'add_structure' in request.POST:
        form = FeeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('finance')
    else:
        form = FeeForm()

    # 2. Prepare Grouped Finance Data
    search_query = request.GET.get('search', '')
    students_list = Student.objects.all().select_related('feebalance')
    
    if search_query:
        students_list = students_list.filter(
            models.Q(name__icontains=search_query) | 
            models.Q(admission_number__icontains=search_query)
        )

    courses = FeeStructure.objects.values_list('course', flat=True).distinct()
    finance_grouped = {course: students_list.filter(course=course) for course in courses}
    
    # 3. Get recent payments for the dashboard summary
    recent_payments = Payment.objects.all().order_by('-date')[:10]

    structures = FeeStructure.objects.all()
    
    context = {
        'finance_grouped': finance_grouped,
        'structures': structures,
        'form': form,
        'search_query': search_query,
        'recent_payments': recent_payments # Added for dashboard visibility
    }
    return render(request, 'finance.html', context)

@login_required
def process_payment(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    # Get or create balance to prevent 404 if a student record exists without a balance record
    balance, created = FeeBalance.objects.get_or_create(student=student)
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        semester = request.POST.get('semester')
        transaction_id = request.POST.get('transaction_id', '') # Capture ref if provided
        
        with transaction.atomic():
            # Record the payment
            new_payment = Payment.objects.create(
                student=student, 
                amount=amount, 
                semester=semester,
                transaction_id=transaction_id
            )
            
            # Update the specific semester balance
            if semester == '1':
                balance.sem1_bal -= amount
            elif semester == '2':
                balance.sem2_bal -= amount
            elif semester == '3':
                balance.sem3_bal -= amount
            
            balance.save()
            
            AuditTrail.objects.create(
                user=request.user, 
                action=f"Payment of {amount} for {student.name} (Sem {semester})"
            )
            
            # After payment, redirect to the receipt for printing
            return redirect('print_receipt', payment_id=new_payment.id)
        
    return render(request, 'make_payment.html', {'student': student, 'balance': balance})

@login_required
def print_receipt(request, payment_id):
    """View to display a printable receipt"""
    payment = get_object_or_404(Payment, id=payment_id)
    return render(request, 'receipt_print.html', {'payment': payment})

@login_required
def payment_history(request):
    """View to show all payments made in the system"""
    payments = Payment.objects.all().order_by('-date')
    return render(request, 'payment_history.html', {'payments': payments})

@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    # Fetch payment history for this specific student
    payments = Payment.objects.filter(student=student).order_by('-date')
    return render(request, 'student_detail.html', {'student': student, 'payments': payments})

@login_required
def delete_student(request, pk):
    if request.user.is_superuser:
        student = get_object_or_404(Student, pk=pk)
        AuditTrail.objects.create(user=request.user, action=f"Deleted student: {student.name}")
        student.delete()
    return redirect('admissions')

@login_required
def examinations_view(request):
    query = request.GET.get('q')
    student = None
    
    # 1. HANDLE SEARCH & ORDERING
    if query:
        student = Student.objects.filter(admission_number=query).first()
        if student:
            # Order by Year and Semester for a single student search
            exams = Examination.objects.filter(student=student).order_by(
                'year_of_study', 
                'semester', 
                'subject_name'
            )
        else:
            exams = Examination.objects.none()
    else:
        # FIX: We use 'student__course' because 'course' is a CharField in Student
        # We also removed select_related('student__course') which caused the error
        exams = Examination.objects.all().select_related('student').order_by(
            'student__course',  # Group level 1 (Text field)
            'year_of_study',    # Group level 2
            'semester',         # Group level 3
            'student__name'     # Final sort
        )

    # 2. HANDLE POST (SAVE/UPDATE/DELETE)
    if request.method == 'POST':
        # Handle Delete
        if 'delete_id' in request.POST:
            exam_to_delete = get_object_or_404(Examination, id=request.POST.get('delete_id'))
            exam_to_delete.delete()
            messages.success(request, "Record deleted successfully.")
            return redirect('examinations')

        # Handle Add/Edit
        instance_id = request.POST.get('instance_id')
        instance = Examination.objects.filter(id=instance_id).first() if instance_id else None
        form = ExaminationForm(request.POST, instance=instance)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Marks saved successfully.")
            return redirect('examinations')
    else:
        # Handle Edit Link (GET request with ?edit=ID)
        edit_id = request.GET.get('edit')
        instance = Examination.objects.filter(id=edit_id).first() if edit_id else None
        form = ExaminationForm(instance=instance)

    context = {
        'form': form,
        'exams': exams,
        'student': student,
        'query': query
    }
    return render(request, 'examinations.html', context)
def stores_view(request):
    items = StoreItem.objects.all()
    if request.method == 'POST':
        form = StoreForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('stores')
    else:
        form = StoreForm()
    return render(request, 'stores.html', {'items': items, 'form': form})