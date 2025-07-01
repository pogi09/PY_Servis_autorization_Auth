from flask import Flask, request, jsonify
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
import logging
import os

# Configure logging
logging.basicConfig(filename='/app/app.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load Jaeger endpoint
JAEGER_ENDPOINT = os.getenv('JAEGER_ENDPOINT', 'http://jaeger:4318/v1/traces')

# OpenTelemetry setup
try:
    resource = Resource(attributes={"service.name": "auth-service"})
    trace.set_tracer_provider(TracerProvider(resource=resource))
    otlp_exporter = OTLPSpanExporter(endpoint=JAEGER_ENDPOINT)
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    tracer = trace.get_tracer(__name__)
    FlaskInstrumentor().instrument_app(app)
    logger.info("Auth Service: Initialized OpenTelemetry with Jaeger at %s", JAEGER_ENDPOINT)
except Exception as e:
    logger.error("Auth Service: Failed to initialize OpenTelemetry: %s", str(e))
    raise

@app.route('/auth', methods=['POST'])
def auth():
    with tracer.start_as_current_span("auth") as span:
        try:
            if not request.is_json:
                raise ValueError("Content-Type must be application/json")
            data = request.json
            username = data.get('username')
            password = data.get('password')
            span.set_attribute("user.username", username)
            
            if username == 'test' and password == 'test':
                span.set_attribute("auth.result", "success")
                logger.info("Auth Service: Successful auth for %s", username)
                return jsonify({"status": "success"}), 200
            else:
                span.set_attribute("auth.result", "failed")
                raise Exception("Invalid credentials")
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error("Auth Service: Failed auth for %s: %s", username or "unknown", str(e))
            return jsonify({"error": str(e)}), 401

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5001)
    finally:
        # Ensure spans are flushed on shutdown
        trace.get_tracer_provider().force_flush()