from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
import uuid
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import date

# --- 1. USER & SYSTEM ---

class UserProfile(models.Model):
    DEPARTMENT_CHOICES = [
        ('finance', 'Finance'),
        ('admission', 'Admission'),
        ('exams', 'Examinations'),
        ('store', 'Store'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.department}"

class AuditTrail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

# --- 2. FINANCE STRUCTURE (Moved up so Student can reference it) ---

class FeeStructure(models.Model):
    SCHOLAR_CHOICES = [('Day Scholar', 'Day Scholar'), ('Boarder', 'Boarder')]
    
    course = models.CharField(max_length=100)
    scholar_type = models.CharField(max_length=20, choices=SCHOLAR_CHOICES)
    financial_year = models.CharField(max_length=20, help_text="e.g., 2025/2026")

    # Term 1
    pta_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ltt_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contingencies_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Term 2
    pta_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ltt_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Term 3
    pta_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ltt_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # One-off Fees
    adm_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    caution_money = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    student_id = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Boarding Fees
    boarding_fee_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    boarding_fee_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    boarding_fee_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('course', 'scholar_type', 'financial_year')

    @property
    def term1_total(self):
        return (self.pta_t1 + self.medical_t1 + self.ltt_t1 + self.contingencies_t1 + 
                self.adm_fee + self.caution_money + self.student_id + self.boarding_fee_t1)

    @property
    def term2_total(self):
        return self.pta_t2 + self.medical_t2 + self.ltt_t2 + self.boarding_fee_t2

    @property
    def term3_total(self):
        return self.pta_t3 + self.medical_t3 + self.ltt_t3 + self.boarding_fee_t3

    def __str__(self):
        return f"{self.course} ({self.scholar_type}) - {self.financial_year}"

# --- 3. STUDENT ---

class Student(models.Model):
    SEX_CHOICES = [('Male', 'Male'), ('Female', 'Female')]
    RESIDENCE_CHOICES = [('Boarder', 'Boarder'), ('Day Scholar', 'Day Scholar')]
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Deferred', 'Deferred'),
        ('Dropout', 'Dropout'),
        ('Completed', 'Completed')
    ]

    name = models.CharField(max_length=100)
    admission_number = models.CharField(max_length=50, unique=True)
    id_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    birth_certificate_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    course = models.CharField(max_length=100)
    last_school = models.CharField(max_length=100)
    parent_contacts = models.CharField(max_length=100)
    religion = models.CharField(max_length=50)
    
    admission_date = models.DateField(default=timezone.now)
    projected_duration_months = models.PositiveIntegerField(default=12)

    year_enrolled = models.IntegerField(default=2026)
    residence = models.CharField(max_length=20, choices=RESIDENCE_CHOICES, default='Day Scholar')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    passport_photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)

    def clean(self):
        # Now we can reference FeeStructure directly because it is defined above
        if not FeeStructure.objects.filter(course__iexact=self.course).exists():
            raise ValidationError(
                f"Cannot admit student: No fee structure found for course '{self.course}'."
            )

    @property
    def current_academic_standing(self):
        today = date.today()
        diff = (today.year - self.admission_date.year) * 12 + (today.month - self.admission_date.month)
        
        if diff >= self.projected_duration_months and self.status == 'Active':
            return {"year": "N/A", "term": "N/A", "is_completed": True}

        academic_year = (diff // 12) + 1
        term_index = (diff % 12) // 4
        current_term = min(term_index + 1, 3)

        return {
            "year": academic_year,
            "term": current_term,
            "is_completed": False,
            "admission_month": self.admission_date.strftime('%B')
        }

    def __str__(self):
        return f"{self.admission_number} - {self.name}"

# --- 4. ACADEMICS ---

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    year_of_study = models.IntegerField() 
    semester = models.IntegerField()      
    
    def __str__(self):
        return f"{self.name} (Year {self.year_of_study}, Sem {self.semester})"

class Examination(models.Model):
    YEAR_CHOICES = [('1', 'Year 1'), ('2', 'Year 2'), ('3', 'Year 3')]
    SEM_CHOICES = [('1', 'Semester 1'), ('2', 'Semester 2')]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject_name = models.CharField(max_length=100)
    cat_1 = models.PositiveIntegerField(default=0)
    cat_2 = models.PositiveIntegerField(default=0)
    end_term = models.PositiveIntegerField(default=0)
    total_marks = models.FloatField(default=0, editable=False)
    
    year_of_study = models.CharField(max_length=1, choices=YEAR_CHOICES, default='1')
    semester = models.CharField(max_length=1, choices=SEM_CHOICES, default='1')
    date_recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['year_of_study', 'semester', 'subject_name']

    def save(self, *args, **kwargs):
        cat_average = (self.cat_1 + self.cat_2) / 2
        self.total_marks = cat_average + self.end_term
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.name} - {self.subject_name} ({self.total_marks})"
class KnecPayment(models.Model):
   
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='knec_payments')
    exam_series = models.CharField(max_length=50, help_text="e.g., July 2026 or Nov 2026")
    required_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date_paid = models.DateField(auto_now_add=True)
    
    @property
    def balance(self):
        return self.required_amount - self.amount_paid

    @property
    def status(self):
        if self.amount_paid >= self.required_amount:
            return "Fully Paid"
        elif self.amount_paid > 0:
            return "Partial"
        return "Not Paid"

    def __str__(self):
        return f"{self.student.name} - {self.exam_series} (Paid: {self.amount_paid})"

    class Meta:
        verbose_name = "KNEC Exam Payment"
        unique_together = ['student', 'exam_series']
    @property
    def get_balance(self):
        return self.required_amount - self.amount_paid

    # --- 5. PAYMENTS & BALANCES ---

