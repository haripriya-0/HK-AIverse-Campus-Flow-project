import os
import re
from datetime import datetime, timedelta

from flask import Flask, redirect, render_template, request, send_from_directory, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import (
    get_all_students,
    get_department_permission_by_id,
    get_department_permissions_for_student,
    get_pending_department_permissions,
    get_db_connection,
    get_document_by_request_id,
    get_pending_requests,
    get_request_by_id,
    get_requests_for_student,
    get_student_attendance,
    get_timetable_for_date,
    get_user_by_email,
    get_user_by_id,
    get_user_by_student_id,
    initialize_database,
    save_document,
    save_department_permission,
    save_request,
    seed_demo_data,
    update_attendance_status,
    update_request_document_id,
    update_request_status,
    update_department_permission_status,
    USE_SQLITE,
)
from services.ai_service import extract_document_with_ai
from services.attendance import calculate_od_days, update_attendance_for_request
from services.ocr import extract_text_from_file, parse_ocr_text

app = Flask(__name__)
app.secret_key = 'leave-reconciliation-demo-secret'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}


def normalize_date_value(value):
    if not value:
        return value
    value = str(value).strip()
    if not value:
        return value
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y', '%d.%m.%y', '%Y/%m/%d', '%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return value


def format_date_for_display(value):
    if not value:
        return value
    value = str(value).strip()
    if not value:
        return value
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y', '%d.%m.%y', '%Y/%m/%d', '%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%d-%m-%Y')
        except ValueError:
            pass
    return value


@app.context_processor
def inject_global_helpers():
    return {'get_user_by_id': get_user_by_id, 'format_date_for_display': format_date_for_display}


def login_required(role=None):
    def decorator(func):
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('login'))
            user = get_user_by_id(session['user_id'])
            if not user:
                session.clear()
                flash('Session expired. Please log in again.', 'warning')
                return redirect(url_for('login'))
            if role and user['role'] != role:
                flash('You do not have access to this page.', 'danger')
                return redirect(get_role_dashboard(user['role']))
            return func(*args, **kwargs)
        wrapped.__name__ = func.__name__
        return wrapped
    return decorator


def get_role_dashboard(role):
    dashboards = {
        'student': 'student_dashboard',
        'coordinator': 'coordinator_dashboard',
        'hod': 'hod_dashboard',
    }
    return dashboards.get(role, 'login')


def get_role_routes():
    return {
        'student': 'student_dashboard',
        'coordinator': 'coordinator_dashboard',
        'hod': 'hod_dashboard',
    }


def create_demo_request_data():
    return {
        'student_id': 'STU-101',
        'request_type': 'OD - official college activities',
        'start_date': '2026-09-12',
        'end_date': '2026-09-12',
        'start_time': '09:00:00',
        'end_time': '12:00:00',
        'reason': 'Academic event participation',
        'organization_name': 'TechHub Solutions',
        'status': 'Pending Coordinator',
        'coordinator_note': '',
        'hod_note': '',
    }


@app.route('/')
def index():
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            return redirect(url_for(get_role_routes()[user['role']]))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = get_user_by_email(email)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            flash('Login successful.', 'success')
            return redirect(url_for(get_role_dashboard(user['role'])))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    user = get_user_by_id(session['user_id'])
    attendance = get_student_attendance(user['student_id'])
    requests = get_requests_for_student(user['student_id'])
    permissions = get_department_permissions_for_student(user['student_id'])
    return render_template('student_dashboard.html', user=user, attendance=attendance, requests=requests, permissions=permissions)


