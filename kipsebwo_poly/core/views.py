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

@department_required('admissions')
@login_required
def admissions_view(request):
    page_title = 'ST AUGUSTINE KIPSEBWO VOCATIONAL TRAINING CENTRE'
    
    students_list = Student.objects.all()
    search_query = request.GET.get('search', '')
    gender_filter = request.GET.get('gender', '')
    
    # Filtering Logic
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
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # The Signal in models.py will automatically create FeeBalance 
                # the moment student.save() is called inside form.save()
                student = form.save()

                AuditTrail.objects.create(
                    user=request.user, 
                    action=f"Admitted student: {student.name}"
                )
                
                # Check if the signal successfully found a fee structure
                # We fetch it to show a nice message to the user
                balance_record = getattr(student, 'fee_balance', None)
                
                if balance_record and balance_record.total_invoiced > 0:
                    messages.success(request, f"Student {student.name} admitted. Fees initialized to {balance_record.total_invoiced}.")
                else:
                    messages.warning(request, f"Student admitted, but no matching Fee Structure was found for {student.course}. Please check Finance settings.")

                return redirect('admissions')
            
            except Exception as e:
                messages.error(request, f"System Error during admission: {str(e)}")
    else:
        form = StudentForm()
    
    context = {
        'grouped_students': grouped_students, 
        'form': form, 
        'search_query': search_query,
        'page_title': page_title
    }
    return render(request, 'admissions.html', context)
@login_required
def student_profile_view(request, pk):
    """View showing all details: Boarding status, photos, and current status."""
    student = get_object_or_404(Student, pk=pk)
    return render(request, 'student_profile.html', {'student': student})

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

