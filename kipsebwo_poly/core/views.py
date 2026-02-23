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
from django.core.exceptions import PermissionDenied
from .forms import RegistrationForm
from .models import UserProfile
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Q
from decimal import Decimal
from .forms import FeeForm  # Assuming your form is named FeeForm
from .forms import ExaminationForm, KnecPaymentForm  # Check if it's 'Knec' or 'KNEC'
from django.views.decorators.cache import never_cache
# 1. Access Control Decorator
def department_required(dept_name):
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # 1. THE SUPERUSER OVERRIDE
            # If the user is a superuser, they bypass all department checks.
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # 2. NORMAL USER CHECK
            profile = getattr(request.user, 'userprofile', None)
            
            # Check if they have a profile, match the dept, and are approved
            if profile and profile.department == dept_name and profile.is_approved:
                return view_func(request, *args, **kwargs)
            
            # 3. ACCESS DENIED
            raise PermissionDenied 
        return _wrapped_view
    return decorator

# 2. Registration View (Updated with Profile and Password Hashing)
def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # commit=False allows us to modify the user object before saving to DB
            user = form.save(commit=False)
            
            # Manually hash the password from the form
            user.set_password(form.cleaned_data['password'])
            
            # Keep user 'inactive' so they can't log in until Admin approves
            user.is_active = False 
            user.save()
            
            # Create the UserProfile with the chosen department
            selected_dept = form.cleaned_data.get('department')
            UserProfile.objects.create(
                user=user, 
                department=selected_dept,
                is_approved=False
            )
            
            # Create Audit Log
            AuditTrail.objects.create(user=user, action="Registered (Pending Approval)")
            
            return render(request, 'registration_pending.html', {'dept': selected_dept})
    else:
        form = RegistrationForm()
        
    return render(request, 'register.html', {'form': form})

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
    """Fallback dashboard if needed"""
    return render(request, 'dashboard.html')

@login_required
def redirect_after_login(request):
    """
    The RBAC Traffic Controller: 
    Checks the user's department and redirects them to their specific home page.
    """
    try:
        # Get the profile for the logged-in user
        profile = request.user.userprofile
        
        # 1. Double check if they are approved (Safety Gate)
        if not profile.is_approved:
            messages.warning(request, "Your account is not yet approved by an administrator.")
            return render(request, 'registration_pending.html', {'dept': profile.department})

        # 2. Redirect based on the department stored in their profile
        if profile.department == 'finance':
            return redirect('finance')  # Make sure this matches your URL name
        elif profile.department == 'admissions':
            return redirect('admissions')
        elif profile.department == 'stores':
            return redirect('stores')
        elif profile.department == 'examinations':
            return redirect('examinations')
            
    except UserProfile.DoesNotExist:
        # If it's a superuser/admin who doesn't have a profile record
        if request.user.is_staff:
            return redirect('admin_management')
        
    # If no profile and not staff, send to a general dashboard
    return redirect('dashboard')
# --- ADMISSIONS DEPT ---

