from django import forms
from .models import Student, Examination, FeeStructure, StoreItem

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

class StoreForm(forms.ModelForm):
    class Meta:
        model = StoreItem
        fields = '__all__'