@app.route('/student/department-permissions', methods=['GET', 'POST'])
@login_required('student')
def department_permission_submit():
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        event_date = request.form.get('date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        form_data = {
            'event_name': request.form.get('event_name', '').strip(),
            'organization': request.form.get('organization', '').strip(),
            'date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'venue': request.form.get('venue', '').strip(),
            'purpose': request.form.get('purpose', '').strip(),
            'reason': request.form.get('reason', '').strip(),
        }
        if not form_data['event_name'] or not event_date or not start_time or not end_time or not form_data['purpose']:
            flash('Event name, date, start time, end time, and purpose are required.', 'danger')
            return render_template('department_permission_submit.html', user=user, form_data=form_data)
        try:
            datetime.strptime(event_date, '%Y-%m-%d')
            parsed_start = datetime.strptime(start_time, '%H:%M')
            parsed_end = datetime.strptime(end_time, '%H:%M')
        except ValueError:
            flash('Enter a valid date and time.', 'danger')
            return render_template('department_permission_submit.html', user=user, form_data=form_data)
        if parsed_end <= parsed_start:
            flash('End time must be after start time.', 'danger')
            return render_template('department_permission_submit.html', user=user, form_data=form_data)

        document_path = None
        uploaded_file = request.files.get('document')
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if file_ext not in ALLOWED_EXTENSIONS:
                flash('Unsupported document type. Upload PNG, JPG, JPEG, or PDF.', 'danger')
                return render_template('department_permission_submit.html', user=user, form_data=form_data)
            document_path = f"permission_{user['student_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], document_path))

        permission_id = save_department_permission({
            **form_data,
            'student_id': user['student_id'],
            'document_path': document_path,
            'status': 'Pending Coordinator',
        })
        flash('Department permission submitted successfully.', 'success')
        return redirect(url_for('department_permission_detail', permission_id=permission_id))
    return render_template('department_permission_submit.html', user=user, form_data={})


@app.route('/student/department-permissions/list')
@login_required('student')
def department_permissions():
    user = get_user_by_id(session['user_id'])
    permissions = get_department_permissions_for_student(user['student_id'])
    return render_template('department_permissions.html', user=user, permissions=permissions)


@app.route('/student/department-permissions/<int:permission_id>')
@login_required('student')
def department_permission_detail(permission_id):
    user = get_user_by_id(session['user_id'])
    permission = get_department_permission_by_id(permission_id)
    if not permission or permission['student_id'] != user['student_id']:
        flash('Permission request not found.', 'danger')
        return redirect(url_for('department_permissions'))
    return render_template('department_permission_detail.html', user=user, permission=permission, student_view=True)


@app.route('/student/submit-request', methods=['GET', 'POST'])
@login_required('student')
def submit_request():
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        request_type = request.form.get('request_type')
        start_date = normalize_date_value(request.form.get('start_date'))
        end_date = normalize_date_value(request.form.get('end_date'))
        reason = request.form.get('reason')
        uploaded_file = request.files.get('document')
        start_time = '09:00:00'
        end_time = '17:00:00'

        if not all([request_type, start_date, end_date, reason]):
            flash('Please fill in all required fields.', 'danger')
            return render_template('submit_request.html', user=user)

        ocr_data = {'name': None, 'date': None, 'leave_from': None, 'leave_to': None, 'organization': None, 'raw_text': ''}
        if uploaded_file and uploaded_file.filename:
            filename = secure_filename(uploaded_file.filename)
            if '.' in filename:
                file_ext = filename.rsplit('.', 1)[1].lower()
            else:
                file_ext = ''
            if file_ext not in ALLOWED_EXTENSIONS:
                flash('Unsupported document type. Upload PNG, JPG, JPEG, or PDF.', 'danger')
                return render_template('submit_request.html', user=user)

            storage_name = f"{user['student_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], storage_name)
            uploaded_file.save(file_path)

            raw_text = extract_text_from_file(file_path)
            ocr_data = parse_ocr_text(raw_text)
            if not raw_text:
                if file_ext in {'png', 'jpg', 'jpeg'}:
                    flash('OCR could not read the uploaded image because Tesseract is not installed on this machine. Install Tesseract OCR to enable document scanning.', 'warning')
                ocr_data = {'name': None, 'date': None, 'leave_from': None, 'leave_to': None, 'organization': None, 'raw_text': ''}

            if raw_text:
                ai_data = extract_document_with_ai(raw_text, filename)
                if ai_data:
                    for key in ['name', 'date', 'organization']:
                        if ai_data.get(key) and not ocr_data.get(key):
                            ocr_data[key] = ai_data.get(key)

            if ocr_data.get('leave_from'):
                start_date = normalize_date_value(ocr_data['leave_from'])
            if ocr_data.get('leave_to'):
                end_date = normalize_date_value(ocr_data['leave_to'])

            if not raw_text:
                flash('No readable text was detected in the uploaded document. The file was saved, but OCR and AI could not extract details.', 'warning')

        request_payload = {
            'student_id': user['student_id'],
            'request_type': request_type,
            'start_date': start_date,
            'end_date': end_date,
            'start_time': start_time,
            'end_time': end_time,
            'reason': reason,
            'organization_name': ocr_data.get('organization') or '',
            'status': 'Pending Coordinator',
            'coordinator_note': '',
            'hod_note': '',
        }
        request_id = save_request(request_payload, None)

        if uploaded_file and uploaded_file.filename:
            storage_name = f"{user['student_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(uploaded_file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], storage_name)
            uploaded_file.save(file_path)
            document_id = save_document(
                request_id,
                storage_name,
                secure_filename(uploaded_file.filename),
                ocr_data.get('raw_text', ''),
                ocr_data.get('name'),
                ocr_data.get('leave_from') or ocr_data.get('date'),
                None,
                ocr_data.get('organization'),
            )
            update_request_document_id(request_id, document_id)

        flash('Request submitted successfully and sent to the coordinator.', 'success')
        return redirect(url_for('student_dashboard'))

    return render_template('submit_request.html', user=user)


