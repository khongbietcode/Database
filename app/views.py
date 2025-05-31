from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
import app.mqtt_client 
from django.http import JsonResponse
from app.mqtt_client import publish_message
from app.models import CardEvent, CardUser, PersonalAttendanceSetting
from .forms import  PersonalAttendanceSettingForm
from datetime import datetime
from django.core.mail import send_mail
import secrets
import string
from django.utils import timezone



# Store the latest received MQTT message (for demo)
latest_esp32_message = None

def is_admin(user):
    return user.is_superuser

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            authenticated_user = authenticate(request, username=user.username, password=password)
            
            if authenticated_user is not None:
                login(request, authenticated_user)
                if authenticated_user.is_superuser:
                    return redirect('admin_menu')
                else:
                    return redirect('user_menu')
            else:
                messages.error(request, 'Email hoặc mật khẩu không đúng')
        except User.DoesNotExist:
            messages.error(request, 'Email không tồn tại trong hệ thống')
    
    return render(request, 'app/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
@user_passes_test(is_admin)
def admin_menu(request):
    context = {
        'total_users': User.objects.count(),
        'admin_count': User.objects.filter(is_superuser=True).count(),
        'user_count': User.objects.filter(is_superuser=False).count(),
        'user': request.user
    }
    return render(request, 'app/admin_menu.html', context)


@login_required
def user_menu(request):
    if request.user.is_superuser:
        return redirect('admin_menu')
    
    context = {
        'user': request.user
    }
    return render(request, 'app/user_menu.html', context)

def generate_random_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

@login_required
@user_passes_test(is_admin)
def user_management(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = generate_random_password()      # Sinh ngẫu nhiên
        confirm_password = password                # Để luôn đúng
        is_admin = request.POST.get('is_admin') == 'on'
        custom_card_id = request.POST.get('custom_card_id')

        if password != confirm_password:
            messages.error(request, 'Mật khẩu không khớp')
            return redirect('user_management')

        try:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Tên đăng nhập đã tồn tại')
                return redirect('user_management')
            
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email đã tồn tại')
                return redirect('user_management')
            
            if custom_card_id and CardUser.objects.filter(card_id=custom_card_id).exists():
                messages.error(request, f'Card ID {custom_card_id} đã tồn tại.')
                return redirect('user_management')
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            if custom_card_id:
                CardUser.objects.create(user=user, card_id=custom_card_id)

            if is_admin:
                user.is_superuser = True
                user.is_staff = True
                user.save()

            # Gửi mail thông báo
            send_mail(
                'Tài khoản mới đã được tạo',
                '',  # Để trống nếu chỉ gửi HTML
                None,
                [email],
                fail_silently=False,
                html_message=f"""
                <html>
                <body style="font-family: Arial, sans-serif; background: #f6f6f6; padding: 30px;">
                    <div style="max-width: 500px; margin: auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #eee; padding: 24px;">
                        <h2 style="color: #007bff;">Chào mừng bạn đến với công ty UIT!</h2>
                        <p>Xin chào <b>{username}</b>,</p>
                        <p>Tài khoản của bạn đã được tạo thành công với các thông tin sau:</p>
                        <ul>
                            <li><b>Tên Nhân Viên:</b> {username}</li>
                            <li><b>Email:</b> {email}</li>
                            <li><b>Mật khẩu:</b> {password}</li>
                        </ul>
                        <p>Vui lòng đăng nhập và đổi mật khẩu sau khi sử dụng lần đầu.</p>
                        <hr>
                        <p style="font-size: 13px; color: #888;">Đây là email tự động, vui lòng không trả lời email này.</p>
                    </div>
                </body>
                </html>
                """
            )

            messages.success(request, 'Tạo nhân viên và Card ID thành công')
            return redirect('user_management')

        except Exception as e:
            messages.error(request, f'Lỗi: {str(e)}')
            return redirect('user_management')

    users = User.objects.all().select_related('carduser').order_by('-date_joined')
    return render(request, 'app/user_management.html', {'users': users})

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    try:
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            messages.error(request, 'Không thể xóa tài khoản của chính mình')
            return redirect('user_management')
        
        user.delete()
        messages.success(request, 'Xóa nhân viên thành công')
    except User.DoesNotExist:
        messages.error(request, 'Không tìm thấy nhân viên')
    return redirect('user_management')

@login_required
@user_passes_test(is_admin)
def edit_user(request, user_id):
    user_to_edit = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        is_admin = request.POST.get('is_admin') == 'on'
        
        try:
            if User.objects.exclude(id=user_id).filter(username=username).exists():
                messages.error(request, 'Tên đăng nhập đã tồn tại')
                return redirect('edit_user', user_id=user_id)

            user_to_edit.username = username
            user_to_edit.email = email
            user_to_edit.is_superuser = is_admin
            user_to_edit.is_staff = is_admin
            
            if new_password:
                user_to_edit.set_password(new_password)
            
            user_to_edit.save()
            messages.success(request, 'Cập nhật nhân viên thành công')
            return redirect('user_management')
            
        except Exception as e:
            messages.error(request, f'Lỗi: {str(e)}')
            
    return render(request, 'app/edit_user.html', {'edit_user': user_to_edit})

@login_required
def personal_info(request):
    user = request.user
    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        try:
            if User.objects.exclude(id=user.id).filter(email=email).exists():
                messages.error(request, 'Email đã tồn tại')
                return redirect('personal_info')
            user.email = email
            if new_password:
                user.set_password(new_password)
            user.save()
            messages.success(request, 'Cập nhật thông tin thành công')
            if new_password:
                login(request, user)
            return redirect('personal_info')
        except Exception as e:
            messages.error(request, f'Lỗi: {str(e)}')
    return render(request, 'app/personal_info.html', {'user': user})

@login_required
def change_password(request):
    user = request.user
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if not user.check_password(old_password):
            messages.error(request, 'Mật khẩu cũ không đúng')
        elif new_password != confirm_password:
            messages.error(request, 'Mật khẩu mới không khớp')
        else:
            user.set_password(new_password)
            user.save()
            messages.success(request, 'Đổi mật khẩu thành công')
            login(request, user)
            return redirect('change_password')
    return render(request, 'app/change_password.html', {'user': user})


@login_required
def report_view(request):
    events = CardEvent.objects.select_related('user').order_by('-created_at')
    event_list = []
    for event in events:
        try:
            setting = PersonalAttendanceSetting.objects.filter(
                user=event.user,
                date=event.created_at.date()
            ).first()
            status = ''
            if setting:
                event_time = event.created_at.time()
                # Chuyển event_dt về naive để phép trừ không lỗi
                event_dt = event.created_at
                if timezone.is_aware(event_dt):
                    event_dt = event_dt.astimezone(timezone.get_current_timezone()).replace(tzinfo=None)
                checkin_dt = datetime.combine(event_dt.date(), setting.checkin_time)

                print(f"event_dt: {event_dt}, checkin_dt: {checkin_dt}, event_dt < checkin_dt: {event_dt < checkin_dt}, event_dt > checkin_dt: {event_dt > checkin_dt}")

                if event_dt < checkin_dt:
                    # Điểm danh sớm
                    time_difference = checkin_dt - event_dt
                    total_seconds = int(time_difference.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    status = f"Sớm {hours:02d}:{minutes:02d}:{seconds:02d}"
                elif event_dt > checkin_dt:
                    # Điểm danh trễ
                    time_difference = event_dt - checkin_dt
                    total_seconds = int(time_difference.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    status = f"Trễ {hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    status = "Đúng giờ"
            else:
                status = "Không có cấu hình"
        except Exception as e:
            print(f"Lỗi với event {event.id}: {e}")
            status = "Lỗi xử lý"
        
        event_list.append({
            'card_id': event.card_id,
            'user': event.user,
            'created_at': event.created_at,
            'status': status,
        })
    return render(request, 'app/report.html', {'events': event_list})

@login_required
def clear_events(request):
    CardEvent.objects.all().delete()
    return redirect('report')

@login_required
@user_passes_test(is_admin)
def personal_attendance_setting_view(request):
    settings = PersonalAttendanceSetting.objects.select_related('user').order_by('-date')
    if request.method == 'POST':
        form = PersonalAttendanceSettingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã lưu cài đặt giờ điểm danh cá nhân.')
            return redirect('personal_attendance_setting')
    else:
        form = PersonalAttendanceSettingForm()
    return render(request, 'app/personal_attendance_setting.html', {'form': form, 'settings': settings})

@login_required
@user_passes_test(is_admin)
def delete_personal_attendance_setting(request, setting_id):
    setting = get_object_or_404(PersonalAttendanceSetting, id=setting_id)
    setting.delete()
    messages.success(request, 'Đã xóa cài đặt giờ điểm danh cá nhân.')
    return redirect('personal_attendance_setting')

@login_required
@user_passes_test(is_admin)
def edit_personal_attendance_setting(request, setting_id):
    setting = get_object_or_404(PersonalAttendanceSetting, id=setting_id)
    if request.method == 'POST':
        form = PersonalAttendanceSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã cập nhật cài đặt giờ điểm danh cá nhân.')
            return redirect('personal_attendance_setting')
    else:
        form = PersonalAttendanceSettingForm(instance=setting)
    return render(request, 'app/edit_personal_attendance_setting.html', {'form': form, 'setting': setting})

@login_required
def my_attendance_settings(request):
    settings = PersonalAttendanceSetting.objects.filter(user=request.user).order_by('-date')
    return render(request, 'app/my_attendance_settings.html', {'settings': settings})