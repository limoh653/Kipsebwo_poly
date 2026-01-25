from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

#tracks the user's requested department, their approval status, and define the department choices.
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

# 1. Audit Trail
class AuditTrail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

# 2. Student Model
class Student(models.Model):
    SEX_CHOICES = [('Male', 'Male'), ('Female', 'Female')]
    
    name = models.CharField(max_length=100)
    admission_number = models.CharField(max_length=50, unique=True)
    # Using the name exactly as the system expects to avoid renaming prompts
    id_birth_number = models.CharField(max_length=50) 
    phone_number = models.CharField(max_length=20)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    course = models.CharField(max_length=100)
    last_school = models.CharField(max_length=100)
    parent_contacts = models.CharField(max_length=100)
    religion = models.CharField(max_length=50)
    year_enrolled = models.IntegerField(default=2026)

    def __str__(self):
        return f"{self.admission_number} - {self.name}"

from django.db import models

# ... (Keep Student, FeeStructure, etc. as they are)

# 1. New Subject Model
class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    year_of_study = models.IntegerField() # e.g., 1, 2, 3
    semester = models.IntegerField()      # e.g., 1, 2
    
    def __str__(self):
        return f"{self.name} (Year {self.year_of_study}, Sem {self.semester})"


class Examination(models.Model):
    # Defining choices for better data integrity
    YEAR_CHOICES = [
        ('1', 'Year 1'),
        ('2', 'Year 2'),
        ('3', 'Year 3'),
    ]
    SEM_CHOICES = [
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    # Use subject_name as a CharField for manual entry
    subject_name = models.CharField(max_length=100)
    marks = models.PositiveIntegerField()
    
    # Adding defaults ensures migrations run smoothly without asking questions
    year_of_study = models.CharField(
        max_length=1, 
        choices=YEAR_CHOICES, 
        default='1'
    )
    semester = models.CharField(
        max_length=1, 
        choices=SEM_CHOICES, 
        default='1'
    )
    
    date_recorded = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.subject_name} ({self.marks})"

    class Meta:
        # This ensures that when we fetch exams, they are always ordered
        # This makes the {% regroup %} logic in your HTML work perfectly
        ordering = ['year_of_study', 'semester', 'subject_name']
# 4. Fee Structure
class FeeStructure(models.Model):
    course = models.CharField(max_length=100, unique=True)
    semester_1 = models.DecimalField(max_digits=10, decimal_places=2)
    semester_2 = models.DecimalField(max_digits=10, decimal_places=2)
    semester_3 = models.DecimalField(max_digits=10, decimal_places=2)

# 5. Fee Balance
class FeeBalance(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='feebalance')
    sem1_bal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sem2_bal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sem3_bal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def total_due(self):
        return self.sem1_bal + self.sem2_bal + self.sem3_bal

## 6. Payment History
class Payment(models.Model):
    SEM_CHOICES = [('1', 'Semester 1'), ('2', 'Semester 2'), ('3', 'Semester 3')]
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    semester = models.CharField(max_length=1, choices=SEM_CHOICES)
    # Added the missing field that the view is looking for
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.amount} ({self.date.strftime('%Y-%m-%d')})"

# --- STORES MODELS ---

class Consumable(models.Model):
    item_name = models.CharField(max_length=200)
    date_supplied = models.DateField()
    balance_stock = models.PositiveIntegerField(default=0)
    last_date_issued = models.DateField(null=True, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.item_name} ({self.balance_stock} left)"

class PermanentEquipment(models.Model):
    CONDITION_CHOICES = [
        ('Good', 'Good'),
        ('Fair', 'Fair'),
        ('Damaged', 'Damaged'),
        ('Under Repair', 'Under Repair'),
    ]
    item_name = models.CharField(max_length=200)
    date_delivered = models.DateField()
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='Good')
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.item_name} - {self.condition}"
# --- SIGNALS ---
@receiver(post_save, sender=Student)
def create_student_financials(sender, instance, created, **kwargs):
    if created:
        try:
            struct = FeeStructure.objects.get(course=instance.course)
            FeeBalance.objects.create(
                student=instance,
                sem1_bal=struct.semester_1,
                sem2_bal=struct.semester_2,
                sem3_bal=struct.semester_3
            )
        except FeeStructure.DoesNotExist:
            FeeBalance.objects.create(student=instance)