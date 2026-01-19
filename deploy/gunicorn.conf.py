# Gunicorn configuration for production deployment

# Bind to localhost - Caddy will proxy requests
bind = "127.0.0.1:8000"

# Worker configuration
workers = 2  # Adjust based on droplet CPU cores (2 * cores + 1)
worker_class = "sync"
threads = 4

# Timeouts
timeout = 120  # API calls to OpenAlex can be slow
keepalive = 5

# Logging
accesslog = "/var/log/openalex-digger/access.log"
errorlog = "/var/log/openalex-digger/error.log"
loglevel = "info"

# Process naming
proc_name = "openalex-digger"

# Security
limit_request_line = 4096
limit_request_fields = 100