class FeeBalance(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='fee_balance')
    total_invoiced = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def balance(self):
        return self.total_invoiced - self.total_paid

    def __str__(self):
        return f"{self.student.name} - Bal: {self.balance}"

class Payment(models.Model):
    MODE_CHOICES = [('M-Pesa', 'M-Pesa'), ('Bank Cheque', 'Bank Cheque'), 
                    ('Bank Deposit', 'Bank Deposit'), ('Cash', 'Cash'), ('Others', 'Others')]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    reference_number = models.CharField(max_length=100, unique=True, blank=True)
    date_paid = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference_number:
            unique_id = uuid.uuid4().hex[:8].upper()
            self.reference_number = f"KIP-2026-{unique_id}"
        
        super().save(*args, **kwargs)

        # Update balance record
        balance_record, _ = FeeBalance.objects.get_or_create(student=self.student)
        total_payments = Payment.objects.filter(student=self.student).aggregate(Sum('amount'))['amount__sum'] or 0
        balance_record.total_paid = total_payments
        balance_record.save()

# --- 6. STORES ---

class Consumable(models.Model):
    description_of_inventory_item = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    number_issued = models.PositiveIntegerField(default=0)
    balance_in_stock = models.IntegerField(default=0)
    date_supplied = models.DateField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        self.balance_in_stock = self.quantity - self.number_issued
        super().save(*args, **kwargs)

class PermanentEquipment(models.Model):
    CONDITION_CHOICES = [('Good', 'Good'), ('Fair', 'Fair'), ('Damaged', 'Damaged'), ('Disposed', 'Disposed')]
    
    asset_description = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=100, unique=True)
    make_and_model = models.CharField(max_length=200)
    date_of_delivery = models.DateField()
    original_location = models.CharField(max_length=200)
    current_location = models.CharField(max_length=200)
    date_of_disposal = models.DateField(null=True, blank=True)
    asset_condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='Good')
    remarks = models.TextField(null=True, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

# --- 7. SIGNALS ---

@receiver(post_save, sender=Student)
def auto_calculate_fees(sender, instance, created, **kwargs):
    if created:
        # Determine the financial year string based on current date
        # e.g., if it's 2026, look for "2026/2027"
        current_year = timezone.now().year
        fin_year_str = f"{current_year}/{current_year + 1}"

        structure = FeeStructure.objects.filter(
            course__iexact=instance.course, 
            scholar_type=instance.residence,
            financial_year=fin_year_str
        ).first()

        # If specific year not found, fall back to the most recent structure
        if not structure:
            structure = FeeStructure.objects.filter(
                course__iexact=instance.course, 
                scholar_type=instance.residence
            ).order_by('-financial_year').first()

        total_invoice = 0
        if structure:
            total_invoice = structure.term1_total + structure.term2_total + structure.term3_total

        FeeBalance.objects.get_or_create(
            student=instance,
            defaults={'total_invoiced': total_invoice, 'total_paid': 0}
        )