@app.route('/student/my-requests')
@login_required('student')
def my_requests():
    user = get_user_by_id(session['user_id'])
    requests = get_requests_for_student(user['student_id'])
    for req in requests:
        doc = get_document_by_request_id(req['id'])
        req['document'] = doc
    return render_template('my_requests.html', user=user, requests=requests)


@app.route('/student/attendance')
@login_required('student')
def student_attendance():
    user = get_user_by_id(session['user_id'])
    attendance = get_student_attendance(user['student_id'])
    return render_template('student_attendance.html', user=user, attendance=attendance)


@app.route('/coordinator/dashboard')
@login_required('coordinator')
def coordinator_dashboard():
    pending = get_pending_requests('Pending Coordinator')
    for req in pending:
        doc = get_document_by_request_id(req['id'])
        student = get_user_by_student_id(req['student_id'])
        req['document'] = doc
        req['student'] = student
    permission_pending = get_pending_department_permissions('Pending Coordinator')
    for permission in permission_pending:
        permission['student'] = get_user_by_student_id(permission['student_id'])
    return render_template('coordinator_dashboard.html', requests=pending, permission_requests=permission_pending)


@app.route('/coordinator/department-permission/<int:permission_id>', methods=['GET', 'POST'])
@login_required('coordinator')
def coordinator_permission_detail(permission_id):
    permission = get_department_permission_by_id(permission_id)
    if not permission or permission['status'] != 'Pending Coordinator':
        flash('Department permission request is not awaiting coordinator review.', 'warning')
        return redirect(url_for('coordinator_dashboard'))
    student = get_user_by_student_id(permission['student_id'])
    if request.method == 'POST':
        action = request.form.get('action')
        remark = request.form.get('coordinator_remark', '').strip()
        if action == 'approve':
            update_department_permission_status(permission_id, 'Pending HOD', coordinator_remark=remark)
            flash('Department permission approved and sent to the HOD.', 'success')
        elif action == 'reject':
            update_department_permission_status(permission_id, 'Rejected', coordinator_remark=remark)
            flash('Department permission rejected.', 'warning')
        return redirect(url_for('coordinator_dashboard'))
    return render_template('department_permission_review.html', permission=permission, student=student, reviewer='Coordinator')


