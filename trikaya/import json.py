import requests
import frappe
from frappe.utils.pdf import get_pdf

SETTINGS_DOTYPE = "whatsapp app setting"  # your Single doctype (lowercase)

def _ok(extra=None):
    out = {"ok": True}
    if isinstance(extra, dict):
        out.update(extra)
    return out

def _fail(step, msg, extra=None):
    out = {"ok": False, "step": step, "message": msg}
    if isinstance(extra, dict):
        out.update(extra)
    return out

def _num(msisdn):
    msisdn = msisdn or ""
    return "".join(ch for ch in msisdn if ch.isdigit() or ch == "+")

def _caption(po):
    name = po.name
    supplier = po.get("supplier") or "-"
    total = po.get("grand_total", 0)
    currency = po.get("currency") or ""
    return "Purchase Order: {0} | Supplier: {1} | Total: {2} {3}".format(name, supplier, total, currency)

def _json_or_text(resp):
    try:
        return resp.json()
    except Exception:
        try:
            return {"text": (resp.text or "")[:2000]}
        except Exception:
            return {"text": ""}

def _read_settings():
    d = frappe.get_single(SETTINGS_DOTYPE)
    token = (d.get("token") or "").strip()
    base = (d.get("url") or "https://graph.facebook.com").strip().rstrip("/")
    ver = (d.get("version") or "v22.0").strip()
    pid = (d.get("phone_id") or "").strip()
    return {"token": token, "base": base, "ver": ver, "pid": pid}

def _upload(pdf_bytes, filename, s):
    url = "{0}/{1}/{2}/media".format(s["base"], s["ver"], s["pid"])
    hdr = {"Authorization": "Bearer {0}".format(s["token"])}
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    data = {"messaging_product": "whatsapp"}

    try:
        r = requests.post(url, headers=hdr, files=files, data=data, timeout=60)
    except Exception as e:
        return _fail("upload", "Network error while uploading: {0}".format(e), {"endpoint": url})

    if r.status_code >= 300:
        return _fail("upload", "Media upload failed", {
            "status_code": r.status_code,
            "response": _json_or_text(r),
            "endpoint": url
        })

    b = _json_or_text(r)
    mid = b.get("id")
    if not mid:
        return _fail("upload", "No media id returned", {"response": b, "endpoint": url})

    return _ok({"media_id": mid, "endpoint": url})

def _send(media_id, to_msisdn, filename, caption, s):
    url = "{0}/{1}/{2}/messages".format(s["base"], s["ver"], s["pid"])
    hdr = {"Authorization": "Bearer {0}".format(s["token"]), "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_msisdn,
        "type": "document",
        "document": {"id": media_id, "filename": filename, "caption": caption}
    }

    try:
        r = requests.post(url, headers=hdr, json=payload, timeout=60)
    except Exception as e:
        return _fail("send", "Network error while sending: {0}".format(e), {"endpoint": url, "payload": payload})

    if r.status_code >= 300:
        return _fail("send", "Send failed", {
            "status_code": r.status_code,
            "response": _json_or_text(r),
            "endpoint": url,
            "payload": payload
        })

    return _ok({"status_code": r.status_code, "response": _json_or_text(r), "endpoint": url, "payload": payload})

@frappe.whitelist()
def send_po_pdf_whatsapp(po_name, recipient_whatsapp_no, print_format=None, preview=0):
    """
    Uses Single Doctype 'whatsapp app setting' fields: token, url, version, phone_id.
    Returns a JSON dict (never throws).
    """
    try:
        s = _read_settings()
        if not s["token"]:
            return _fail("settings", "Token empty in {0}".format(SETTINGS_DOTYPE))
        if not s["pid"]:
            return _fail("settings", "Phone ID empty in {0}".format(SETTINGS_DOTYPE))

        po = frappe.get_doc("Purchase Order", po_name)
        html = frappe.get_print("Purchase Order", po_name, print_format=print_format)
        pdf_bytes = get_pdf(html)
        filename = "{0}.pdf".format(po_name)

        to = _num(recipient_whatsapp_no)
        if not to:
            return _fail("input", "Invalid WhatsApp number")

        is_preview = str(preview).lower() in ("1", "true", "yes")
        if is_preview:
            return _ok({
                "mode": "preview",
                "po": po_name,
                "caption": _caption(po),
                "pdf_size_bytes": len(pdf_bytes),
                "filename": filename,
                "to": to,
                "settings_used": {"url": s["base"], "version": s["ver"], "phone_id": s["pid"]}
            })

        up = _upload(pdf_bytes, filename, s)
        if not up.get("ok"):
            return up

        mid = up.get("media_id")
        if not mid:
            return _fail("upload", "No media id received", {"upload_result": up})

        return _send(mid, to, filename, _caption(po), s)

    except Exception as e:
        return _fail("server", "{0}: {1}".format(e.__class__.__name__, e), {"trace": frappe.get_traceback()})
