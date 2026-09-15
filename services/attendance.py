from datetime import datetime, timedelta

from database import get_attendance_subjects_for_date, get_timetable_for_date, update_attendance_status_for_subjects


def parse_date(value):
    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%y', '%d/%m/%y', '%d.%m.%y', '%Y/%m/%d', '%d %B %Y', '%d %b %Y'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f'Unsupported date format: {value}')


def calculate_od_days(start_date, end_date):
    start = parse_date(start_date)
    end = parse_date(end_date)
    return (end - start).days + 1


def parse_time(value):
    value = str(value).strip()
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            pass
    raise ValueError(f'Unsupported time format: {value}')


def update_attendance_for_request(request):
    student_id = request['student_id']
    start_date = request['start_date']
    end_date = request['end_date']
    start_time = request['start_time']
    end_time = request['end_time']
    request_type = request['request_type'] or ''
    is_od = str(request_type).lower().startswith('od')
    status_label = 'Present (OD - official college activities)' if is_od else 'Present (Medical Leave)'

    current = parse_date(start_date)
    last = parse_date(end_date)

    while current <= last:
        date_value = current.strftime('%Y-%m-%d')
        timetable = get_timetable_for_date(date_value)
        req_start = datetime.combine(current.date(), parse_time(start_time))
        req_end = datetime.combine(current.date(), parse_time(end_time))
        matching_subjects = []
        for period in timetable:
            period_start = datetime.combine(current.date(), parse_time(period['start_time']))
            period_end = datetime.combine(current.date(), parse_time(period['end_time']))

            if req_start < period_end and req_end > period_start:
                matching_subjects.append(period['subject'])
        if not matching_subjects:
            matching_subjects = get_attendance_subjects_for_date(student_id, date_value)
        update_attendance_status_for_subjects(student_id, matching_subjects, date_value, status_label)
        current += timedelta(days=1)

    return True