@app.route('/coordinator/request/<int:request_id>', methods=['GET', 'POST'])
@login_required('coordinator')
def coordinator_request_detail(request_id):
    request_record = get_request_by_id(request_id)
    if not request_record:
        flash('Request not found.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    document = get_document_by_request_id(request_id)
    student = get_user_by_student_id(request_record['student_id'])
    if request.method == 'POST':
        action = request.form.get('action')
        note = request.form.get('coordinator_note', '').strip()
        if action == 'approve':
            update_request_status(request_id, 'Pending HOD', coordinator_note=note)
            flash('Request approved and sent to the HOD.', 'success')
        elif action == 'reject':
            update_request_status(request_id, 'Rejected', coordinator_note=note)
            flash('Request rejected.', 'warning')
        return redirect(url_for('coordinator_dashboard'))
    return render_template('coordinator_request_detail.html', request_record=request_record, document=document, student=student)


@app.route('/hod/dashboard')
@login_required('hod')
def hod_dashboard():
    pending = get_pending_requests('Pending HOD')
    for req in pending:
        doc = get_document_by_request_id(req['id'])
        student = get_user_by_student_id(req['student_id'])
        req['document'] = doc
        req['student'] = student
        req['od_days'] = calculate_od_days(req['start_date'], req['end_date'])
    permission_pending = get_pending_department_permissions('Pending HOD')
    for permission in permission_pending:
        permission['student'] = get_user_by_student_id(permission['student_id'])
    return render_template('hod_dashboard.html', requests=pending, permission_requests=permission_pending)


@app.route('/hod/department-permission/<int:permission_id>', methods=['GET', 'POST'])
@login_required('hod')
def hod_permission_detail(permission_id):
    permission = get_department_permission_by_id(permission_id)
    if not permission or permission['status'] != 'Pending HOD':
        flash('Department permission request is not awaiting HOD review.', 'warning')
        return redirect(url_for('hod_dashboard'))
    student = get_user_by_student_id(permission['student_id'])
    if request.method == 'POST':
        action = request.form.get('action')
        remark = request.form.get('hod_remark', '').strip()
        if action == 'approve':
            update_department_permission_status(permission_id, 'Approved', permission.get('coordinator_remark'), remark)
            flash('Department permission approved.', 'success')
        elif action == 'reject':
            update_department_permission_status(permission_id, 'Rejected', permission.get('coordinator_remark'), remark)
            flash('Department permission rejected.', 'warning')
        return redirect(url_for('hod_dashboard'))
    return render_template('department_permission_review.html', permission=permission, student=student, reviewer='HOD')


@app.route('/hod/request/<int:request_id>', methods=['GET', 'POST'])
@login_required('hod')
def hod_request_detail(request_id):
    request_record = get_request_by_id(request_id)
    if not request_record:
        flash('Request not found.', 'danger')
        return redirect(url_for('hod_dashboard'))
    student = get_user_by_student_id(request_record['student_id'])
    document = get_document_by_request_id(request_id)
    od_days = calculate_od_days(request_record['start_date'], request_record['end_date'])
    exceeded = od_days > 10

    timetable_rows = []
    current = datetime.strptime(request_record['start_date'], '%Y-%m-%d')
    last = datetime.strptime(request_record['end_date'], '%Y-%m-%d')
    while current <= last:
        date_value = current.strftime('%Y-%m-%d')
        timetable_rows.append({
            'date': date_value,
            'periods': get_timetable_for_date(date_value),
        })
        current += timedelta(days=1)

    if request.method == 'POST':
        action = request.form.get('action')
        hod_note = request.form.get('hod_note', '').strip()
        reason_override = request.form.get('override_reason', '').strip()

        if action == 'approve':
            if exceeded and not reason_override:
                flash('This OD exceeds the 10-day limit. Please enter a reason to override.', 'warning')
                return render_template('hod_request_detail.html', request_record=request_record, document=document, student=student, od_days=od_days, exceeded=exceeded, timetable_rows=timetable_rows)
            update_request_status(request_id, 'Approved', coordinator_note=request_record.get('coordinator_note'), hod_note=hod_note)
            update_attendance_for_request(request_record)
            update_request_status(request_id, 'Attendance Updated', coordinator_note=request_record.get('coordinator_note'), hod_note=hod_note)
            flash('Request approved and attendance updated.', 'success')
        elif action == 'reject':
            update_request_status(request_id, 'Rejected', coordinator_note=request_record.get('coordinator_note'), hod_note=hod_note)
            flash('Request rejected.', 'warning')
        return redirect(url_for('hod_dashboard'))

    return render_template('hod_request_detail.html', request_record=request_record, document=document, student=student, od_days=od_days, exceeded=exceeded, timetable_rows=timetable_rows)


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)


@app.route('/health')
def health_check():
    return {'status': 'ok'}


if __name__ == '__main__':
    initialize_database()
    seed_demo_data()
    app.run(debug=True, host='0.0.0.0', port=5000)
1