@department_required('finance')
@login_required
def finance_view(request):
    # 1. Fetch search parameters
    search_adm = request.GET.get('search_adm', '').strip()
    search_query = request.GET.get('search', '').strip()
    
    # NEW: Handle "Edit Mode" for the dashboard
    edit_id = request.GET.get('edit_id')
    edit_structure = None
    if edit_id:
        edit_structure = get_object_or_404(FeeStructure, id=edit_id)

    # 2. Get all students and fee structures
    students = Student.objects.all().select_related('fee_balance')
    fee_structures = FeeStructure.objects.all().order_by('-financial_year', '-id')

    # 3. Handle Searching
    search_result = students.filter(admission_number=search_adm).first() if search_adm else None
    if search_query:
        students = students.filter(
            Q(name__icontains=search_query) | Q(admission_number__icontains=search_query)
        )

    recent_payments = Payment.objects.all().select_related('student').order_by('-date_paid')[:10]
    
    return render(request, 'finance.html', {
        'students': students, 
        'search_result': search_result,
        'fee_structures': fee_structures,
        'recent_payments': recent_payments,
        'search_query': search_query,
        'edit_structure': edit_structure,  # Passed to trigger the edit form in your template
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
def print_fee_structure(request, pk):
    structure = get_object_or_404(FeeStructure, id=pk)
    
    # For now, let's just render a simple print template
    return render(request, 'print_fee_template.html', {
        'structure': structure,
    })
# examinations
@department_required('examinations')
@login_required
def examinations_view(request):
    query = request.GET.get('q')
    student = None
    
    # 1. Handling Search/List Logic
    if query:
        student = Student.objects.filter(admission_number=query).first()
        exams = Examination.objects.filter(student=student).order_by('year_of_study', 'semester', 'subject_name') if student else Examination.objects.none()
    else:
        exams = Examination.objects.all().select_related('student').order_by('student__course', 'year_of_study', 'semester', 'student__name')

    # 2. Handling POST requests (Save/Update/Delete)
    if request.method == 'POST':
        # DELETE LOGIC
        if 'delete_id' in request.POST:
            exam_to_delete = get_object_or_404(Examination, id=request.POST.get('delete_id'))
            student_name = exam_to_delete.student.name
            subject = exam_to_delete.subject_name
            exam_to_delete.delete()
            AuditTrail.objects.create(user=request.user, action=f"Deleted marks for {student_name} (Subject: {subject})")
            messages.success(request, "Record deleted successfully.")
            return redirect('examinations')

        # SAVE/UPDATE LOGIC
        instance_id = request.POST.get('instance_id')
        instance = Examination.objects.filter(id=instance_id).first() if instance_id else None
        form = ExaminationForm(request.POST, instance=instance)
        
        if form.is_valid():
            # The .save() call here triggers the average calculation we wrote in the Model
            exam = form.save() 
            
            action_type = "Updated" if instance_id else "Recorded"
            AuditTrail.objects.create(
                user=request.user, 
                action=f"{action_type} marks: {exam.student.name} - {exam.subject_name} (Total: {exam.total_marks})"
            )
            messages.success(request, f"Marks for {exam.subject_name} saved successfully. Total: {exam.total_marks}")
            return redirect('examinations')
            
    # 3. Handling GET request (Edit/Empty Form)
    else:
        edit_id = request.GET.get('edit')
        instance = Examination.objects.filter(id=edit_id).first() if edit_id else None
        form = ExaminationForm(instance=instance)

    return render(request, 'examinations.html', {
        'form': form, 
        'exams': exams, 
        'student': student, 
        'query': query
    })
# --- STORES ---

@department_required('stores')
@login_required
def stores_view(request):
    consumables = Consumable.objects.all()
    equipment = PermanentEquipment.objects.all()
    
    # Initialize forms
    c_form = ConsumableForm()
    e_form = EquipmentForm()

    if request.method == 'POST':
        # Handling Consumables (New fields: description_of_inventory_item, quantity, etc.)
        if 'add_consumable' in request.POST:
            c_form = ConsumableForm(request.POST)
            if c_form.is_valid():
                item = c_form.save(commit=False)
                item.added_by = request.user
                item.save()
                AuditTrail.objects.create(
                    user=request.user, 
                    action=f"Added Consumable: {item.description_of_inventory_item}"
                )
                messages.success(request, "Consumable added successfully")
                return redirect('stores')

        # Handling Equipment (New fields: asset_description, serial_number, etc.)
        elif 'add_equipment' in request.POST:
            e_form = EquipmentForm(request.POST)
            if e_form.is_valid():
                item = e_form.save(commit=False)
                item.added_by = request.user
                item.save()
                AuditTrail.objects.create(
                    user=request.user, 
                    action=f"Added Equipment: {item.asset_description}"
                )
                messages.success(request, "Equipment added successfully")
                return redirect('stores')

    context = {
        'consumables': consumables, 
        'equipment': equipment, 
        'c_form': c_form, 
        'e_form': e_form
    }
    return render(request, 'stores.html', context)

# --- UPDATED EDIT LOGIC TO FIX ATTRIBUTE ERROR ---

@department_required('stores')
@login_required
def edit_store_item(request, item_type, pk):
    """
    This is the missing function your URL configuration is looking for.
    It routes the request to the correct specific edit view.
    """
    if item_type == 'consumable':
        return edit_consumable(request, pk)
    elif item_type == 'equipment':
        return edit_equipment(request, pk)
    else:
        messages.error(request, "Invalid item type specified.")
        return redirect('stores')

@department_required('stores')
@login_required
def edit_consumable(request, pk):
    item = get_object_or_404(Consumable, pk=pk)
    if request.method == 'POST':
        form = ConsumableForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            AuditTrail.objects.create(
                user=request.user, 
                action=f"Edited Consumable: {item.description_of_inventory_item}"
            )
            messages.success(request, "Consumable updated successfully")
            return redirect('stores')
    else:
        form = ConsumableForm(instance=item)
    return render(request, 'edit_item.html', {'form': form, 'title': 'Edit Consumable'})

@department_required('stores')
@login_required
def edit_equipment(request, pk):
    item = get_object_or_404(PermanentEquipment, pk=pk)
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            AuditTrail.objects.create(
                user=request.user, 
                action=f"Edited Equipment: {item.asset_description}"
            )
            messages.success(request, "Equipment updated successfully")
            return redirect('stores')
    else:
        form = EquipmentForm(instance=item)
    return render(request, 'edit_item.html', {'form': form, 'title': 'Edit Equipment'})
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