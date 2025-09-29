import structlog

structlog.configure(
    # wrapper_class=structlog.make_filtering_bound_logger(40)
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.EventRenamer("log"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()