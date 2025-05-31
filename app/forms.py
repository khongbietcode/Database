from django import forms
from .models import PersonalAttendanceSetting

class PersonalAttendanceSettingForm(forms.ModelForm):
    class Meta:
        model = PersonalAttendanceSetting
        fields = ['user', 'date', 'checkin_time', 'checkout_time']  # Thêm checkout_time
        labels = {
            'user': 'Tên nhân viên',
            'date': 'Ngày',
            'checkin_time': 'Giờ vào ca',
            'checkout_time': 'Giờ ra ca',  # Thêm dòng này
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'checkin_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'checkout_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),  # Thêm dòng này
            'user': forms.Select(attrs={'class': 'form-control'}),
        }