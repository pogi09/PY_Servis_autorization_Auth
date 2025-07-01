from flask import Flask, request, jsonify
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
import redis
import logging
import os

# Configure logging
logging.basicConfig(filename='/app/app.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
JAEGER_ENDPOINT = os.getenv('JAEGER_ENDPOINT', 'http://jaeger:4318/v1/traces')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

# Initialize Redis
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    logger.info("Storage Service: Connected to Redis at %s:%d", REDIS_HOST, REDIS_PORT)
except redis.ConnectionError as e:
    logger.error("Storage Service: Failed to connect to Redis: %s", str(e))
    raise

# OpenTelemetry setup
try:
    resource = Resource(attributes={"service.name": "storage-service"})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    otlp_exporter = OTLPSpanExporter(endpoint=JAEGER_ENDPOINT)
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    tracer = trace.get_tracer(__name__)
    FlaskInstrumentor().instrument_app(app)
    logger.info("Storage Service: Initialized OpenTelemetry with Jaeger at %s", JAEGER_ENDPOINT)
except Exception as e:
    logger.error("Storage Service: Failed to initialize OpenTelemetry: %s", str(e))
    raise

@app.route('/storage', methods=['GET'])
def storage():
    with tracer.start_as_current_span("storage-get") as span:
        try:
            username = request.args.get('username')
            if not username:
                raise Exception("Missing username parameter")
            redis_key = f"storage:{username}"
            redis_client.set(redis_key, f"Data for {username}")
            span.set_attribute("user.username", username)
            span.set_attribute("redis.key", redis_key)
            logger.info("Storage Service: Stored data for %s", username)
            return jsonify({"data": f"Storage for {username}"}), 200
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error("Storage Service: Error for %s: %s", username or "unknown", str(e))
            return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5002)
    finally:
        # Ensure spans are flushed on shutdown
        trace.get_tracer_provider().force_flush()