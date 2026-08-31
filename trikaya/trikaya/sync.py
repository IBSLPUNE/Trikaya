import frappe
import requests
from frappe.utils import get_datetime, now_datetime, today, cstr
from datetime import datetime

def sync_attendance():
	settings = frappe.get_single("Attendance Sync Settings")

	if not settings.enabled:
		return

	if not settings.api_url or not settings.app_key or not settings.sync_from:
		frappe.log_error(
			title="Attendance Sync: Missing Settings",
			message="API URL, App Key or Sync From is not set in Attendance Sync Settings",
		)
		return

	device_directions = {}
	for row in settings.device_mapping:
		device_id = cstr(row.device_id).strip()
		device_directions.setdefault(device_id, set()).add(row.direction)

	sync_from_dt = get_datetime(settings.sync_from)
	start_date = sync_from_dt.strftime("%Y-%m-%d")
	end_date = today()

	url = "{0}?AppKey={1}&StartDate={2}&EndDate={3}".format(
		settings.api_url.strip().rstrip("?"), settings.app_key, start_date, end_date
	)

	created, skipped, unmatched_employee, unmapped_device, failed = 0, 0, 0, 0, 0
	max_log_dt = sync_from_dt

	try:
		response = requests.get(url, timeout=60)
		response.raise_for_status()
		records = response.json()
	except Exception:
		frappe.log_error(title="Attendance Sync: API Call Failed", message=frappe.get_traceback())
		settings.db_set("last_sync_status", "Failed to fetch data from API. Check Error Log.")
		settings.db_set("last_sync_time", now_datetime())
		frappe.db.commit()
		return

	if not isinstance(records, list):
		frappe.log_error(
			title="Attendance Sync: Unexpected Response",
			message=frappe.as_json(records)[:5000],
		)
		settings.db_set("last_sync_status", "Unexpected response format from API. Check Error Log.")
		settings.db_set("last_sync_time", now_datetime())
		frappe.db.commit()
		return

	parsed = []
	for record in records:
		try:
			log_dt = datetime.strptime(record.get("LogDate"), "%d-%b-%Y %H:%M")
		except Exception:
			failed += 1
			continue

		if log_dt <= sync_from_dt:
			continue  # already synced in a previous run

		parsed.append((log_dt, record))

	parsed.sort(key=lambda x: x[0])

	day_counts = {}

	for log_dt, record in parsed:
		employee_code = cstr(record.get("EmployeeCode")).strip()
		device_id = cstr(record.get("DeviceId")).strip()

		directions = device_directions.get(device_id)
		if not directions:
			unmapped_device += 1
			if log_dt > max_log_dt:
				max_log_dt = log_dt
			continue

		employee = frappe.db.get_value("Employee", {"attendance_device_id": employee_code}, "name")
		if not employee:
			unmatched_employee += 1
			if log_dt > max_log_dt:
				max_log_dt = log_dt
			continue

		exists = frappe.db.exists(
			"Employee Checkin", {"employee": employee, "time": log_dt}
		)

		if exists:
			skipped += 1
			if log_dt > max_log_dt:
				max_log_dt = log_dt
			continue

		if len(directions) == 1:
			log_type = next(iter(directions))
		else:
			log_type = _next_alternating_type(employee, log_dt, day_counts)

		try:
			doc = frappe.new_doc("Employee Checkin")
			doc.employee = employee
			doc.time = log_dt
			doc.log_type = log_type
			doc.device_id = device_id
			doc.insert(ignore_permissions=True)
			created += 1
		except Exception:
			failed += 1
			frappe.log_error(
				title="Attendance Sync: Checkin Insert Failed",
				message="{0}\nRecord: {1}".format(frappe.get_traceback(), frappe.as_json(record)),
			)

		if log_dt > max_log_dt:
			max_log_dt = log_dt

	settings.db_set("sync_from", max_log_dt)
	settings.db_set("last_sync_time", now_datetime())
	status = (
		"Created: {0}, Already Synced: {1}, Unmapped Device: {2}, "
		"Employee Not Found: {3}, Failed: {4}"
	).format(created, skipped, unmapped_device, unmatched_employee, failed)
	settings.db_set("last_sync_status", status)
	frappe.db.commit()


def _next_alternating_type(employee, log_dt, day_counts):

	day_key = (employee, log_dt.date())

	if day_key not in day_counts:
		day_start = datetime.combine(log_dt.date(), datetime.min.time())
		day_end = datetime.combine(log_dt.date(), datetime.max.time())
		day_counts[day_key] = frappe.db.count(
			"Employee Checkin",
			{"employee": employee, "time": ["between", [day_start, day_end]]},
		)

	count = day_counts[day_key]
	log_type = "IN" if count % 2 == 0 else "OUT"
	day_counts[day_key] = count + 1
	return log_type


@frappe.whitelist()
def sync_now():
	frappe.only_for(["System Manager", "HR Manager"])
	sync_attendance()
	settings = frappe.get_single("Attendance Sync Settings")
	return settings.last_sync_status
