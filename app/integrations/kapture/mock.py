"""Mock Kapture client — same interface as KaptureClient, canned sample data.

Lets every journey run offline. Shapes mirror the API Contract samples exactly so
swapping to the real client needs no code change.
"""
from __future__ import annotations

import uuid


def _page(content: list) -> dict:
    return {
        "content": content,
        "number": 0, "size": 20, "totalElements": len(content),
        "totalPages": 1, "first": True, "last": True,
        "numberOfElements": len(content),
    }


_SAMPLE_OBJECT = {
    "objectid": "900000012345",
    "serial_no": "SN12345678",
    "brand": "RELIANCE",
    "fg_article": "ART001",
    "date_of_purchase": "2025-01-15T00:00:00.000+0000",
    "wty_start_date": "2025-01-15T00:00:00.000+0000",
    "wty_end_date": "2027-01-14T23:59:59.000+0000",
    "partner_no": "100000678",
    "sales_order_no": "6000012345",
}

_SAMPLE_CUSTOMER = {
    "first_name": "Rahul", "last_name": "Sharma",
    "primary_mobile_number": "9876543210", "email": "rahul@example.com",
    "bpid": "100000678",
    "address": {"house_no": "12", "street": "MG Road", "city": "Mumbai",
                "postal_code": "400001", "region": "MH", "country": "IN"},
}


class MockKaptureClient:
    def __init__(self, *_, **__):
        self.checksum_key = "mock"

    async def tr_listing(self, object_id, page=0, size=20):
        return _page([{"transaction_no": "7000045678", "object_id": object_id,
                       "user_stat_text": "Approved", "process_type": "ZFTR"}])

    async def sales_order_listing(self, object_id, page=0, size=20):
        return _page([{"sales_order": "6000012345", "customer_id": "100000678",
                       "invoice_value": 45000.0,
                       "items": [{"article": "ART001", "iobject_id": object_id,
                                  "article_status": "DLVD"}]}])

    async def service_order_listing(self, object_id, page=0, size=20):
        return _page([{"service_order_no": "8000012345", "user_status": "OPEN",
                       "ref_object_id": object_id, "technician": "100001234"}])

    async def service_order_details(self, service_order_no):
        return {"service_order_no": service_order_no, "user_status": "OPEN",
                "ref_object": _SAMPLE_OBJECT, "sold_to_customer": {
                    "fullname": "Rahul Sharma", "phone": "9876543210",
                    "city": "Mumbai", "postal_code": "400001"},
                "iris": {"product_category": "AC"}}

    async def complaint_listing(self, object_id, page=0, size=20):
        return _page([{"complaint_no": "7000099999", "status_code": "OPEN",
                       "category": "INSTALLATION", "sub_category": "DELAY"}])

    async def contract_listing(self, object_id, page=0, size=20):
        return _page([{"contract_no": "4000012345", "contract_type": "RCP",
                       "cont_status": "A", "rcp_sale_price": 4999.0,
                       "object_id": object_id}])

    async def service_order_request(self, service_req_no):
        return {"service_order_no": "8000012345", "service_status": "OPEN"}

    async def rcp_order_listing(self, object_id=None, mobile_no=None, page=0, size=20):
        return _page([{"customer": _SAMPLE_CUSTOMER,
                       "object": _SAMPLE_OBJECT,
                       "contracts": [{"contract_no": "4000012345",
                                      "contract_type": "RCP", "cont_status": "A",
                                      "rcp_sale_price": 4999.0,
                                      "object_id": _SAMPLE_OBJECT["objectid"]}]}])

    async def b2b_complaint_create(self, body, transaction_number):
        return {"complaint_return": {"crmcomplaintid": f"7{uuid.uuid4().int % 10**9:09d}"},
                "response": {"msgtype": "S", "msgdesc": "Complaint created (mock)"}}

    async def b2b_service_request_create(self, body, transaction_number):
        return {"serreq_return": {"crmservicerequestid": f"8{uuid.uuid4().int % 10**9:09d}"},
                "response": {"msgtype": "S", "msgdesc": "Service request created (mock)"}}
