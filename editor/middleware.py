"""
Custom middleware for the editor app.
"""
import logging

logger = logging.getLogger(__name__)


class CORSMiddleware:
    """CORS設定ミドルウェア"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
        return response


class LoggingMiddleware:
    """リクエストログミドルウェア"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            msg = (
                f"=== リクエスト受信 ===\n"
                f"Method: {request.method}\n"
                f"Path: {request.path}\n"
                f"URL: {request.build_absolute_uri()}\n"
                f"Remote Address: {request.META.get('REMOTE_ADDR', 'N/A')}\n"
                f"User Agent: {request.META.get('HTTP_USER_AGENT', 'N/A')}"
            )
            logger.info(msg)
            print(msg, flush=True)
        except Exception as e:
            logger.error(f"リクエストログ記録エラー: {e}")
            print(f"リクエストログ記録エラー: {e}", flush=True)
        
        response = self.get_response(request)
        
        try:
            logger.info(f"=== レスポンス送信 ===\nStatus: {response.status_code}\nPath: {request.path}")
        except Exception:
            pass
        
        return response
