from django import forms
from .models import Student, Examination, FeeStructure
from .models import Consumable, PermanentEquipment
from django.contrib.auth.models import User
from .models import UserProfile
#registration form that includes the department selection and the logic to reject the 3rd user.
class RegistrationForm(forms.ModelForm):
    # 1. Defining the 4 specific departments
    DEPARTMENT_CHOICES = [
        ('finance', 'Finance'),
        ('admissions', 'Admissions'),
        ('stores', 'Stores'),
        ('examinations', 'Examinations'),
    ]

    # 2. This creates the dropdown field
    department = forms.ChoiceField(
        choices=DEPARTMENT_CHOICES,
        label="Department to Access",
        required=True
    )
    
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        # 3. Added 'department' here so it renders in the HTML loop
        fields = ['username', 'email', 'password', 'department']

    def clean_department(self):
        dept = self.cleaned_data.get('department')
        # Logic: Check if 2 users already exist for this department
        existing_count = UserProfile.objects.filter(department=dept).count()
        if existing_count >= 2:
            raise forms.ValidationError(
                f"The {dept} department already has the maximum limit of 2 users."
            )
        return dept

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = '__all__'

class ExaminationForm(forms.ModelForm):
    class Meta:
        model = Examination
        # Match these exactly to your model fields
        fields = ['student', 'subject_name', 'marks', 'year_of_study', 'semester']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'subject_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mathematics'}),
            'marks': forms.NumberInput(attrs={'class': 'form-control'}),
            'year_of_study': forms.Select(attrs={'class': 'form-control'}),
            'semester': forms.Select(attrs={'class': 'form-control'}),
        }
class FeeForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = '__all__'


class ConsumableForm(forms.ModelForm):
    class Meta:
        model = Consumable
        fields = ['item_name', 'date_supplied', 'balance_stock', 'last_date_issued']
        widgets = {
            'date_supplied': forms.DateInput(attrs={'type': 'date'}),
            'last_date_issued': forms.DateInput(attrs={'type': 'date'}),
        }

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = PermanentEquipment
        fields = ['item_name', 'date_delivered', 'condition']
        widgets = {
            'date_delivered': forms.DateInput(attrs={'type': 'date'}),
        }