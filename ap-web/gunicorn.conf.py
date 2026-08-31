bind = "0.0.0.0:5001"
workers = 1
threads = 4
# preload_app=False so the app + its background threads (FEAT-04 deadline
# sweeper, FEAT-17 tracker_ws) initialise INSIDE each worker process, not
# in the master before fork. Threads started before fork don't run in the
# child - that broke FEAT-17's WebSocket connections (master had them,
# worker handling /api/admin/tracker_ws did not). With workers=1 the
# memory/startup-cost penalty of disabling preload is essentially zero.
preload_app = False
accesslog = "-"
errorlog = "-"
# Privacy-minimised request log: path without query string, no client IP,
# User-Agent or referrer. In particular this keeps Discord OAuth codes/state
# out of the container log while preserving status/latency evidence.
access_log_format = '%(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