def get_academic_progress(student):
    today = date.today()
    # Total months since admission
    total_months = (today.year - student.admission_date.year) * 12 + (today.month - student.admission_date.month)
    
    if total_months >= student.projected_duration_months and student.status == 'Active':
        student.status = 'Completed'
        student.save()
        return "Completed", "N/A", "N/A", student.admission_date.strftime('%B')

    # Year calculation: 0-11 months = Year 1, 12-23 months = Year 2, etc.
    current_year = (total_months // 12) + 1
    
    # Term calculation: 4 month cycles
    term_index = (total_months % 12) // 4
    current_term = min(term_index + 1, 3)
    
    return student.status, f"Year {current_year}", f"Term {current_term}", student.admission_date.strftime('%B')

@department_required('admissions')
@login_required

def admissions_view(request):
    page_title = 'ST AUGUSTINE KIPSEBWO VOCATIONAL TRAINING CENTRE'
    
    # 1. Start with the base QuerySet
    students_query = Student.objects.all()
    
    # 2. Extract GET parameters
    search_query = request.GET.get('search', '')
    gender_filter = request.GET.get('gender', '')
    course_filter = request.GET.get('course', '')

    # 3. Apply Filters to the QuerySet
    if search_query:
        students_query = students_query.filter(
            models.Q(name__icontains=search_query) | 
            models.Q(admission_number__icontains=search_query)
        )
    if gender_filter:
        students_query = students_query.filter(sex=gender_filter)
    if course_filter:
        students_query = students_query.filter(course=course_filter)

    # 4. Get distinct courses based on filtered students
    course_list = students_query.values_list('course', flat=True).distinct()
    
    # 5. Group students AND attach dynamic attributes
    grouped_students = {}
    for course in course_list:
        # Get students for this specific course
        course_students = list(students_query.filter(course=course))
        
        # PROCESS EACH STUDENT HERE: This attaches the missing data
        for s in course_students:
            status, yr, trm, month = get_academic_progress(s)
            s.display_status = status
            s.current_year_study = yr
            s.current_term_study = trm
            s.admission_month = month
            
        grouped_students[course] = course_students

    # 6. Handling the POST request (Registration)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                selected_course = form.cleaned_data.get('course')
                if not FeeStructure.objects.filter(course=selected_course).exists():
                    messages.error(request, f"Admission Denied: No Fee Structure found for '{selected_course}'.")
                else:
                    student = form.save()
                    AuditTrail.objects.create(
                        user=request.user, 
                        action=f"Admitted student: {student.name}"
                    )
                    
                    # Check if balance was created (usually via signals)
                    balance_record = getattr(student, 'fee_balance', None)
                    if balance_record:
                        messages.success(request, f"Student {student.name} admitted successfully.")
                    else:
                        messages.warning(request, f"Student admitted, but fees not initialized.")

                    return redirect('admissions')
            except Exception as e:
                messages.error(request, f"System Error: {str(e)}")
    else:
        form = StudentForm()
    
    context = {
        'grouped_students': grouped_students, 
        'form': form, 
        'search_query': search_query,
        'page_title': page_title,
        'courses': course_list # For the course filter dropdown if used
    }
    return render(request, 'admissions.html', context)

@login_required
def student_profile_view(request, pk):
    """View showing all details including dynamic year and term."""
    student = get_object_or_404(Student, pk=pk)
    
    # Calculate dynamic data for profile view
    status, yr, trm, month = get_academic_progress(student)
    
    context = {
        'student': student,
        'current_year': yr,
        'current_term': trm,
        'admission_month': month
    }
    return render(request, 'student_profile.html', context)

@department_required('admissions')
@login_required
def edit_student_view(request, pk):
    """Functionality to edit student details including their status."""
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            AuditTrail.objects.create(user=request.user, action=f"Updated student: {student.name}")
            messages.success(request, "Student profile updated.")
            return redirect('student_profile', pk=student.pk)
    else:
        form = StudentForm(instance=student)
    return render(request, 'edit_student.html', {'form': form, 'student': student})
# --- FINANCE DEPT ---

def finance_view(request):
    # 1. Fetch search AND date parameters
    search_adm = request.GET.get('search_adm', '').strip()
    search_query = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from') # Added
    date_to = request.GET.get('date_to')     # Added
    
    edit_id = request.GET.get('edit_id')
    edit_structure = None
    if edit_id:
        edit_structure = get_object_or_404(FeeStructure, id=edit_id)

    # 2. Get base querysets
    students = Student.objects.all().select_related('fee_balance')
    fee_structures = FeeStructure.objects.all().order_by('-financial_year', '-id')
    recent_payments = Payment.objects.all().select_related('student').order_by('-date_paid')

    # 3. Handle Date Filtering (The missing logic)
    if date_from and date_to:
        # Filter payments within the range and show ALL of them
        recent_payments = recent_payments.filter(date_paid__date__range=[date_from, date_to])
    else:
        # If no filter is applied, only show the 10 most recent
        recent_payments = recent_payments[:10]

    # 4. Handle Student Searching
    search_result = students.filter(admission_number=search_adm).first() if search_adm else None
    if search_query:
        students = students.filter(
            Q(name__icontains=search_query) | Q(admission_number__icontains=search_query)
        )

    return render(request, 'finance.html', {
        'students': students, 
        'search_result': search_result,
        'fee_structures': fee_structures,
        'recent_payments': recent_payments,
        'search_query': search_query,
        'edit_structure': edit_structure,
        'date_from': date_from, # Pass back to keep value in input
        'date_to': date_to,     # Pass back to keep value in input
    })

@department_required('finance')
@login_required
def edit_fee_structure(request, structure_id=None):
    instance = get_object_or_404(FeeStructure, id=structure_id) if structure_id else None

    if request.method == 'POST':
        form = FeeForm(request.POST, instance=instance)
        if form.is_valid():
            # 1. Don't save to DB yet
            obj = form.save(commit=False)

            # 2. Calculate Term 1 Total (Include boarding here!)
            obj.term_1_total = (
                (obj.pta_t1 or 0) + (obj.medical_t1 or 0) + (obj.ltt_t1 or 0) + 
                (obj.adm_fee or 0) + (obj.caution_money or 0) + (obj.student_id or 0) + 
                (obj.contingencies_t1 or 0) + (obj.boarding_fee_t1 or 0)
            )

            # 3. Calculate Term 2 Total
            obj.term_2_total = (
                (obj.pta_t2 or 0) + (obj.medical_t2 or 0) + (obj.ltt_t2 or 0) + 
                (obj.boarding_fee_t2 or 0)
            )

            # 4. Calculate Term 3 Total
            obj.term_3_total = (
                (obj.pta_t3 or 0) + (obj.medical_t3 or 0) + (obj.ltt_t3 or 0) + 
                (obj.boarding_fee_t3 or 0)
            )

            # 5. Calculate Grand Annual Total
            obj.annual_total = obj.term_1_total + obj.term_2_total + obj.term_3_total

            # 6. Now save to database
            obj.save()
            
            messages.success(request, f"Successfully saved structure for {obj.course}")
            return redirect('finance') 
        else:
            print("FORM ERRORS:", form.errors.as_data())
            messages.error(request, f"Save Failed: {form.errors.as_text()}")
            return render(request, 'fee_structure.html', {'form': form, 'instance': instance})
    
    form = FeeForm(instance=instance)
    return render(request, 'fee_structure.html', {'form': form, 'instance': instance})
@department_required('finance')
@login_required
def process_payment(request, student_id):
    """Record a new payment with mode of payment selection."""
    student = get_object_or_404(Student, id=student_id)
    balance, created = FeeBalance.objects.get_or_create(student=student)
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        mode = request.POST.get('mode')
        ref = request.POST.get('reference_number')
        
        with transaction.atomic():
            new_payment = Payment.objects.create(
                student=student, 
                amount=amount, 
                mode=mode, 
                reference_number=ref
            )
            AuditTrail.objects.create(
                user=request.user, 
                action=f"Recorded {mode} payment of {amount} for {student.name}"
            )
            return redirect('print_receipt', payment_id=new_payment.id)
        
    return render(request, 'make_payment.html', {'student': student, 'balance': balance})

@login_required
def download_fee_structure(request, structure_id, student_id=None):
    """Generates the printable Ministry of Education style fee structure."""
    structure = get_object_or_404(FeeStructure, id=structure_id)
    student = get_object_or_404(Student, id=student_id) if student_id else None
    
    # Logic for termly totals
    t1_total = (structure.pta_t1 + structure.medical_t1 + structure.ltt_t1 + 
                structure.contingencies_t1 + structure.adm_fee + 
                structure.caution_money + structure.student_id + structure.boarding_fee_t1)
    
    t2_total = (structure.pta_t2 + structure.medical_t2 + structure.ltt_t2 + 
                structure.boarding_fee_t2)
    
    t3_total = (structure.pta_t3 + structure.medical_t3 + structure.ltt_t3 + 
                structure.boarding_fee_t3)

    return render(request, 'fee_structure_printable.html', {
        's': structure,
        'student': student,
        't1_total': t1_total,
        't2_total': t2_total,
        't3_total': t3_total,
        'grand_total': t1_total + t2_total + t3_total,
    })

@login_required
def print_receipt(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    return render(request, 'receipt_print.html', {'payment': payment})

@login_required
def payment_history(request, student_id=None):
    """View history for all or a specific student."""
    if student_id:
        student = get_object_or_404(Student, id=student_id)
        payments = Payment.objects.filter(student=student).order_by('-date_paid')
    else:
        payments = Payment.objects.all().order_by('-date_paid')
    return render(request, 'payment_history.html', {'payments': payments, 'student_id': student_id})

@department_required('finance')
@login_required
def fee_structure_view(request):
    """Handles searching for a student without crashing."""
    adm_no = request.GET.get('adm_no')
    
    if adm_no:
        # Filter instead of get_object_or_404 to avoid the crash
        student = Student.objects.filter(admission_number=adm_no).first()
        
        if not student:
            # Send a friendly error message back to the dashboard
            messages.error(request, f"Search Failed: Student with Admission Number '{adm_no}' was not found.")
            return redirect('finance')
            
        # If student exists, proceed to their statement/structure
        history = Payment.objects.filter(student=student).order_by('-date_paid')
        structure = FeeStructure.objects.filter(course=student.course).first()
        
        return render(request, 'fee_structure.html', {
            'student': student,
            'history': history,
            'structure': structure,
        })
    
    return redirect('finance')

@department_required('finance')
@login_required
def record_payment(request):
    if request.method == 'POST':
        adm_no = request.POST.get('adm_no')
        amount = request.POST.get('amount')
        mode = request.POST.get('mode')
        # Do NOT capture reference_number here if you want it to be 100% automatic
        
        try:
            student = Student.objects.get(admission_number=adm_no)
            # Create the payment - the save() method in models.py will handle the ID
            new_payment = Payment.objects.create(
                student=student,
                amount=amount,
                mode=mode
            )
            messages.success(request, f"Payment of {amount} recorded successfully!")
            return redirect('generate_receipt', payment_id=new_payment.id)
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('finance_view')

@department_required('finance')
@login_required
def record_payment(request):
    if request.method == 'POST':
        adm_no = request.POST.get('adm_no')
        amount_str = request.POST.get('amount', '0')
        mode = request.POST.get('mode')
        # Use .strip() or None to ensure the model's auto-gen logic triggers
        ref = request.POST.get('reference', '').strip() or None 
        
        # 1. Convert amount safely
        try:
            amount = Decimal(amount_str)
        except:
            messages.error(request, "Invalid amount entered.")
            return redirect('finance_view') # Ensure 'finance_view' matches your dashboard URL name

        # 2. Find Student or trigger Error
        student = Student.objects.filter(admission_number=adm_no).first()
        
        if not student:
            messages.error(request, f"❌ Error: No student found with Admission Number '{adm_no}'.")
            return redirect('finance_view')

        # 3. Save Payment
        try:
            with transaction.atomic():
                new_payment = Payment.objects.create(
                    student=student, 
                    amount=amount, 
                    mode=mode,
                    reference_number=ref # If ref is None, the Model save() generates the ID
                )
                
                # Update Audit Trail
                AuditTrail.objects.create(
                    user=request.user, 
                    action=f"Recorded {mode} payment of {amount} for {student.name}"
                )
                
                messages.success(request, f"✅ Payment of Ksh {amount} recorded for {student.name}")
                
                # 4. FIXED REDIRECT: Matches the name in your urls.py
                return redirect('generate_receipt', payment_id=new_payment.id)
                
        except Exception as e:
            messages.error(request, f"An error occurred while saving: {str(e)}")
            return redirect('finance_view')
            
    return redirect('finance_view')

def generate_receipt(request, payment_id):
    """View to display a printable receipt for a specific payment."""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # We fetch the balance from the student's related fee_balance record
    student = payment.student
    balance = student.fee_balance.balance if hasattr(student, 'fee_balance') else 0

    return render(request, 'receipt_printable.html', {
        'payment': payment,
        'student': student,
        'balance': balance,
    })


@department_required('finance')
@login_required
@never_cache
def print_fee_structure(request, pk):
    # Fetch the structure and use .refresh_from_db() to be 100% sure 
    # we aren't looking at a cached version.
    structure = get_object_or_404(FeeStructure, id=pk)
    structure.refresh_from_db()
    
    return render(request, 'print_fee_template.html', {
        'structure': structure,
        # Property methods will now calculate using fresh data
        't1_total': structure.term1_total,
        't2_total': structure.term2_total,
        't3_total': structure.term3_total,
    })
@department_required('finance')
@login_required
def print_transactions(request):
    """Generates a printable report of transactions between two dates."""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if not start_date or not end_date:
        messages.error(request, "Please select both a start and end date to print.")
        return redirect('finance_view')

    # Fetch payments within the range
    payments = Payment.objects.filter(
        date_paid__range=[start_date, end_date]
    ).select_related('student').order_by('date_paid')

    total_collected = sum(p.amount for p in payments)

    return render(request, 'transactions_report_print.html', {
        'payments': payments,
        'start_date': start_date,
        'end_date': end_date,
        'total_collected': total_collected,
        'print_date': timezone.now()
    })
# examinations
@department_required('examinations')
@login_required
def examinations_view(request):
    # 1. Setup Filters & Initial State
    query = request.GET.get('q', '').strip()
    course_filter = request.GET.get('course', '').strip()
    year_filter = request.GET.get('year', '').strip()
    term_filter = request.GET.get('term', '').strip()
    
    # 2. Handle GET Edit IDs
    edit_exam_id = request.GET.get('edit_exam')
    edit_knec_id = request.GET.get('edit_payment') 

    # 3. Fetch Instances (Previous Records)
    exam_instance = Examination.objects.filter(id=edit_exam_id).first() if edit_exam_id else None
    knec_instance = KnecPayment.objects.filter(id=edit_knec_id).first() if edit_knec_id else None

    # --- THE FIX: Initialize both forms early so they are NEVER "Unbound" ---
    form = ExaminationForm(instance=exam_instance)
    knec_form = KnecPaymentForm(instance=knec_instance)

    # 4. Handle POST Requests
    if request.method == 'POST':
        if 'submit_payment' in request.POST:
            # Re-bind knec_form with POST data
            knec_form = KnecPaymentForm(request.POST, instance=knec_instance)
            if knec_form.is_valid():
                if knec_instance:
                    knec_form.save()
                    action_msg = f"Edited KNEC record for {knec_instance.student.name}"
                else:
                    data = knec_form.cleaned_data
                    obj, created = KnecPayment.objects.get_or_create(
                        student=data['student'],
                        exam_series=data['exam_series'],
                        defaults={'required_amount': data['required_amount'], 'amount_paid': 0}
                    )
                    obj.amount_paid += data['amount_paid']
                    obj.required_amount = data['required_amount']
                    obj.save()
                    action_msg = f"Added KES {data['amount_paid']} to {obj.student.name}"

                AuditTrail.objects.create(user=request.user, action=action_msg)
                messages.success(request, "KNEC Payment processed.")
                return redirect('examinations')
            else:
                print(f"❌ KNEC VALIDATION ERROR: {knec_form.errors}")

        elif 'submit_marks' in request.POST:
            # Re-bind 'form' with POST data
            form = ExaminationForm(request.POST, instance=exam_instance)
            if form.is_valid():
                form.save()
                messages.success(request, "Marks updated successfully.")
                return redirect('examinations')

    # 5. Apply Exclusive Filtering (Displays only the student being edited)
    if knec_instance:
        knec_payments = KnecPayment.objects.filter(id=edit_knec_id).select_related('student')
        exams = Examination.objects.none()
        students = Student.objects.filter(id=knec_instance.student.id)
        student = knec_instance.student
    elif exam_instance:
        exams = Examination.objects.filter(id=edit_exam_id).select_related('student')
        knec_payments = KnecPayment.objects.none()
        students = Student.objects.filter(id=exam_instance.student.id)
        student = exam_instance.student
    else:
        # Normal List View with Filters
        exams = Examination.objects.all().select_related('student')
        knec_payments = KnecPayment.objects.all().select_related('student')
        students = Student.objects.all()
        student = None

        if query:
            student = Student.objects.filter(admission_number=query).first()
            if student:
                exams = exams.filter(student=student)
                knec_payments = knec_payments.filter(student=student)
                students = students.filter(id=student.id)
        
        if course_filter:
            exams = exams.filter(student__course__icontains=course_filter)
            knec_payments = knec_payments.filter(student__course__icontains=course_filter)

    exams = exams.order_by('student__course', 'year_of_study', 'semester', 'student__name')

    # 6. Final Render (Both 'form' and 'knec_form' are now guaranteed to exist)
    context = {
        'form': form, 
        'knec_form': knec_form,
        'exams': exams, 
        'knec_payments': knec_payments,
        'students': students, 
        'student': student,
        'is_editing': bool(knec_instance or exam_instance),
    }
    return render(request, 'examinations.html', context)

@login_required
def print_student_report(request, student_id):
    """Generates a printable report card for a single student."""
    student = get_object_or_404(Student, id=student_id)
    year = request.GET.get('year')
    term = request.GET.get('term')
    
    exams = Examination.objects.filter(student=student)
    if year: exams = exams.filter(year_of_study=year)
    if term: exams = exams.filter(semester=term)
    
    # Statistical Calculation
    stats = exams.aggregate(
        avg_score=Avg('total_marks'),
        total_subjects=Avg('id') # Using Avg here just to get a count via aggregate if needed
    )
    mean_score = stats['avg_score'] or 0
    count = exams.count()

    return render(request, 'reports/student_report_print.html', {
        'student': student,
        'exams': exams,
        'year': year,
        'term': term,
        'mean_score': round(mean_score, 2),
        'subject_count': count,
        'print_date': timezone.now()
    })

@login_required
def print_course_results(request):
    """Generates a printable broadsheet for a specific course/year/term."""
    course = request.GET.get('course')
    year = request.GET.get('year')
    term = request.GET.get('term')

    if not all([course, year, term]):
        messages.error(request, "Please provide Course, Year, and Term to generate a broadsheet.")
        return redirect('examinations')

    exams = Examination.objects.filter(
        student__course__icontains=course,
        year_of_study=year,
        semester=term
    ).select_related('student').order_by('student__name', 'subject_name')

    return render(request, 'reports/course_results_print.html', {
        'exams': exams,
        'course': course,
        'year': year,
        'term': term,
        'print_date': timezone.now()
    })
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Consumable, PermanentEquipment, AuditTrail
from .forms import ConsumableForm, EquipmentForm

# --- MAIN STORES VIEW ---
@department_required('stores')
@login_required
def stores_view(request):
    # 1. Fetch data
    consumables = Consumable.objects.all().order_by('description_of_inventory_item')
    equipment = PermanentEquipment.objects.all().order_by('asset_description')
    
    # 2. Initialize Forms (Blank by default)
    c_form = ConsumableForm()
    e_form = EquipmentForm()

    # 3. Handle Addition of New Items
    if request.method == 'POST':
        # Add Consumable
        if 'add_consumable' in request.POST:
            c_form = ConsumableForm(request.POST)
            if c_form.is_valid():
                item = c_form.save(commit=False)
                item.added_by = request.user
                item.save()
                AuditTrail.objects.create(user=request.user, action=f"Added Consumable: {item.description_of_inventory_item}")
                messages.success(request, "Consumable added successfully")
                return redirect('stores')

        # Add Equipment
        elif 'add_equipment' in request.POST:
            e_form = EquipmentForm(request.POST)
            if e_form.is_valid():
                item = e_form.save(commit=False)
                item.added_by = request.user
                item.save()
                AuditTrail.objects.create(user=request.user, action=f"Added Equipment: {item.asset_description}")
                messages.success(request, "Equipment added successfully")
                return redirect('stores')

    context = {
        'consumables': consumables, 
        'equipment': equipment, 
        'c_form': c_form, 
        'e_form': e_form,
    }
    return render(request, 'stores.html', context)

# --- EDIT LOGIC ---
@department_required('stores')
@login_required
def edit_store_item(request, item_type, pk):
    """Router for editing items based on type."""
    if item_type == 'consumable':
        item = get_object_or_404(Consumable, pk=pk)
        form_class = ConsumableForm
        title = "Edit Consumable"
        action_name = item.description_of_inventory_item
    else:
        item = get_object_or_404(PermanentEquipment, pk=pk)
        form_class = EquipmentForm
        title = "Edit Equipment"
        action_name = item.asset_description

    if request.method == 'POST':
        form = form_class(request.POST, instance=item)
        if form.is_valid():
            form.save()
            AuditTrail.objects.create(user=request.user, action=f"Edited {item_type}: {action_name}")
            messages.success(request, f"{item_type.capitalize()} updated successfully")
            return redirect('stores')
    else:
        # Pre-fills the form with existing data
        form = form_class(instance=item)

    return render(request, 'edit_item.html', {'form': form, 'title': title, 'item': item})

# --- PRINT REPORT VIEWS ---
@department_required('stores')
@login_required
def print_inventory(request, report_type):
    """Dedicated view for printer-friendly reports."""
    if report_type == 'consumables':
        items = Consumable.objects.all().order_by('description_of_inventory_item')
        template = 'reports/print_consumables.html'
        title = "Consumables Inventory Report"
    else:
        items = PermanentEquipment.objects.all().order_by('asset_description')
        template = 'reports/print_equipment.html'
        title = "Permanent Equipment Inventory Report"

    return render(request, template, {
        'items': items,
        'title': title,
        'print_date': timezone.now()
    })

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
    
    # Also approve the associated UserProfile
    profile = getattr(user, 'userprofile', None)
    if profile:
        profile.is_approved = True
        profile.save()

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