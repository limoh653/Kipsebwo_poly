from django import forms
from .models import Student, Examination, FeeStructure
from .models import Consumable, PermanentEquipment

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