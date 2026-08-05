from django import forms
from django.core.exceptions import ValidationError
from datetime import date, datetime
from .models import ExpertAvailability
from .models import Review


class AvailabilitySlotForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text="Select a future date for consultation."
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )

    class Meta:
        model = ExpertAvailability
        fields = ['date', 'start_time', 'end_time']

    def clean_date(self):
        slot_date = self.cleaned_data.get('date')
        if slot_date < date.today():
            raise ValidationError("You cannot create schedule slots for past dates.")
        return slot_date

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        slot_date = cleaned_data.get('date')

        if start and end:
            if start >= end:
                raise ValidationError("End time must be strictly after the start time.")
            
            # Check for current date time validation
            if slot_date == date.today():
                current_time = datetime.now().time()
                if start <= current_time:
                    raise ValidationError("Start time for today's slot must be in the future.")
        return cleaned_data


class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(
        min_value=1, 
        max_value=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'min': '1', 
            'max': '5', 
            'placeholder': 'Rating (1 to 5)'
        })
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'Write your feedback about this consultation...'
        })
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']