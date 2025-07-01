from flask import Flask, request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
import redis
import json
import logging

logging.basicConfig(filename='app.log', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

# Настройка OpenTelemetry
resource = Resource(attributes={"service.name": "cache-service"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer(__name__)
FlaskInstrumentor().instrument_app(app)
logger.info("Cache Service: Sending traces to Jaeger at http://jaeger:4318/v1/traces")

@app.route('/cache', methods=['GET'])
def get_cache():
    with tracer.start_as_current_span("cache-get") as span:
        try:
            key = request.args.get('key')
            if not key:
                raise Exception("Missing key parameter")
            value = redis_client.get(key)
            span.set_attribute("cache.key", key)
            span.set_attribute("cache.operation", "get")
            if value:
                logger.info(f"Cache Service: Retrieved key {key}")
                return json.loads(value), 200
            raise Exception("Key not found")
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Cache Service: Error getting key {key}: {str(e)}")
            return {"error": str(e)}, 404

@app.route('/cache', methods=['POST'])
def set_cache():
    with tracer.start_as_current_span("cache-set") as span:
        try:
            data = request.json
            key = data.get('key')
            value = data.get('value')
            if not key or not value:
                raise Exception("Missing key or value")
            redis_client.setex(key, 3600, json.dumps(value))
            span.set_attribute("cache.key", key)
            span.set_attribute("cache.operation", "set")
            logger.info(f"Cache Service: Set key {key}")
            return {"status": "cached"}, 200
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Cache Service: Error setting key {key}: {str(e)}")
            return {"error": str(e)}, 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)