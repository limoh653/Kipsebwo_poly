from django import forms
from django.contrib.auth.models import User
from .models import Student, Examination, FeeStructure, Consumable, PermanentEquipment, UserProfile

# --- REGISTRATION FORM ---
class RegistrationForm(forms.ModelForm):
    DEPARTMENT_CHOICES = [
        ('finance', 'Finance'),
        ('admissions', 'Admissions'),
        ('stores', 'Stores'),
        ('examinations', 'Examinations'),
    ]

    department = forms.ChoiceField(
        choices=DEPARTMENT_CHOICES,
        label="Department to Access",
        required=True
    )
    
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'department']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_department(self):
        dept = self.cleaned_data.get('department')
        existing_count = UserProfile.objects.filter(department=dept).count()
        if existing_count >= 2:
            raise forms.ValidationError(
                f"The {dept} department already has the maximum limit of 2 users."
            )
        return dept

# --- STUDENT FORM ---
class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = '__all__'
        widgets = {
            'date_of_admission': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# --- EXAMINATION FORM ---
class ExaminationForm(forms.ModelForm):
    class Meta:
        model = Examination
        fields = ['student', 'subject_name', 'cat_1', 'cat_2', 'end_term', 'year_of_study', 'semester']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'subject_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mathematics'}),
            'cat_1': forms.NumberInput(attrs={'class': 'form-control'}),
            'cat_2': forms.NumberInput(attrs={'class': 'form-control'}),
            'end_term': forms.NumberInput(attrs={'class': 'form-control'}),
            'year_of_study': forms.Select(attrs={'class': 'form-control'}),
            'semester': forms.Select(attrs={'class': 'form-control'}),
        }

# --- FEE FORM ---
class FeeForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = '__all__'
        widgets = {
            'course': forms.TextInput(attrs={'placeholder': 'Enter Course Name'}),
            'financial_year': forms.TextInput(attrs={'placeholder': 'e.g. 2024/2025'}),
            'scholar_type': forms.Select(choices=[('Day Scholar', 'Day Scholar'), ('Boarder', 'Boarder')]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.required = False
            field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        for field_name in self.fields:
            if field_name not in ['course', 'financial_year', 'scholar_type']:
                value = cleaned_data.get(field_name)
                if value in [None, '']:
                    cleaned_data[field_name] = 0
        
        course = cleaned_data.get('course')
        scholar_type = cleaned_data.get('scholar_type')

        if not course:
            self.add_error('course', 'Please enter the course name.')
        if not scholar_type:
            self.add_error('scholar_type', 'Please select a scholar type.')
            
        return cleaned_data

# --- UPDATED STORES FORMS ---


class ConsumableForm(forms.ModelForm):
    class Meta:
        model = Consumable
        # 1. 'fields' must match the attribute names in models.py exactly
        fields = ['description_of_inventory_item', 'quantity', 'number_issued', 'balance_in_stock']
        widgets = {
            'description_of_inventory_item': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Item description'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}), # Fixed typo: quantiy -> quantity
            'number_issued': forms.NumberInput(attrs={'class': 'form-control'}), # Fixed typo: sforms -> forms
            'balance_in_stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Remaining stock'}),
        }

class EquipmentForm(forms.ModelForm):
    class Meta:
        model = PermanentEquipment
        fields = [
            'asset_description', 'serial_number', 'make_and_model', 
            'date_of_delivery', 'original_location', 'current_location', 
            'date_of_disposal', 'asset_condition', 'remarks'
        ]
        widgets = {
            'asset_description': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'make_and_model': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_delivery': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'original_location': forms.TextInput(attrs={'class': 'form-control'}),
            'current_location': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_disposal': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'asset_condition': forms.Select(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }