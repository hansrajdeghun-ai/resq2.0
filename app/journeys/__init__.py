"""Import every journey module so its @on(...) handlers register with the router."""
from app.journeys import shared_assign  # noqa: F401  (job_accept/decline/assign)
from app.journeys import shared_visit  # noqa: F401  (travel/serial/extras/work/confirm)
from app.journeys import j1_installation  # noqa: F401
from app.journeys import j2_repair  # noqa: F401
from app.journeys import j3_repair_with_part  # noqa: F401
from app.journeys import j4_out_of_warranty  # noqa: F401
from app.journeys import j5_brand_repair  # noqa: F401
from app.journeys import j6_walk_in  # noqa: F401
from app.journeys import j7_doa  # noqa: F401
from app.journeys import j8_house_move  # noqa: F401
from app.journeys import j9_care_plan  # noqa: F401
from app.journeys import j10_complaint  # noqa: F401
from app.journeys import j11_sale_delivery  # noqa: F401
from app.journeys import j12_roster  # noqa: F401
from app.journeys import j13_payouts  # noqa: F401
from app.journeys import misc  # noqa: F401
from app.journeys import exceptions_extra  # noqa: F401
from app.monitoring import handlers as monitoring_handlers  # noqa: F401

__all__ = ["shared_assign", "shared_visit"]
