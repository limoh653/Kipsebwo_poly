from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
import uuid

# --- USER PROFILE ---
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
        return f"{self.user.username} - {self.department} ({'Approved' if self.is_approved else 'Pending'})"

# --- AUDIT & STUDENT ---
class AuditTrail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

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
    year_enrolled = models.IntegerField(default=2026)
    residence = models.CharField(max_length=20, choices=RESIDENCE_CHOICES, default='Day Scholar')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    passport_photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)

    def __str__(self):
        return f"{self.admission_number} - {self.name}"

# --- ACADEMICS ---
class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    year_of_study = models.IntegerField() 
    semester = models.IntegerField()      
    
    def __str__(self):
        return f"{self.name} (Year {self.year_of_study}, Sem {self.semester})"

from django.db import models

class Examination(models.Model):
    YEAR_CHOICES = [('1', 'Year 1'), ('2', 'Year 2'), ('3', 'Year 3')]
    SEM_CHOICES = [('1', 'Semester 1'), ('2', 'Semester 2')]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject_name = models.CharField(max_length=100)
    
    cat_1 = models.PositiveIntegerField(default=0)
    cat_2 = models.PositiveIntegerField(default=0)
    end_term = models.PositiveIntegerField(default=0)
    
    # Changed to FloatField to accommodate averages like 12.5
    total_marks = models.FloatField(default=0, editable=False)
    
    year_of_study = models.CharField(max_length=1, choices=YEAR_CHOICES, default='1')
    semester = models.CharField(max_length=1, choices=SEM_CHOICES, default='1')
    date_recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['year_of_study', 'semester', 'subject_name']

    def save(self, *args, **kwargs):
        # 1. Calculate the average of CAT 1 and CAT 2
        cat_average = (self.cat_1 + self.cat_2) / 2
        
        # 2. Add the average to the End Term
        self.total_marks = cat_average + self.end_term
        
        # Optional: If you want to force it back to an Integer, use:
        # self.total_marks = round(cat_average + self.end_term)
        
        super().save(*args, **kwargs)

    def __str__(self):
        # Accessing student.name (ensure this matches your Student model field)
        return f"{self.student.name} - {self.subject_name} (Total: {self.total_marks})"
# --- FINANCE ---
class FeeStructure(models.Model):
    SCHOLAR_CHOICES = [('Day Scholar', 'Day Scholar'), ('Boarder', 'Boarder')]
    
    course = models.CharField(max_length=100)
    scholar_type = models.CharField(max_length=20, choices=SCHOLAR_CHOICES)
    financial_year = models.CharField(max_length=20, help_text="e.g., 2025/2026")

    pta_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ltt_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contingencies_t1 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    pta_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ltt_t2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    pta_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ltt_t3 = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    adm_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    caution_money = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    student_id = models.DecimalField(max_digits=10, decimal_places=2, default=0)

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
    MODE_CHOICES = [
        ('M-Pesa', 'M-Pesa'),
        ('Bank Cheque', 'Bank Cheque'),
        ('Bank Deposit', 'Bank Deposit'),
        ('Cash', 'Cash'),
        ('Others', 'Others')
    ]
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

        # Update balance
        balance_record, created = FeeBalance.objects.get_or_create(student=self.student)
        total_payments = Payment.objects.filter(student=self.student).aggregate(Sum('amount'))['amount__sum'] or 0
        balance_record.total_paid = total_payments
        balance_record.save()

# --- STORES ---
class Consumable(models.Model):
    description_of_inventory_item = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    number_issued = models.PositiveIntegerField(default=0)
    # This field remains for DB storage, but we'll automate it in save()
    balance_in_stock = models.IntegerField(default=0,)
    
    date_supplied = models.DateField(auto_now_add=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        # Automatically calculate balance
        self.balance_in_stock = self.quantity - self.number_issued
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description_of_inventory_item

class PermanentEquipment(models.Model):
    CONDITION_CHOICES = [
        ('Good', 'Good'), 
        ('Fair', 'Fair'), 
        ('Damaged', 'Damaged'),
        ('Disposed', 'Disposed')
    ]
    
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

    def __str__(self):
        return f"{self.asset_description} ({self.serial_number})"

# --- SIGNALS ---
@receiver(post_save, sender=Student)
def auto_calculate_fees(sender, instance, created, **kwargs):
    if created:
        # 1. Determine the current financial year (matches your Student default)
        # You might want to make this dynamic based on the current date
        current_year = f"{instance.year_enrolled}/{instance.year_enrolled + 1}"

        # 2. Look up the structure with a more specific filter
        structure = FeeStructure.objects.filter(
            course__iexact=instance.course, 
            scholar_type=instance.residence,
            financial_year=current_year
        ).first()

        # 3. Calculate total
        total_invoice = 0
        if structure:
            # We use the properties you already defined
            total_invoice = structure.term1_total + structure.term2_total + structure.term3_total
        else:
            # OPTIONAL: Fallback to the latest year if the specific year isn't found
            structure = FeeStructure.objects.filter(
                course__iexact=instance.course, 
                scholar_type=instance.residence
            ).order_by('-financial_year').first()
            
            if structure:
                total_invoice = structure.term1_total + structure.term2_total + structure.term3_total

        # 4. Create the Balance Record
        FeeBalance.objects.get_or_create(
            student=instance,
            defaults={
                'total_invoiced': total_invoice, 
                'total_paid': 0
            }
        )